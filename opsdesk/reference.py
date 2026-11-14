"""Scripted reference desk (the "stronger reference run") and the simple baselines.

The reference talks to the environment ONLY through the same tools the agent gets
(`call(name, args) -> dict`), so it can run in-process or over MCP, and it provably
uses no hidden information. This file is standalone (stdlib only) on purpose: it is
copied verbatim into the Harbor oracle solution.

Every hour the reference:
  1. reads the alerts and turns closure notices into "doomed" flights,
  2. collects bookings that have problems, sit on a doomed flight, or that it moved before,
  3. serves them in order: deadline first, then tier weight, then group size,
  4. gives each the earliest legal itinerary that avoids doomed flights (and meets its deadline if possible),
  5. moves a healthy booking only if that gets it there at least an hour earlier (e.g. a new recovery flight).
"""
from __future__ import annotations

import re
from typing import Callable

CLOSURE_RE = re.compile(r"([A-Z]{3}) airport will be CLOSED (\d\d:\d\d)-(\d\d:\d\d)")
TIER = {"standard": 1.0, "gold": 1.5, "medical": 3.0, "umnr": 3.0}
SHIFT_END = "23:00"

Call = Callable[[str, dict], dict]


def t2m(s: str) -> int:
    s = s.strip()
    plus = s.startswith("+1")
    h, m = s.replace("+1", "").strip().split(":")
    return int(h) * 60 + int(m) + (1440 if plus else 0)


def doomed_flights(call: Call) -> set[str]:
    closures = []
    for a in call("read_alerts", {})["alerts"]:
        m = CLOSURE_RE.search(a["text"])
        if m:
            closures.append((m.group(1), t2m(m.group(2)), t2m(m.group(3))))
    out: set[str] = set()
    for ap, t0, t1 in closures:
        for leg in ("origin", "dest"):
            rows = call("list_flights", {leg: ap, "after": "00:00", "before": "+1 23:59"})["flights"]
            for f in rows:
                if f["status"] not in ("scheduled", "delayed"):
                    continue
                if (f["from"] == ap and t0 <= t2m(f["dep"]) < t1) or (f["to"] == ap and t0 <= t2m(f["arr"]) < t1):
                    out.add(f["flight"])
    return out


TURNAROUND, MCT = 40, 35


def projection(call: Call):
    """Knock-on delays not yet in the schedule: replay each aircraft's rotation with the 40-minute
    turnaround rule (stated in the instructions) and return extra minutes per flight."""
    hub = "HEL"
    rows = call("list_flights", {"origin": hub, "after": "00:00", "before": "+1 23:59"})["flights"]
    spokes = sorted({f["to"] for f in rows})
    for s_ in spokes:
        rows += call("list_flights", {"origin": s_, "after": "00:00", "before": "+1 23:59"})["flights"]
    tails: dict[str, list] = {}
    for f in rows:
        if f.get("carrier") == "AU":
            tails.setdefault(f["aircraft_reg"], []).append(f)
    extra: dict[str, int] = {}
    for legs in tails.values():
        legs.sort(key=lambda f: t2m(f.get("scheduled_dep", f["dep"])))
        prev_arr = None
        for f in legs:
            if f["status"] == "cancelled":
                prev_arr = None
                continue
            dep, arr = t2m(f["dep"]), t2m(f["arr"])
            if f["status"] in ("scheduled", "delayed") and prev_arr is not None and prev_arr + TURNAROUND > dep:
                d = prev_arr + TURNAROUND - dep
                extra[f["flight"]] = d
                arr += d
            prev_arr = arr
    legs_by_id = {f["flight"]: f for f in rows}
    return extra, legs_by_id


def projected_arr(o: dict, legs: dict[str, dict], extra: dict[str, int]) -> int | None:
    """Arrival of an itinerary under projected knock-on delays, or None if a connection would break."""
    prev = None
    for fid in o["flights"]:
        f = legs.get(fid)
        if f is None:
            return t2m(o["arr"]) if prev is None else None
        dep, arr = t2m(f["dep"]) + extra.get(fid, 0), t2m(f["arr"]) + extra.get(fid, 0)
        if prev is not None and dep < prev + MCT:
            return None
        prev = arr
    return prev


PARTNER_THRESHOLD = 0.6   # value gained per partner seat needed before spending the scarce allowance
BUMP = True


def value(b: dict, arr: int | None) -> float:
    """The published scoring rule for one booking arriving at `arr` (minutes)."""
    if arr is None:
        return 0.0
    if "must_arrive_by" in b and arr > t2m(b["must_arrive_by"]):
        return 0.0
    late = max(0, arr - t2m(b["originally_due"]))
    return TIER[b["tier"]] * b["pax"] * max(0.0, 1 - late / 1440)


def _ok(r: dict) -> bool:
    return bool(r.get("results", [{}])[0].get("ok"))


def try_bump(call: Call, p: str, b: dict, doomed: set[str], moved: set[str], have: float) -> bool:
    """Free seats for an urgent group by moving healthy, flexible groups to their next-best option,
    but only when the urgent group gains more than the moved groups lose."""
    res = call("search_itineraries", {"pnrs": [p], "include_full": True})["results"][0]
    opts = [o for o in res.get("options", []) if not any(f in doomed for f in o["flights"])]
    opts.sort(key=lambda o: -value(b, t2m(o["arr"])))
    for o in opts[:3]:
        gain = value(b, t2m(o["arr"])) - have
        if gain <= 0.5:
            return False
        plan, cost = [], 0.0
        for fid in o["flights"]:
            fl = call("get_flight", {"flight": fid})
            deficit = b["pax"] - (fl["seats_free"] if isinstance(fl["seats_free"], int) else 999)
            if deficit <= 0:
                continue
            cands = []
            for r in fl["bookings"]:
                q = r["pnr"]
                if q == p or q in [x[0] for x in plan]:
                    continue
                bq = call("get_booking", {"pnr": q})
                if bq.get("location") in (None, "airborne") or bq.get("problems") or "must_arrive_by" in bq \
                        or bq["tier"] in ("medical", "umnr"):
                    continue
                cur = value(bq, t2m(bq["itinerary"][-1]["arr"]))
                alt = call("search_itineraries", {"pnrs": [q]})["results"][0].get("options", [])
                alt = [x for x in alt if not any(f in doomed or f in o["flights"] for f in x["flights"])]
                if not alt:
                    continue
                best = max(alt, key=lambda x: value(bq, t2m(x["arr"])))
                cands.append((cur - value(bq, t2m(best["arr"])), q, best["flights"], bq["pax"]))
            cands.sort()
            freed = 0
            for c, q, fl2, pax in cands:
                if freed >= deficit:
                    break
                plan.append((q, fl2))
                cost += c
                freed += pax
            if freed < deficit:
                plan = None
                break
        if plan is None or cost >= gain:
            continue
        for q, fl2 in plan:
            if _ok(call("rebook", {"changes": [{"pnr": q, "flights": fl2}]})):
                moved.add(q)
        if _ok(call("rebook", {"changes": [{"pnr": p, "flights": o["flights"]}]})):
            moved.add(p)
            return True
    return False


def plan_tick(call: Call, moved: set[str]):
    doomed = doomed_flights(call)
    extra, legs = projection(call)

    def arr_of(o):
        return projected_arr(o, legs, extra)

    def itin_arr(b):
        rem = [s["flight"] for s in b["itinerary"] if not s["flown"]]
        if not rem:
            return None
        return arr_of({"flights": rem, "arr": b["itinerary"][-1]["arr"]})

    info: dict[str, dict] = {}
    for r in call("find_disrupted_bookings", {})["bookings"]:
        info[r["pnr"]] = {"broken": True}
    for fid in extra:
        for r in call("get_flight", {"flight": fid})["bookings"]:
            info.setdefault(r["pnr"], {"broken": False})
    for fid in doomed:
        try:
            for r in call("get_flight", {"flight": fid})["bookings"]:
                info.setdefault(r["pnr"], {"broken": True})
        except KeyError:
            pass
    for p in moved:
        info.setdefault(p, {"broken": False})
    books = {}
    for p in list(info):
        b = call("get_booking", {"pnr": p})
        if "error" in b or b.get("arrived") or b.get("location") == "airborne":
            info.pop(p)
            continue
        books[p] = b

    def prio(p):
        b = books[p]
        dl = t2m(b["must_arrive_by"]) if "must_arrive_by" in b else None
        return (0 if dl is not None else 1, dl or 0, -TIER[b["tier"]], -b["pax"], p)

    order = sorted(info, key=prio)
    deferred: set[str] = set()
    urgent_left: list[str] = []
    i = 0
    while i < len(order):
        p = order[i]
        i += 1
        b = call("get_booking", {"pnr": p})
        if b.get("arrived") or b.get("location") == "airborne":
            continue
        rem = [s["flight"] for s in b["itinerary"] if not s["flown"]]
        broken = bool(b.get("problems")) or any(f in doomed for f in rem) or itin_arr(b) is None
        cur_val = 0.0 if broken else value(b, itin_arr(b))
        res = call("search_itineraries", {"pnrs": [p]})
        left = res["partner_seats_left"]
        res = res["results"][0]
        au = [o for o in res.get("options", []) if not any(f in doomed for f in o["flights"]) and arr_of(o)]
        nl = [o for o in res.get("partner_options", []) if not any(f in doomed for f in o["flights"]) and arr_of(o)]
        best_au = max(au, key=lambda o: (value(b, arr_of(o)), -arr_of(o))) if au else None
        best_nl = max(nl, key=lambda o: (value(b, arr_of(o)), -arr_of(o))) if nl else None
        v_au = value(b, arr_of(best_au)) if best_au else 0.0
        v_nl = value(b, arr_of(best_nl)) if best_nl else 0.0
        if "must_arrive_by" in b and v_au == 0 and v_nl == 0 and p not in deferred:
            deferred.add(p)          # deadline already lost: still get them home, after everyone else
            order.append(p)
            continue
        choice, v = best_au, v_au
        if best_nl and b["pax"] <= left and (v_nl - v_au) / b["pax"] >= PARTNER_THRESHOLD:
            choice, v = best_nl, v_nl
        if choice is None:
            if broken and ("must_arrive_by" in b or b["tier"] in ("medical", "umnr")):
                urgent_left.append(p)
            continue
        if not broken and v <= cur_val + 0.05 * TIER[b["tier"]] * b["pax"]:
            continue
        if choice["flights"] != rem and _ok(call("rebook", {"changes": [{"pnr": p, "flights": choice["flights"]}]})):
            moved.add(p)
        full = TIER[b["tier"]] * b["pax"]
        if ("must_arrive_by" in b or b["tier"] in ("medical", "umnr")) and v < 0.5 * full:
            urgent_left.append(p)
    if BUMP:
        for p in urgent_left:
            b = call("get_booking", {"pnr": p})
            if b.get("arrived") or b.get("location") == "airborne":
                continue
            rem = [s["flight"] for s in b["itinerary"] if not s["flown"]]
            have = 0.0 if (b.get("problems") or any(f in doomed for f in rem) or itin_arr(b) is None) \
                else value(b, itin_arr(b))
            try_bump(call, p, b, doomed, moved, have)


def run_reference(call: Call):
    moved: set[str] = set()
    while True:
        plan_tick(call, moved)
        st = call("get_status", {})
        if st["time"] == SHIFT_END:
            break
        call("advance_clock", {"minutes": 60})
    call("end_shift", {"handover": "reference desk"})


def run_nothing(call: Call):
    call("end_shift", {"handover": ""})


def run_stop_early(call: Call, hours: int = 3):
    """Acts exactly like the reference for the first few hours, then quits."""
    moved: set[str] = set()
    for _ in range(hours):
        plan_tick(call, moved)
        call("advance_clock", {"minutes": 60})
    call("end_shift", {"handover": "stopping early"})


def run_naive(call: Call):
    """A plausible first-attempt desk: every hour, fix what is listed, in list order, with the first option."""
    while True:
        rows = call("find_disrupted_bookings", {})["bookings"]
        for i in range(0, len(rows), 20):
            res = call("search_itineraries", {"pnrs": [r["pnr"] for r in rows[i:i + 20]]})["results"]
            for r in res:
                if r.get("options"):
                    call("rebook", {"changes": [{"pnr": r["pnr"], "flights": r["options"][0]["flights"]}]})
        if call("get_status", {})["time"] == SHIFT_END:
            break
        call("advance_clock", {"minutes": 60})
    call("end_shift", {"handover": ""})


POLICIES = {"reference": run_reference, "nothing": run_nothing, "stop_early": run_stop_early, "naive": run_naive}


class StdlibMCP:
    """Tiny MCP streamable-HTTP client using only the standard library (so the oracle needs no installs)."""

    def __init__(self, url: str):
        self.url, self.sid, self.n = url, None, 0
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "opsdesk-reference", "version": "1"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, msg: dict):
        import json
        import urllib.request
        req = urllib.request.Request(self.url, data=json.dumps(msg).encode(), method="POST", headers={
            "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
            **({"Mcp-Session-Id": self.sid} if self.sid else {})})
        with urllib.request.urlopen(req, timeout=600) as r:
            self.sid = r.headers.get("Mcp-Session-Id") or self.sid
            body = r.read().decode()
            if not body.strip():
                return None
            if "text/event-stream" in (r.headers.get("Content-Type") or ""):
                datas = [ln[5:].strip() for ln in body.splitlines() if ln.startswith("data:")]
                return json.loads(datas[-1]) if datas else None
            return json.loads(body)

    def _rpc(self, method: str, params: dict):
        self.n += 1
        out = self._send({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params})
        if out is None or "error" in out:
            raise RuntimeError(f"MCP {method} failed: {out}")
        return out["result"]

    def __call__(self, name: str, args: dict) -> dict:
        import json
        res = self._rpc("tools/call", {"name": name, "arguments": args})
        return json.loads(res["content"][0]["text"])


if __name__ == "__main__":  # python reference.py http://host:8000/mcp [reference|nothing|stop_early|naive]
    import sys
    POLICIES[sys.argv[2] if len(sys.argv) > 2 else "reference"](StdlibMCP(sys.argv[1]))
