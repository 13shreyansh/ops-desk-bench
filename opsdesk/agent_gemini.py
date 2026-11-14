"""Minimal tool-calling agent loop for Gemini models (REST, no SDK).

It mirrors what a coding-agent harness does: the model sees the instruction, calls
tools, sees results, and the episode ends when the model stops calling tools,
calls end_shift, or hits the turn cap. The full transcript is saved.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

from .env import OpsDesk
from .tools import TOOLS

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _decl(t):
    params = t["parameters"]
    if not params.get("properties"):
        return {"name": t["name"], "description": t["description"]}
    return {"name": t["name"], "description": t["description"], "parameters": params}


def call(model: str, contents: list, system: str, retries: int = 6) -> dict:
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "tools": [{"functionDeclarations": [_decl(t) for t in TOOLS]}],
        "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}},
        "generationConfig": {"temperature": 1.0},
    }
    if os.environ.get("OPSDESK_THINKING"):
        body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": os.environ["OPSDESK_THINKING"]}
    for i in range(retries):
        try:
            r = requests.post(API.format(model=model), params={"key": os.environ["GEMINI_API_KEY"]},
                              json=body, timeout=600)
            if r.status_code == 200:
                return r.json()
            err = r.text[:500]
        except requests.RequestException as e:
            err = str(e)
        time.sleep(min(60, 4 * 2 ** i))
    raise RuntimeError(f"Gemini API failed after {retries} tries: {err}")


def run_agent(seed: int, size: str, model: str, out_dir: str | Path, max_turns: int = 300) -> OpsDesk:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    env = OpsDesk(seed, size)
    system = (Path(__file__).with_name("instruction.md")).read_text()
    contents = [{"role": "user", "parts": [{"text": "Your shift starts now. Use the tools."}]}]
    usage = {"prompt": 0, "output": 0, "thoughts": 0, "cached": 0}
    infra_errors = 0
    log = open(out / "transcript.jsonl", "w")
    stop = "turn_cap"
    for turn in range(max_turns):
        try:
            resp = call(model, contents, system)
        except RuntimeError as e:
            infra_errors += 1
            stop = f"infra_error: {e}"[:300]
            break
        um = resp.get("usageMetadata", {})
        usage["prompt"] += um.get("promptTokenCount", 0)
        usage["output"] += um.get("candidatesTokenCount", 0)
        usage["thoughts"] += um.get("thoughtsTokenCount", 0)
        usage["cached"] += um.get("cachedContentTokenCount", 0)
        cands = resp.get("candidates") or []
        if not cands or "content" not in cands[0]:
            log.write(json.dumps({"turn": turn, "empty": resp.get("promptFeedback") or cands}) + "\n")
            stop = "empty_response"
            break
        content = cands[0]["content"]
        content.setdefault("role", "model")
        contents.append(content)
        calls = [p["functionCall"] for p in content.get("parts", []) if "functionCall" in p]
        texts = [p["text"] for p in content.get("parts", []) if "text" in p and not p.get("thought")]
        log.write(json.dumps({"turn": turn, "t": env.now, "text": texts, "calls": calls}) + "\n")
        if not calls:
            stop = "model_stopped"
            break
        parts = []
        for c in calls:
            res = env.tool(c["name"], c.get("args") or {})
            rs = json.dumps(res)
            log.write(json.dumps({"turn": turn, "tool": c["name"], "args": c.get("args"),
                                  "result": rs if len(rs) < 3000 else rs[:3000] + "..."}) + "\n")
            parts.append({"functionResponse": {"name": c["name"], "response": {"result": res}}})
        contents.append({"role": "user", "parts": parts})
        log.flush()
        if env.ended:
            stop = "end_shift"
            break
    log.close()
    if not env.ended:
        env.finish(reason="agent")
    env.agent_meta = {"model": model, "stop": stop, "turns": turn + 1, "usage": usage, "infra_errors": infra_errors}
    return env
