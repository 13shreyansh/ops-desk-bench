"""One-command evaluation.

    python -m opsdesk.eval                         # reference, do-nothing, stop-early, naive, exploit checks
    python -m opsdesk.eval --agent gemini-4-argon --runs 3   # plus 3 agent runs per seed (needs GEMINI_API_KEY)

Writes results/<size>/summary.json and prints a table. Everything except the LLM calls is deterministic.
"""
from __future__ import annotations

import argparse
import json
import statistics
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .env import OpsDesk
from .reference import POLICIES
from .verify import report

ROOT = Path(__file__).resolve().parent.parent


def scripted(name: str, seed: int, size: str) -> dict:
    env = OpsDesk(seed, size)
    POLICIES[name](env.tool)
    if not env.ended:
        env.finish(reason="harness")
    return report(env)


def agent_run(model: str, seed: int, size: str, k: int, out: Path) -> dict:
    from .agent_gemini import run_agent
    d = out / "agents" / model / f"seed{seed}_run{k}"
    env = run_agent(seed, size, model, d)
    r = report(env)
    r["agent"] = env.agent_meta
    (d / "report.json").write_text(json.dumps(r, indent=1))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="standard")
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--agent", default=None, help="Gemini model id, e.g. gemini-4-argon")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--parallel", type=int, default=3)
    a = ap.parse_args()
    out = ROOT / "results" / a.size
    out.mkdir(parents=True, exist_ok=True)
    summary: dict = {"size": a.size, "seeds": a.seeds, "policies": {}}
    for name in ("reference", "nothing", "stop_early", "naive"):
        rs = [scripted(name, s, a.size) for s in a.seeds]
        summary["policies"][name] = {"scores": [r["score"] for r in rs],
                                     "failure_modes": [{k: v["count"] for k, v in r["failure_modes"].items()} for r in rs]}
        (out / f"{name}.json").write_text(json.dumps(rs, indent=1))
    if a.agent:
        jobs = [(s, k) for s in a.seeds for k in range(a.runs)]
        with ThreadPoolExecutor(a.parallel) as ex:
            rs = list(ex.map(lambda sk: agent_run(a.agent, sk[0], a.size, sk[1], out), jobs))
        summary["policies"][a.agent] = {"scores": [r["score"] for r in rs], "runs": [list(j) for j in jobs],
                                        "failure_modes": [{k: v["count"] for k, v in r["failure_modes"].items()} for r in rs],
                                        "agent": [r["agent"] for r in rs]}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(f"\nOps Desk, size={a.size}, seeds={a.seeds}")
    print(f"{'policy':22s} {'mean':>7s} {'min':>7s} {'max':>7s}   scores")
    for name, d in summary["policies"].items():
        s = d["scores"]
        print(f"{name:22s} {statistics.mean(s):7.3f} {min(s):7.3f} {max(s):7.3f}   " + " ".join(f"{x:.3f}" for x in s))


if __name__ == "__main__":
    main()
