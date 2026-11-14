"""MCP server exposing one Ops Desk episode (streamable HTTP or stdio).

Environment variables:
  OPSDESK_SEED   scenario seed (default 0)
  OPSDESK_SIZE   small | standard (default standard)
  OPSDESK_GRADER_TOKEN  if set, enables GET /grade?token=... for the verifier (never shown to the agent)
  OPSDESK_LOG_DIR  where to write the final snapshot when graded (optional)
"""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .env import OpsDesk

SEED = int(os.environ.get("OPSDESK_SEED", "0"))
SIZE = os.environ.get("OPSDESK_SIZE", "standard")
TOKEN = os.environ.get("OPSDESK_GRADER_TOKEN", "")

ENV = OpsDesk(SEED, SIZE)
LOCK = threading.Lock()
mcp = FastMCP("opsdesk", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")),
              instructions=(Path(__file__).with_name("instruction.md")).read_text())


def _run(name: str, args: dict) -> str:
    with LOCK:
        return json.dumps(ENV.tool(name, {k: v for k, v in args.items() if v is not None}))


@mcp.tool()
def get_status() -> str:
    """Current sim time, shift end, number of alerts published and how many bookings currently have problems."""
    return _run("get_status", {})


@mcp.tool()
def read_alerts(since: str | None = None) -> str:
    """All operations alerts published so far (cancellations, delays, notices, added flights), oldest first.
    Pass `since` (an alert id) to get only newer ones."""
    return _run("read_alerts", {"since": since})


@mcp.tool()
def list_flights(origin: str | None = None, dest: str | None = None,
                 after: str | None = None, before: str | None = None) -> str:
    """Published schedule with current times, status and free seats. Optional filters: origin, dest (airport codes)
    and a departure window after/before as HH:MM (prefix '+1 ' for tomorrow). Max 60 rows (150 when origin or dest is given)."""
    return _run("list_flights", {"origin": origin, "dest": dest, "after": after, "before": before})


@mcp.tool()
def get_flight(flight: str) -> str:
    """One flight with its manifest (bookings currently on it)."""
    return _run("get_flight", {"flight": flight})


@mcp.tool()
def get_booking(pnr: str) -> str:
    """One booking: passengers, tier, deadline, current location, itinerary and any problems."""
    return _run("get_booking", {"pnr": pnr})


@mcp.tool()
def find_disrupted_bookings() -> str:
    """Every booking that will NOT reach its destination as currently booked (cancelled flight, misconnection,
    missed flight, or will be denied boarding on an oversold flight). Uses the current schedule only; it does not
    apply notices about future closures."""
    return _run("find_disrupted_bookings", {})


@mcp.tool()
def search_itineraries(pnrs: list[str]) -> str:
    """For up to 20 bookings, the legal itineraries (direct or via HEL) from where the group is now, earliest
    arrival first, with free seats. Respects check-in cut-off and minimum connection time. Does not apply notices
    about future closures."""
    return _run("search_itineraries", {"pnrs": pnrs})


@mcp.tool()
def rebook(changes: list[dict]) -> str:
    """Replace the remaining itinerary of up to 25 bookings. Each change is {"pnr": "...", "flights": ["AU123", ...]};
    the whole group moves together. Changes are applied in order and each is validated (seats, cut-off,
    connection time, route)."""
    return _run("rebook", {"changes": changes})


@mcp.tool()
def advance_clock(minutes: int = 60) -> str:
    """Let the operation run for 30 or 60 minutes. Flights depart and land, and new alerts may arrive.
    Returns the new alerts."""
    return _run("advance_clock", {"minutes": minutes})


@mcp.tool()
def end_shift(handover: str = "") -> str:
    """End your shift and hand over. Nothing more can be changed afterwards; the rest of the operation
    (including tomorrow's flights) runs without the desk."""
    return _run("end_shift", {"handover": handover})


if TOKEN:
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    @mcp.custom_route("/grade", methods=["GET"])
    async def grade(request: Request):
        if request.query_params.get("token") != TOKEN:
            return JSONResponse({"error": "forbidden"}, status_code=403)
        from .verify import report
        with LOCK:
            if not ENV.ended:
                ENV.finish(reason="harness")
            rep = report(ENV)
            snap = ENV.snapshot()
        d = os.environ.get("OPSDESK_LOG_DIR")
        if d:
            Path(d).mkdir(parents=True, exist_ok=True)
            (Path(d) / "snapshot.json").write_text(json.dumps(snap))
        return JSONResponse({"report": rep, "snapshot": snap})


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    from starlette.responses import PlainTextResponse
    return PlainTextResponse("ok")


def main():
    transport = sys.argv[1] if len(sys.argv) > 1 else "streamable-http"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
