"""Export compact JSON for the replay viewer (web/).

For every run it replays the logged actions on a fresh environment (the env is deterministic,
so the replay is exact) and records, at each hour, the value the desk has secured so far:
the value the day would end with if the desk stopped right there.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .env import OpsDesk
from .reference import POLICIES
from .verify import report, total_value
from .world import hhmm

ROOT = Path(__file__).resolve().parent.parent


def projected(env: OpsDesk) -> float:
    e = copy.deepcopy(env)
    e.finish(reason="projection")
    return total_value(e)


def trace_policy(seed, size, name):
    env = OpsDesk(seed, size)
    curve = []

    def call(tool, args):
        if tool in ("advance_clock", "end_shift"):
            curve.append({"t": hhmm(env.now), "value": round(projected(env), 2)})
        return env.tool(tool, args)
    POLICIES[name](call)
    if not env.ended:
        env.finish(reason="harness")
    return env, curve


def trace_actions(seed, size, actions):
    env = OpsDesk(seed, size)
    curve = []
    for name, args in actions:
        if env.ended:
            break
        if name in ("advance_clock", "end_shift"):
            curve.append({"t": hhmm(env.now), "value": round(projected(env), 2)})
        env.tool(name, args)
    if not env.ended:
        curve.append({"t": hhmm(env.now), "value": round(projected(env), 2)})
        env.finish(reason="agent")
    return env, curve


def actions_from_transcript(path: Path):
    acts = []
    for line in open(path):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "calls" in d:
            for c in d["calls"]:
                acts.append((c["name"], c.get("args") or {}))
    return acts


def summarize(env, curve, label, extra=None):
    r = report(env)
    rebooks = [{"t": hhmm(l.t), "pnr": l.data["pnr"], "new": l.data["new"]} for l in env.log if l.kind == "rebook"]
    tools = {}
    for l in env.log:
        if l.kind == "tool":
            tools[l.data["name"]] = tools.get(l.data["name"], 0) + 1
    return {"label": label, "score": r["score"], "value": r["value"], "ended_at": r["ended_at"],
            "end_reason": r["end_reason"], "tool_calls": r["tool_calls"], "tool_errors": r["tool_errors"],
            "failure_modes": r["failure_modes"], "coherence": r["coherence"], "curve": curve,
            "rebooks": len(rebooks), "tools": tools, **(extra or {})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="standard")
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--runs", default=str(ROOT / "results"), help="folder with agents/<model>/seed*_run*/transcript.jsonl")
    ap.add_argument("--out", default=str(ROOT / "web" / "data" / "runs.json"))
    a = ap.parse_args()
    data = {"size": a.size, "seeds": {}}
    for seed in a.seeds:
        base = OpsDesk(seed, a.size)
        sd = {"events": [{"id": e.id, "time": hhmm(e.at), "kind": e.kind, "text": e.text} for e in base.events],
              "flights": len(base.flights), "bookings": len(base.bookings),
              "passengers": sum(b.pax for b in base.bookings.values()), "runs": []}
        for name in ("reference", "nothing", "stop_early", "naive"):
            env, curve = trace_policy(seed, a.size, name)
            sd["runs"].append(summarize(env, curve, name, {"kind": "scripted"}))
        rd = Path(a.runs) / a.size / "agents"
        if rd.exists():
            for tr in sorted(rd.glob(f"*/seed{seed}_run*/transcript.jsonl")):
                model = tr.parent.parent.name
                env, curve = trace_actions(seed, a.size, actions_from_transcript(tr))
                meta = {}
                rp = tr.parent / "report.json"
                if rp.exists():
                    meta = json.loads(rp.read_text()).get("agent", {})
                sd["runs"].append(summarize(env, curve, f"{model} #{tr.parent.name.split('_run')[-1]}",
                                            {"kind": "agent", "model": model, "agent": meta}))
        data["seeds"][str(seed)] = sd
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(data))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
