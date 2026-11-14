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


def plan_tick(call: Call, moved: set[str]):
    doomed = doomed_flights(call)
    info: dict[str, dict] = {}
    for r in call("find_disrupted_bookings", {})["bookings"]:
        info[r["pnr"]] = {"broken": True}
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
    i = 0
    while i < len(order):
        p = order[i]
        i += 1
        b = call("get_booking", {"pnr": p})
        if b.get("arrived") or b.get("location") == "airborne":
            continue
        rem = [s["flight"] for s in b["itinerary"] if not s["flown"]]
        broken = bool(b.get("problems")) or any(f in doomed for f in rem)
        res = call("search_itineraries", {"pnrs": [p]})["results"][0]
        opts = [o for o in res.get("options", []) if not any(f in doomed for f in o["flights"])]
        if not opts:
            continue
        if "must_arrive_by" in b:
            ok = [o for o in opts if t2m(o["arr"]) <= t2m(b["must_arrive_by"])]
            if not ok and p not in deferred:
                # the deadline can no longer be met: still get them home, but after everyone it can help
                deferred.add(p)
                order.append(p)
                continue
            opts = ok or opts
        best = opts[0]
        if not broken:
            cur_arr = next((t2m(s["arr"]) for s in reversed(b["itinerary"])), None)
            if cur_arr is None or t2m(best["arr"]) > cur_arr - 60:
                continue
        if best["flights"] != rem:
            r = call("rebook", {"changes": [{"pnr": p, "flights": best["flights"]}]})
            if r.get("results", [{}])[0].get("ok"):
                moved.add(p)


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
