"""The Ops Desk simulator: world state, agent actions and the clock.

The environment is deterministic. Given the seed and the sequence of actions,
the outcome is always identical.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field

from .world import (AIRCRAFT, TURNAROUND, CHECKIN_CUTOFF, HUB, MCT, PARTNER_SEATS, SHIFT_END, SHIFT_START, SIM_END, TICK,
                    Booking, Flight, generate, hhmm)


class ActionError(Exception):
    pass


@dataclass
class PaxState:
    location: str | None      # airport, or None while airborne
    ready: int                # minute the group is available at `location`
    flown: int = 0            # number of itinerary legs flown
    arrived_at: int | None = None
    offloaded: bool = False


@dataclass
class LogEntry:
    t: int
    kind: str
    data: dict = field(default_factory=dict)


class OpsDesk:
    def __init__(self, seed: int = 0, size: str = "standard", profile: str = "all"):
        self.seed, self.size = seed, size
        self.profile = profile
        sc = generate(seed, size, profile)
        self.flights: dict[str, Flight] = sc.flights
        self.bookings: dict[str, Booking] = sc.bookings
        self.events = sc.events
        self.original = {p: list(b.itinerary) for p, b in self.bookings.items()}
        self.state = {p: PaxState(b.origin, 0) for p, b in self.bookings.items()}
        self.now = SHIFT_START
        self.fired: list[str] = []
        self.ended = False
        self.end_reason = ""
        self.log: list[LogEntry] = []
        self.seq = max(b.booked_seq for b in self.bookings.values())
        self.tool_calls = 0
        self.tool_errors = 0
        self.dyn_alerts: list[dict] = []
        # the night before the shift has already happened: overnight flights are airborne or landed
        self.now = -1
        self._fly_until(SHIFT_START)
        self.now = SHIFT_START
        self._fire_events()
        self._scan()

    # ------------------------------------------------------------------ helpers
    def _visible(self, f: Flight) -> bool:
        return f.visible_from <= self.now

    def booked(self, fid: str) -> int:
        if getattr(self, "_dirty", True):
            c: dict[str, int] = {}
            for p, b in self.bookings.items():
                for x in b.itinerary[self.state[p].flown:]:
                    c[x] = c.get(x, 0) + b.pax
            self._counts, self._dirty = c, False
        return self._counts.get(fid, 0)

    def _avail(self, fid: str) -> int:
        f = self.flights[fid]
        return f.seats - self.booked(fid)

    def _remaining(self, p: str) -> list[str]:
        return self.bookings[p].itinerary[self.state[p].flown:]

    def problems(self, p: str, include_airborne: bool = False) -> list[str]:
        """Why a booking will not reach its destination as currently booked (empty = fine)."""
        b, st = self.bookings[p], self.state[p]
        if st.arrived_at is not None:
            return []
        rem = self._remaining(p)
        if st.location is None and not include_airborne:
            return []  # public tools defer airborne issues until landing
        if not rem:
            return ["no onward flight booked"]
        out = []
        prev_ready, loc = st.ready, st.location if st.location is not None else st._dest
        need_mct = st.flown > 0
        for i, fid in enumerate(rem):
            f = self.flights[fid]
            if f.status == "cancelled":
                out.append(f"{fid} cancelled")
                break
            if f.status in ("departed", "arrived"):
                out.append(f"{fid} departed without them")
                break
            if f.origin != loc:
                out.append(f"{fid} departs {f.origin} but they are at {loc}")
                break
            if f.etd < prev_ready + (MCT if need_mct else 0):
                out.append(f"misconnect onto {fid} (needs {MCT} min, has {f.etd - prev_ready})")
                break
            prev_ready, loc, need_mct = f.eta, f.dest, True
        if not out and self._oversold_risk(p):
            out.append(self._oversold_risk(p))
        return out

    def _oversold_risk(self, p: str) -> str | None:
        b = self.bookings[p]
        for fid in self._remaining(p):
            f = self.flights[fid]
            if f.status in ("cancelled", "departed", "arrived"):
                continue
            if self.booked(fid) > f.seats:
                # who gets offloaded: latest booking first
                on = sorted([q for q, bb in self.bookings.items() if fid in self._remaining(q)],
                            key=lambda q: (self.bookings[q].booked_seq, q))
                cap, keep = f.seats, set()
                for q in on:
                    if self.bookings[q].pax <= cap:
                        cap -= self.bookings[q].pax
                        keep.add(q)
                    else:
                        cap = -1
                if p not in keep:
                    return f"will be denied boarding on oversold {fid}"
        return None

    # ------------------------------------------------------------------ clock
    def _fire_events(self):
        for e in self.events:
            if e.id in self.fired or e.at > self.now:
                continue
            self.fired.append(e.id)
            pl = e.payload
            if e.kind == "cancel":
                for fid in pl["flights"]:
                    if self.flights[fid].status not in ("departed", "arrived"):
                        self.flights[fid].status = "cancelled"
            elif e.kind == "delay":
                f = self.flights[pl["flight"]]
                if f.status not in ("departed", "arrived", "cancelled"):
                    f.etd = f.std + pl["minutes"]
                    f.eta = f.sta + pl["minutes"]
                    f.status = "delayed"
            elif e.kind == "add_flight":
                for spec in pl["flights"]:
                    self.flights[spec["id"]] = Flight(spec["id"], spec["origin"], spec["dest"], spec["std"],
                                                      spec["std"] + spec["block"], spec["std"],
                                                      spec["std"] + spec["block"], "E190", AIRCRAFT["E190"],
                                                      tail=f"OH-R{spec['id'][-2:]}", added=True, visible_from=e.at)
            self._dirty = True
            if e.kind == "downgauge":
                f = self.flights[pl["flight"]]
                f.aircraft, f.seats = pl["aircraft"], AIRCRAFT[pl["aircraft"]]
            self.log.append(LogEntry(e.at, "event", {"id": e.id}))
            changed = set(pl.get("flights", [])) if e.kind == "cancel" else ({pl["flight"]} if e.kind in ("delay", "downgauge") else set())
            self._record_invalidated(e.id, e.kind, changed, self.now)

    def _record_invalidated(self, event: str, cause: str, changed: set[str], at: int):
        """Keep an audit of upstream failures and the dependent seats they strand."""
        if not changed:
            return
        moved = {l.data["pnr"] for l in self.log if l.kind == "rebook"}
        for p in sorted(moved):
            rem = self._remaining(p)
            hit = changed.intersection(rem)
            pr = self.problems(p, include_airborne=True) if hit else []
            if hit and pr:
                first = min(rem.index(fid) for fid in hit)
                self.log.append(LogEntry(at, "plan_invalidated", {
                    "pnr": p, "event": event, "cause": cause,
                    "invalid_flights": sorted(hit), "itinerary": list(rem),
                    "dependent_flights": rem[first + 1:],
                    "problem": pr[0]}))

    def _scan(self):
        """Record, once per tick, which bookings have problems and their best option (for the verifier)."""
        if self.ended:
            return
        seen = self.__dict__.setdefault("problem_ticks", {})
        for p in self.bookings:
            pr = self.problems(p)
            if pr:
                opt = self.options(p, limit=1)
                seen.setdefault(p, []).append((self.now, pr[0], self.flights[opt[0][-1]].eta if opt else None))

    def _land(self, t: int):
        for p, st in self.state.items():
            if st.location is None and st.ready <= t:
                st.location = st._dest  # type: ignore[attr-defined]
                b = self.bookings[p]
                if st.location == b.dest and not self._remaining(p):
                    st.arrived_at = st.ready

    def _fly_until(self, t_end: int):
        """Operate every flight whose departure falls in (now, t_end], in time order."""
        done: set[str] = set()
        while True:
            deps = [f for f in self.flights.values() if f.id not in done
                    and f.status in ("scheduled", "delayed") and self.now < f.etd <= t_end]
            if not deps:
                break
            f = min(deps, key=lambda f: (f.etd, f.id))
            done.add(f.id)
            self._land(f.etd)
            on = sorted([p for p in self.bookings
                         if self._remaining(p) and self._remaining(p)[0] == f.id],
                        key=lambda p: (self.bookings[p].booked_seq, p))
            cap = f.seats
            for p in on:
                st, b = self.state[p], self.bookings[p]
                ok_conn = st.location == f.origin and st.ready + (MCT if st.flown > 0 else 0) <= f.etd
                if not ok_conn:
                    continue
                if b.pax > cap:
                    st.offloaded = True
                    self.log.append(LogEntry(f.etd, "denied_boarding", {"pnr": p, "flight": f.id}))
                    continue
                cap -= b.pax
                st.location, st.flown = None, st.flown + 1
                st.ready = f.eta
                st._dest = f.dest  # type: ignore[attr-defined]
            f.status = "departed"
            self._dirty = True
            self._knock_on(f)
        self._land(t_end)
        for f in self.flights.values():
            if f.status == "departed" and f.eta <= t_end:
                f.status = "arrived"

    def _knock_on(self, f: Flight):
        """Once a late aircraft is airborne, its next flight is re-timed (40 min minimum turnaround)."""
        if f.carrier != "AU":
            return
        nxt = sorted([g for g in self.flights.values() if g.tail == f.tail and g.carrier == "AU"
                      and g.std > f.std and g.status in ("scheduled", "delayed")], key=lambda g: g.std)
        if not nxt:
            return
        g = nxt[0]
        need = f.eta + TURNAROUND
        if need > g.etd:
            shift = need - g.etd
            g.etd, g.eta, g.status = need, g.eta + shift, "delayed"
            self._dirty = True
            self.dyn_alerts.append({"id": f"KNOCK-{len(self.dyn_alerts) + 1:02d}", "t": f.etd,
                                    "time": hhmm(f.etd),
                                    "text": f"Knock-on delay: aircraft {g.tail} is late from {f.id}; "
                                            f"{g.id} {g.origin}-{g.dest} now departs {hhmm(g.etd)} (was {hhmm(g.std)})."})
            self._record_invalidated(self.dyn_alerts[-1]["id"], "knock_on", {g.id}, f.etd)

    def _step_to(self, t: int):
        while self.now < t:
            nxt = min(t, self.now + TICK)
            # events at exactly nxt fire after flights up to nxt operate
            self._fly_until(nxt)
            self.now = nxt
            self._fire_events()
            self._scan()

    # ------------------------------------------------------------------ agent API
    def tool(self, name: str, args: dict) -> dict:
        """Single entry point used by every front end (MCP, local runner, scripts)."""
        self.tool_calls += 1
        fn = getattr(self, f"t_{name}", None)
        if fn is None:
            self.tool_errors += 1
            return {"error": f"unknown tool {name}"}
        if self.ended and name not in ("get_status", "read_alerts", "get_booking", "get_flight", "list_flights"):
            return {"error": "shift has ended; no further actions are possible"}
        try:
            out = fn(**(args or {}))
            self.log.append(LogEntry(self.now, "tool", {"name": name, "args": args, "ok": True}))
            return out
        except (ActionError, TypeError, KeyError, ValueError) as e:
            self.tool_errors += 1
            self.log.append(LogEntry(self.now, "tool", {"name": name, "args": args, "ok": False, "error": str(e)}))
            return {"error": str(e)}

    def t_get_status(self):
        dis = [p for p in self.bookings if self.problems(p)]
        return {
            "time": hhmm(self.now), "shift_ends": hhmm(SHIFT_END), "shift_over": self.ended,
            "alerts_published": len(self.fired),
            "partner_seats_left": self.partner_left(),
            "bookings_with_problems": len(dis),
            "passengers_with_problems": sum(self.bookings[p].pax for p in dis),
        }

    def t_read_alerts(self, since: str | None = None):
        out = [{"id": e.id, "time": hhmm(e.at), "text": e.text, "_t": e.at} for e in self.events if e.id in self.fired]
        out += [{"id": a["id"], "time": a["time"], "text": a["text"], "_t": a["t"]} for a in self.dyn_alerts]
        out.sort(key=lambda a: (a["_t"], a["id"]))
        for a in out:
            a.pop("_t")
        if since:
            ids = [a["id"] for a in out]
            if since in ids:
                out = out[ids.index(since) + 1:]
        return {"now": hhmm(self.now), "alerts": out}

    def _flight_view(self, f: Flight, manifest=False):
        d = {"flight": f.id, "carrier": f.carrier, "aircraft_reg": f.tail, "from": f.origin, "to": f.dest, "dep": hhmm(f.etd), "arr": hhmm(f.eta),
             "status": f.status, "aircraft": f.aircraft, "seats": f.seats,
             "seats_free": (self._avail(f.id) if f.carrier == "AU" else "partner")
             if f.status in ("scheduled", "delayed") else 0}
        if f.etd != f.std:
            d["scheduled_dep"] = hhmm(f.std)
        if manifest:
            d["bookings"] = [{"pnr": p, "pax": self.bookings[p].pax} for p in self.bookings
                             if f.id in self._remaining(p)]
        return d

    def t_list_flights(self, origin: str | None = None, dest: str | None = None,
                       after: str | None = None, before: str | None = None):
        lo = _parse(after) if after else self.now
        hi = _parse(before) if before else SIM_END
        fl = sorted([f for f in self.flights.values() if self._visible(f)
                     and (origin is None or f.origin == origin.upper())
                     and (dest is None or f.dest == dest.upper()) and lo <= f.etd <= hi
                     and (f.carrier == "AU" or origin or dest)],
                    key=lambda f: (f.etd, f.id))
        cap = 150 if (origin or dest) else 60
        return {"now": hhmm(self.now), "flights": [self._flight_view(f) for f in fl[:cap]],
                "truncated": len(fl) > cap}

    def t_get_flight(self, flight: str):
        f = self.flights.get(flight.upper())
        if f is None or not self._visible(f):
            raise ActionError(f"no flight {flight}")
        return self._flight_view(f, manifest=True)

    def _booking_view(self, p):
        b, st = self.bookings[p], self.state[p]
        d = {"pnr": p, "name": b.name, "pax": b.pax, "tier": b.tier, "from": b.origin, "to": b.dest,
             "originally_due": hhmm(b.orig_arrival),
             "location": st.location or "airborne",
             "itinerary": [{"flight": fid, "from": self.flights[fid].origin, "to": self.flights[fid].dest,
                            "dep": hhmm(self.flights[fid].etd), "arr": hhmm(self.flights[fid].eta),
                            "status": self.flights[fid].status,
                            "flown": i < st.flown} for i, fid in enumerate(b.itinerary)]}
        if b.deadline:
            d["must_arrive_by"] = hhmm(b.deadline)
            d["deadline_reason"] = b.deadline_reason
        if st.arrived_at is not None:
            d["arrived"] = hhmm(st.arrived_at)
        pr = self.problems(p)
        if pr:
            d["problems"] = pr
        return d

    def t_get_booking(self, pnr: str):
        p = pnr.upper()
        if p not in self.bookings:
            raise ActionError(f"no booking {pnr}")
        return self._booking_view(p)

    def t_find_disrupted_bookings(self):
        rows = []
        for p in sorted(self.bookings):
            pr = self.problems(p)
            if pr:
                b, st = self.bookings[p], self.state[p]
                r = {"pnr": p, "pax": b.pax, "tier": b.tier, "at": st.location, "to": b.dest,
                     "problem": pr[0]}
                if b.deadline:
                    r["must_arrive_by"] = hhmm(b.deadline)
                rows.append(r)
        return {"now": hhmm(self.now), "count": len(rows), "bookings": rows}

    def options(self, p: str, ignore: set[str] = frozenset(), limit: int = 6, partner: bool = False,
                include_full: bool = False) -> list[list[str]]:
        """Legal itineraries from the group's current position, earliest arrival first.
        partner=False: own flights only. partner=True: itineraries using at least one partner flight."""
        b, st = self.bookings[p], self.state[p]
        if st.location is None or st.arrived_at is not None:
            return []
        own = set(self._remaining(p))
        earliest = max(self.now + CHECKIN_CUTOFF, st.ready + (MCT if st.flown > 0 else 0))

        def ok(f: Flight, t_ready: int):
            if f.id in ignore or not self._visible(f) or f.status not in ("scheduled", "delayed"):
                return False
            if f.carrier == "NL" and not partner:
                return False
            if f.etd < t_ready or f.etd > SIM_END:
                return False
            if include_full and f.carrier == "AU":
                return True
            free = self._avail(f.id) + (b.pax if f.id in own else 0)
            return free >= b.pax

        res = []
        for f in self.flights.values():
            if f.origin != st.location or not ok(f, earliest):
                continue
            if f.dest == b.dest:
                res.append([f.id])
            elif f.dest == HUB:
                for g in self.flights.values():
                    if g.origin == HUB and g.dest == b.dest and ok(g, f.eta + MCT):
                        res.append([f.id, g.id])
        if partner:
            res = [it for it in res if any(self.flights[x].carrier == "NL" for x in it)]
        res.sort(key=lambda it: (self.flights[it[-1]].eta, len(it), it))
        return res[:limit]

    def partner_used(self) -> int:
        return sum(b.pax for b in self.bookings.values()
                   if any(self.flights[x].carrier == "NL" for x in b.itinerary))

    def partner_left(self) -> int:
        return PARTNER_SEATS[self.size] - self.partner_used()

    def t_search_itineraries(self, pnrs: list[str], include_full: bool = False):
        if isinstance(pnrs, str):
            pnrs = [pnrs]
        if not pnrs or len(pnrs) > 20:
            raise ActionError("give 1 to 20 PNRs")
        out = []
        for pnr in pnrs:
            p = pnr.upper()
            if p not in self.bookings:
                out.append({"pnr": pnr, "error": "no such booking"})
                continue
            st = self.state[p]
            if st.arrived_at is not None or st.location is None:
                out.append({"pnr": p, "error": "already arrived" if st.arrived_at is not None else "airborne"})
                continue
            view = lambda it: {"flights": it, "dep": hhmm(self.flights[it[0]].etd),
                               "arr": hhmm(self.flights[it[-1]].eta),
                               "seats_free": min(self._avail(x) if self.flights[x].carrier == "AU" else 999 for x in it)}
            out.append({"pnr": p, "at": st.location, "to": self.bookings[p].dest, "pax": self.bookings[p].pax,
                        "options": [view(it) for it in self.options(p, limit=8, include_full=include_full)],
                        "partner_options": [view(it) for it in self.options(p, limit=3, partner=True)]})
        return {"now": hhmm(self.now), "partner_seats_left": self.partner_left(),
                "note": "Published schedule with current estimates and free seats. Notices about future closures are NOT applied."
                        + (" include_full: options may lack enough free seats; free them first." if include_full else ""),
                "results": out}

    def t_rebook(self, changes: list[dict]):
        if isinstance(changes, dict):
            changes = [changes]
        if not changes or len(changes) > 25:
            raise ActionError("give 1 to 25 changes")
        res = []
        for ch in changes:
            try:
                res.append(self._rebook_one(ch["pnr"], ch["flights"]))
            except (ActionError, KeyError, TypeError) as e:
                self.tool_errors += 1
                res.append({"pnr": ch.get("pnr") if isinstance(ch, dict) else None, "ok": False, "error": str(e)})
        return {"now": hhmm(self.now), "results": res}

    def _rebook_one(self, pnr: str, flights: list[str]):
        p = pnr.upper()
        if p not in self.bookings:
            raise ActionError(f"no booking {pnr}")
        b, st = self.bookings[p], self.state[p]
        if isinstance(flights, str):
            flights = [flights]
        flights = [x.upper() for x in flights]
        if st.arrived_at is not None:
            raise ActionError(f"{p} already arrived")
        if st.location is None:
            raise ActionError(f"{p} is airborne; rebook after landing")
        if not flights or len(flights) > 3:
            raise ActionError("give 1 to 3 flights")
        own = set(self._remaining(p))
        loc = st.location
        t_ready = max(self.now + CHECKIN_CUTOFF, st.ready + (MCT if st.flown > 0 else 0))
        for i, fid in enumerate(flights):
            f = self.flights.get(fid)
            if f is None or not self._visible(f):
                raise ActionError(f"no flight {fid}")
            if f.status not in ("scheduled", "delayed"):
                raise ActionError(f"{fid} is {f.status}")
            if f.origin != loc:
                raise ActionError(f"{fid} departs {f.origin}, passengers would be at {loc}")
            if f.etd < t_ready:
                raise ActionError(f"{fid} departs {hhmm(f.etd)}; earliest possible boarding is {hhmm(t_ready)}"
                                  + (" (check-in cut-off)" if i == 0 else f" (needs {MCT} min connection)"))
            free = f.seats - self.booked(fid) + (b.pax if fid in own else 0)
            if free < b.pax:
                raise ActionError(f"{fid} has {max(free, 0)} free seats, booking has {b.pax} passengers")
            loc, t_ready = f.dest, f.eta + MCT
        if loc != b.dest:
            raise ActionError(f"itinerary ends at {loc}, booking goes to {b.dest}")
        uses_nl = any(self.flights[x].carrier == "NL" for x in flights)
        had_nl = any(self.flights[x].carrier == "NL" for x in b.itinerary)
        if uses_nl and not had_nl and self.partner_left() < b.pax:
            raise ActionError(f"partner allowance: {self.partner_left()} seats left, booking has {b.pax} passengers")
        old = self._remaining(p)
        best = self.options(p, limit=1)
        had_problem = bool(self.problems(p))
        b.itinerary = b.itinerary[:st.flown] + flights
        self._dirty = True
        if old != flights:
            self.seq += 1
            b.booked_seq = self.seq
        st.offloaded = False
        self.log.append(LogEntry(self.now, "rebook", {
            "pnr": p, "old": old, "new": flights, "had_problem": had_problem,
            "eta": self.flights[flights[-1]].eta,
            "best_eta": self.flights[best[0][-1]].eta if best else None}))
        return {"pnr": p, "ok": True, "flights": flights, "arrives": hhmm(self.flights[flights[-1]].eta)}

    def t_advance_clock(self, minutes: int = 60):
        if self.now >= SHIFT_END:
            raise ActionError("shift is over; call end_shift")
        minutes = int(minutes)
        if minutes not in (30, 60):
            raise ActionError("minutes must be 30 or 60")
        before = set(self.fired)
        nd = len(self.dyn_alerts)
        self._step_to(min(SHIFT_END, self.now + minutes))
        new = [{"id": e.id, "time": hhmm(e.at), "text": e.text} for e in self.events
               if e.id in self.fired and e.id not in before]
        new += [{"id": a["id"], "time": a["time"], "text": a["text"]} for a in self.dyn_alerts[nd:]]
        denied = [l.data for l in self.log if l.kind == "denied_boarding" and self.now - minutes < l.t <= self.now]
        out = {"now": hhmm(self.now), "new_alerts": new}
        if denied:
            out["denied_boarding"] = denied
        if self.now >= SHIFT_END:
            out["note"] = "Shift time is over. Call end_shift to hand over."
        return out

    def t_end_shift(self, handover: str = ""):
        self.finish(reason="agent", handover=handover)
        return {"ok": True, "message": "Shift ended. The rest of the operation runs without the desk."}

    # ------------------------------------------------------------------ end of episode
    def finish(self, reason: str = "agent", handover: str = ""):
        if not self.ended:
            self.ended = True
            self.end_reason = reason
            self.handover = handover
            self.end_time = self.now
            self.log.append(LogEntry(self.now, "end", {"reason": reason}))
        # operate the rest of the timeline with no desk
        self._step_to(SIM_END)

    def snapshot(self) -> dict:
        """Full, serialisable record of the episode, consumed by the verifier."""
        return {
            "seed": self.seed, "size": self.size, "profile": self.profile, "now": self.now,
            "ended": self.ended, "end_reason": self.end_reason, "end_time": getattr(self, "end_time", None),
            "tool_calls": self.tool_calls, "tool_errors": self.tool_errors,
            "arrivals": {p: s.arrived_at for p, s in self.state.items()},
            "itineraries": {p: b.itinerary for p, b in self.bookings.items()},
            "log": [{"t": l.t, "kind": l.kind, **l.data} for l in self.log],
            "problem_ticks": getattr(self, "problem_ticks", {}),
        }


def _parse(s: str) -> int:
    s = s.strip()
    plus = s.startswith("+1")
    s = s.replace("+1", "").strip()
    h, m = s.split(":")
    return int(h) * 60 + int(m) + (24 * 60 if plus else 0)


def replay(seed: int, size: str, actions: list[tuple[str, dict]]) -> OpsDesk:
    env = OpsDesk(seed, size)
    for name, args in actions:
        env.tool(name, args)
    env.finish(reason=env.end_reason or "harness")
    return env
