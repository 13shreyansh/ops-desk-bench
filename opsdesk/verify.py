"""Verifier: reward and named failure modes, computed from the final world state and the action log.

Reward
------
Each booking is worth  weight x f(delay), where weight = tier weight x passengers and
    f = 1                                 if it arrives no later than originally due,
    f = max(0, 1 - delay / 12 h)          otherwise,
    f = 0                                 if it misses a stated deadline or never arrives.

    score = (V_agent - V_nothing) / (V_reference - V_nothing)

so doing nothing scores exactly 0 and the scripted reference scores 1. The two anchor
runs are recomputed from the seed at grading time, never read from the agent's side.
"""
from __future__ import annotations

from functools import lru_cache

from .env import OpsDesk
from .world import CHECKIN_CUTOFF, HUB, SHIFT_END, TIER_WEIGHT, hhmm

DECAY_MIN = 24 * 60
PRIORITY_TIERS = ("medical", "umnr")


def booking_value(env: OpsDesk, p: str) -> float:
    b, st = env.bookings[p], env.state[p]
    if st.arrived_at is None:
        return 0.0
    if b.deadline is not None and st.arrived_at > b.deadline:
        return 0.0
    delay = max(0, st.arrived_at - b.orig_arrival)
    return b.weight * max(0.0, 1 - delay / DECAY_MIN)


def total_value(env: OpsDesk) -> float:
    return sum(booking_value(env, p) for p in env.bookings)


@lru_cache(maxsize=64)
def anchors(seed: int, size: str) -> dict:
    from .reference import run_nothing, run_reference
    n, r = OpsDesk(seed, size), OpsDesk(seed, size)
    run_nothing(n.tool)
    run_reference(r.tool)
    return {"v_nothing": total_value(n), "v_reference": total_value(r),
            "per_pnr_nothing": {p: booking_value(n, p) for p in n.bookings},
            "per_pnr_reference": {p: booking_value(r, p) for p in r.bookings},
            "max_value": sum(b.weight for b in n.bookings.values())}


def score(env: OpsDesk) -> dict:
    a = anchors(env.seed, env.size)
    v = total_value(env)
    span = a["v_reference"] - a["v_nothing"]
    s = (v - a["v_nothing"]) / span if span > 0 else 0.0
    return {"score": round(s, 4), "value": round(v, 2), "v_nothing": round(a["v_nothing"], 2),
            "v_reference": round(a["v_reference"], 2), "value_at_stake": round(a["max_value"] - a["v_nothing"], 2)}


def failure_modes(env: OpsDesk) -> dict:
    """Concrete, code-detected failure modes. Each entry lists the bookings involved."""
    a = anchors(env.seed, env.size)
    ref = a["per_pnr_reference"]
    nothing = a["per_pnr_nothing"]
    vals = {p: booking_value(env, p) for p in env.bookings}
    rebooks = [l for l in env.log if l.kind == "rebook"]
    by_pnr: dict[str, list] = {}
    for l in rebooks:
        by_pnr.setdefault(l.data["pnr"], []).append(l)
    end_t = getattr(env, "end_time", SHIFT_END)
    seen = getattr(env, "problem_ticks", {})
    out: dict[str, list] = {k: [] for k in (
        "never_handled", "cascade_blind", "ignored_notice", "procrastinated", "worse_choice",
        "priority_inversion", "harmful_churn", "denied_boarding", "stopped_early")}

    from .reference import CLOSURE_RE
    from .env import _parse  # noqa
    notices = []
    for e in env.events:
        m = CLOSURE_RE.search(e.text)
        if m:
            notices.append((e.at, m.group(1), _parse(m.group(2)), _parse(m.group(3))))

    def lost(p):  # value the reference kept that the agent did not
        return ref[p] - vals[p] > 0.05 * env.bookings[p].weight

    for p, ticks in seen.items():
        b = env.bookings[p]
        if not lost(p):
            continue
        reb = by_pnr.get(p, [])
        first_bad = ticks[0][0]
        acted_after = [l for l in reb if l.t >= first_bad]
        had_option = any(t[2] is not None for t in ticks if t[0] <= end_t)
        if not acted_after and had_option:
            out["never_handled"].append(p)
            continue
        # it was handled once, broke again later and was left broken
        if acted_after:
            last = acted_after[-1].t
            later = [t for t in ticks if t[0] > last]
            if later and any(t[2] is not None for t in later):
                out["cascade_blind"].append(p)
        # option quality decayed while waiting
        if acted_after:
            first_eta = next((t[2] for t in ticks if t[2] is not None), None)
            got = acted_after[0].data.get("eta")
            if first_eta is not None and got is not None and got > first_eta + 120 and acted_after[0].t > first_bad:
                out["procrastinated"].append(p)

    for l in rebooks:
        p = l.data["pnr"]
        # booked through a flight that a published closure notice already covered
        for (at, ap, t0, t1) in notices:
            if at <= l.t:
                for fid in l.data["new"]:
                    f = env.flights[fid]
                    if (f.origin == ap and t0 <= f.std < t1) or (f.dest == ap and t0 <= f.sta < t1):
                        out["ignored_notice"].append(p)
        be, eta = l.data.get("best_eta"), l.data.get("eta")
        if be is not None and eta is not None and eta - be >= 180 and lost(p):
            out["worse_choice"].append(p)
        if not l.data.get("had_problem") and vals[p] < nothing[p] - 1e-9:
            out["harmful_churn"].append(p)

    # a priority booking lost value while the desk moved lower-priority bookings onto
    # flights leaving from where the priority group was waiting, toward its destination
    for p in seen:
        b = env.bookings[p]
        if not (b.deadline or b.tier in PRIORITY_TIERS) or not lost(p):
            continue
        t0 = seen[p][0][0]
        loc = env.bookings[p].origin
        for l in rebooks:
            q = l.data["pnr"]
            if l.t < t0 or q == p:
                continue
            bq = env.bookings[q]
            if bq.deadline or TIER_WEIGHT[bq.tier] >= TIER_WEIGHT[b.tier]:
                continue
            f0 = env.flights[l.data["new"][0]]
            if f0.dest == b.dest or (f0.dest == HUB and env.flights[l.data["new"][-1]].dest == b.dest):
                out["priority_inversion"].append(p)
                break

    out["denied_boarding"] = sorted({l.data["pnr"] for l in env.log if l.kind == "denied_boarding"})
    if env.end_reason == "agent" and end_t < SHIFT_END:
        out["stopped_early"] = [e.id for e in env.events if e.at > end_t]

    res = {}
    for k, v in out.items():
        v = sorted(set(v))
        res[k] = {"count": len(v), "examples": v[:8],
                  "value_lost": round(sum(max(0.0, ref.get(p, 0) - vals.get(p, 0)) for p in v if p in vals), 2)}
    return res


def coherence_curve(env: OpsDesk) -> list[dict]:
    """For each alert, how much of the reference's recovery the agent achieved for the bookings it hit."""
    a = anchors(env.seed, env.size)
    ref, nothing = a["per_pnr_reference"], a["per_pnr_nothing"]
    vals = {p: booking_value(env, p) for p in env.bookings}
    seen = getattr(env, "problem_ticks", {})
    rows = []
    for e in env.events:
        hit = [p for p, t in seen.items() if e.at <= t[0][0] < e.at + 60]
        gain_ref = sum(ref[p] - nothing[p] for p in hit)
        gain = sum(vals[p] - nothing[p] for p in hit)
        rows.append({"alert": e.id, "time": hhmm(e.at), "kind": e.kind, "bookings_hit": len(hit),
                     "recovered": round(gain / gain_ref, 3) if gain_ref > 1e-9 else None})
    return rows


def report(env: OpsDesk) -> dict:
    return {"seed": env.seed, "size": env.size, **score(env),
            "end_reason": env.end_reason, "ended_at": hhmm(getattr(env, "end_time", env.now)),
            "tool_calls": env.tool_calls, "tool_errors": env.tool_errors,
            "failure_modes": failure_modes(env), "coherence": coherence_curve(env)}
