"""Scenario generation for Ops Desk.

Everything here is a pure function of the seed: the same seed always yields the
same schedule, the same passengers and the same disruption script.
All times are integer minutes after 00:00 on day 1, hub local time.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

HUB = "HEL"
MCT = 35            # minimum connecting time at the hub, minutes
CHECKIN_CUTOFF = 20  # a rebooking must be made at least this long before departure
SHIFT_START = 6 * 60
SHIFT_END = 23 * 60
DAY2 = 24 * 60
SIM_END = DAY2 + 16 * 60  # flights after this are not simulated
TICK = 60
TURNAROUND = 40   # minimum ground time between two flights of the same aircraft
LF_DAY1, LF_DAY2 = (0.72, 0.92), (0.40, 0.65)   # target load factors
PARTNER_SEATS = {"small": 14, "standard": 20}   # passengers per day the desk may put on the partner airline
PARTNER_OUT = [8 * 60 + 15, 12 * 60 + 45, 17 * 60 + 15, 24 * 60 + 8 * 60 + 15]

# spoke code -> (block minutes, city name, daily banks served on day 1)
SPOKES = {
    "ARN": (60, "Stockholm", 6),
    "TLL": (35, "Tallinn", 5),
    "CPH": (95, "Copenhagen", 5),
    "OSL": (85, "Oslo", 4),
    "OUL": (60, "Oulu", 5),
    "RVN": (80, "Rovaniemi", 3),
    "RIX": (60, "Riga", 3),
    "FRA": (160, "Frankfurt", 3),
    "AMS": (165, "Amsterdam", 3),
    "LHR": (190, "London", 3),
}
DAY1_BANKS = [7 * 60, 9 * 60 + 30, 12 * 60, 14 * 60 + 30, 17 * 60, 19 * 60 + 30]
DAY2_BANKS = [DAY2 + 7 * 60, DAY2 + 9 * 60 + 30, DAY2 + 12 * 60]
AIRCRAFT = {"SF340": 34, "ATR42": 48, "ATR72": 70, "E190": 100}

TIER_WEIGHT = {"standard": 1.0, "gold": 1.5, "medical": 3.0, "umnr": 3.0}
DEADLINE_REASONS = [
    "cruise departure", "wedding", "hospital appointment", "job interview",
    "funeral", "exam", "contract signing", "school term start",
]


def hhmm(t: int) -> str:
    day = "" if t < DAY2 else "+1 "
    t = t % DAY2
    return f"{day}{t // 60:02d}:{t % 60:02d}"


@dataclass
class Flight:
    id: str
    origin: str
    dest: str
    std: int            # scheduled departure
    sta: int            # scheduled arrival
    etd: int            # current estimated departure
    eta: int
    aircraft: str
    seats: int
    tail: str
    status: str = "scheduled"   # scheduled | delayed | cancelled | departed | arrived
    added: bool = False         # recovery flight created mid-day
    visible_from: int = 0       # minute the flight becomes public
    carrier: str = "AU"         # AU = own airline, NL = partner (seats come from the daily partner allowance)


@dataclass
class Booking:
    pnr: str
    pax: int
    tier: str
    origin: str
    dest: str
    itinerary: list[str]          # remaining + flown flight ids, in order
    orig_arrival: int             # scheduled arrival of the original itinerary
    deadline: int | None = None
    deadline_reason: str | None = None
    name: str = ""
    booked_seq: int = 0           # ordering used when an oversold flight offloads

    @property
    def weight(self) -> float:
        return TIER_WEIGHT[self.tier] * self.pax


@dataclass
class Event:
    """A scheduled disruption. `at` is when it fires and becomes visible."""
    id: str
    at: int
    kind: str          # cancel | delay | advisory | closure_confirm | add_flight | downgauge
    text: str
    payload: dict = field(default_factory=dict)
    family: str = ""


@dataclass
class Scenario:
    seed: int
    size: str
    flights: dict[str, Flight]
    bookings: dict[str, Booking]
    events: list[Event]


FIRST = ["Aino", "Eero", "Lea", "Mikko", "Sofia", "Juho", "Emma", "Ville", "Olivia", "Leo",
         "Ella", "Onni", "Iida", "Elias", "Aada", "Noah", "Helmi", "Oliver", "Venla", "Eino",
         "Maria", "Jonas", "Clara", "Lukas", "Freja", "Oskar", "Nora", "Hugo", "Alma", "Felix"]
LAST = ["Virtanen", "Korhonen", "Nieminen", "Makinen", "Hamalainen", "Laine", "Heikkinen",
        "Koskinen", "Jarvinen", "Lehtonen", "Andersson", "Hansen", "Muller", "Smith", "Dubois",
        "Jansen", "Berg", "Nilsson", "Ozols", "Tamm", "Rossi", "Novak", "Kowalski", "Lind"]


# Whole disruption families, never random event rows, define the supplemental audit.
PROFILE_FAMILIES = {
    "development": frozenset({"technical_cancel", "rotation_delay", "closure_recovery", "inbound_delay", "late_fault", "hydraulic_delay", "atc_delay"}),
    "final": frozenset({"escalating_delay", "capacity_constraint", "next_day_cancel"}),
}


def generate(seed: int = 0, size: str = "standard", profile: str = "all") -> Scenario:
    rng = random.Random(seed * 7919 + (0 if size == "standard" else 1))
    spokes = ["ARN", "TLL", "CPH", "OSL", "OUL", "RVN", "FRA"]
    if size == "small":
        spokes = ["ARN", "TLL", "CPH", "OUL", "FRA"]

    flights: dict[str, Flight] = {}
    fno = [100]

    def mk(origin, dest, dep, block, aircraft):
        fno[0] += rng.randint(1, 3)
        fid = f"AU{fno[0]}"
        f = Flight(fid, origin, dest, dep, dep + block, dep, dep + block, aircraft,
                   AIRCRAFT[aircraft], tail="")
        flights[fid] = f
        return f

    # --- schedule: each spoke gets inbound waves before banks and outbound at banks
    for s in spokes:
        block, _, nbanks = SPOKES[s]
        nbanks = 3
        if block >= 150:
            ac = "ATR72"
        elif block <= 70:
            ac = "SF340"
        else:
            ac = "ATR42"
        # pick which day-1 banks this spoke serves, spread through the day
        idx = sorted(rng.sample(range(len(DAY1_BANKS)), nbanks))
        banks = [DAY1_BANKS[i] for i in idx] + DAY2_BANKS[: (2 if block < 150 else 1) + 1]
        for b in banks:
            arr_in = b - 50 + rng.choice([-10, -5, 0])
            mk(s, HUB, arr_in - block, block, ac)          # inbound into the bank
            mk(HUB, s, b + rng.choice([0, 5, 10]), block, ac)  # outbound from the bank

    # tail assignment, deterministic
    tails: list[list] = []  # [tail_id, location, ready]
    for f in sorted(flights.values(), key=lambda f: (f.std, f.id)):
        cand = [t for t in tails if t[1] == f.origin and t[2] <= f.std and t[3] == f.aircraft]
        if cand:
            t = min(cand, key=lambda t: t[2])
        else:
            t = [f"OH-{len(tails) + 1:03d}", f.origin, 0, f.aircraft]
            tails.append(t)
        f.tail = t[0]
        t[1], t[2] = f.dest, f.sta + TURNAROUND

    # --- demand
    bookings: dict[str, Booking] = {}
    booked = {fid: 0 for fid in flights}
    seq = [0]

    def new_pnr():
        while True:
            code = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
            if code not in bookings:
                return code

    def add(itin: list[Flight]):
        pax = rng.choices([1, 2, 3, 4], weights=[38, 30, 16, 16])[0]
        tier = rng.choices(["standard", "gold", "medical", "umnr"], weights=[78, 13, 5, 4])[0]
        if tier == "umnr":
            pax = 1
        if any(booked[f.id] + pax > f.seats * target_lf[f.id] for f in itin):
            return False
        for f in itin:
            booked[f.id] += pax
        deadline = reason = None
        if rng.random() < 0.15:
            deadline = itin[-1].sta + rng.choice([60, 90, 120, 180, 240])
            reason = rng.choice(DEADLINE_REASONS)
        seq[0] += 1
        b = Booking(new_pnr(), pax, tier, itin[0].origin, itin[-1].dest, [f.id for f in itin],
                    itin[-1].sta, deadline, reason,
                    f"{rng.choice(FIRST)} {rng.choice(LAST)}", seq[0])
        bookings[b.pnr] = b
        return True

    target_lf = {fid: (rng.uniform(*LF_DAY1) if f.std < DAY2 else rng.uniform(*LF_DAY2))
                 for fid, f in flights.items()}
    inbound = [f for f in flights.values() if f.dest == HUB and f.std < DAY2]
    outbound = [f for f in flights.values() if f.origin == HUB and f.std < DAY2]
    # connecting demand first (it is what makes the hub fragile)
    for _ in range(4000):
        fi = rng.choice(inbound)
        conns = [fo for fo in outbound if fo.dest != fi.origin and fi.sta + MCT <= fo.std <= fi.sta + 150]
        if not conns:
            continue
        fo = rng.choice(conns)
        add([fi, fo])
        if sum(booked.values()) > 0.42 * sum(f.seats * target_lf[f.id] for f in flights.values()):
            break
    # local demand fills the rest
    for f in sorted(flights.values(), key=lambda f: f.id):
        tries = 0
        while booked[f.id] < f.seats * target_lf[f.id] - 1 and tries < 200:
            tries += 1
            add([f])

    # partner airline (NordicLink): a few frequencies per spoke, effectively unlimited seats,
    # but every passenger placed on it uses the desk's daily partner allowance
    for s in spokes:
        block = SPOKES[s][0] + 10
        for i, dep in enumerate(PARTNER_OUT):
            for (o, d, t) in ((HUB, s, dep), (s, HUB, dep + block + 50)):
                fid = f"NL{3000 + len([f for f in flights.values() if f.carrier == 'NL']) * 7 + i}"
                flights[fid] = Flight(fid, o, d, t, t + block, t, t + block, "partner", 999, tail="NL",
                                      carrier="NL")

    events = _disruptions(rng, flights, spokes)
    if profile != "all":
        if profile not in PROFILE_FAMILIES:
            raise ValueError(f"unknown disruption profile {profile!r}")
        events = [e for e in events if e.family in PROFILE_FAMILIES[profile]]
    return Scenario(seed, size, flights, bookings, events)


def _disruptions(rng: random.Random, flights: dict[str, Flight], spokes: list[str]) -> list[Event]:
    """The disruption script. The shape is fixed, the targets depend on the seed."""
    ev: list[Event] = []
    day1 = sorted([f for f in flights.values() if f.std < DAY2 and f.carrier == "AU"], key=lambda f: (f.std, f.id))
    n = [0]

    def eid():
        n[0] += 1
        return f"OPS-{n[0]:02d}"

    def pick(lo, hi, pred=lambda f: True):
        for widen in (0, 45, 90, 180):
            c = [f for f in day1 if lo - widen <= f.std <= hi + widen and pred(f)]
            if c:
                return rng.choice(c)
        raise RuntimeError("scenario generation: no candidate flight")

    # 1. 07:00 aircraft technical fault: the tail's next two legs are cancelled
    f = pick(8 * 60, 10 * 60, lambda f: f.origin == HUB)
    legs = sorted([g for g in flights.values() if g.tail == f.tail and g.std >= f.std], key=lambda g: g.std)[:2]
    ev.append(Event(eid(), 7 * 60, "cancel",
                    f"Technical fault on aircraft {f.tail}. Flights {', '.join(g.id for g in legs)} are CANCELLED.",
                    {"flights": [g.id for g in legs]}))
    used = {legs[0].dest if legs[0].origin == HUB else legs[0].origin}

    def knock(f, d):
        """How many later same-day legs of this aircraft a d-minute delay on f would push back."""
        legs = sorted([g for g in day1 if g.tail == f.tail and g.std > f.std], key=lambda g: g.std)
        n, arr = 0, f.sta + d
        for g in legs:
            if arr + TURNAROUND <= g.std:
                break
            n += 1
            arr = g.sta + (arr + TURNAROUND - g.std)
        return n

    def pick_chain(lo, hi, d, pred=lambda f: True):
        c = [f for f in day1 if lo <= f.std <= hi and pred(f)]
        best = max((knock(f, d) for f in c), default=0)
        top = sorted([f for f in c if knock(f, d) == best], key=lambda f: f.id)
        return rng.choice(top) if top else pick(lo, hi, pred)

    # 2. 12:00 crew delay: it ripples through the rest of that aircraft's day
    f = pick_chain(12 * 60 + 30, 14 * 60, 150, lambda f: f.origin not in used)
    ev.append(Event(eid(), 12 * 60, "delay",
                    f"{f.id} {f.origin}-{f.dest} delayed 150 minutes (crew rest requirement), aircraft {f.tail}.",
                    {"flight": f.id, "minutes": 150}))
    used.add(f.dest if f.origin == HUB else f.origin)

    # 2b. 10:00 inbound delay that breaks connections at the hub
    f = pick_chain(10 * 60 + 30, 12 * 60, 110, lambda f: f.dest == HUB and f.origin not in used)
    ev.append(Event(eid(), 10 * 60, "delay",
                    f"{f.id} {f.origin}-{HUB} delayed 110 minutes (late inbound crew), aircraft {f.tail}.",
                    {"flight": f.id, "minutes": 110}))

    # 3. 11:00 closure notice for the busiest spoke in the afternoon; cancellations applied at 14:00
    w0, w1 = 14 * 60 + 30, 19 * 60

    def hit(ap):
        return [g.id for g in flights.values() if g.std < DAY2 and
                ((g.origin == ap and w0 <= g.std < w1) or (g.dest == ap and w0 <= g.sta < w1))]
    cands = sorted([s for s in spokes if s not in used and SPOKES[s][0] < 150], key=lambda s: (-len(hit(s)), s))
    ap = rng.choice(cands[:2])
    closed = sorted(hit(ap))
    used.add(ap)
    ev.append(Event(eid(), 11 * 60, "advisory",
                    f"NOTICE: {ap} airport will be CLOSED {hhmm(w0)}-{hhmm(w1)} (thunderstorm cell, ground stop). "
                    f"Every flight departing from or arriving at {ap} inside that window will be cancelled; "
                    f"the cancellations are applied to the schedule at 14:00.",
                    {"airport": ap, "from": w0, "to": w1}))
    ev.append(Event(eid(), 14 * 60, "cancel",
                    f"{ap} ground stop confirmed: flights {', '.join(closed)} are CANCELLED.",
                    {"flights": closed}))

    # 4. 12:00 delay that escalates to a cancellation at 13:00
    f = pick(14 * 60, 16 * 60, lambda f: f.origin == HUB and f.dest not in used and f.id not in closed)
    ev.append(Event(eid(), 12 * 60, "delay",
                    f"{f.id} {HUB}-{f.dest} delayed 45 minutes (de-icing equipment fault).",
                    {"flight": f.id, "minutes": 45}))
    ev.append(Event(eid(), 13 * 60, "cancel",
                    f"Update on {f.id}: replacement equipment unavailable, {f.id} {HUB}-{f.dest} is CANCELLED.",
                    {"flights": [f.id]}))
    used.add(f.dest)

    # 5. 15:00 recovery flights to/from the closed airport (new capacity right after the ground stop)
    block = SPOKES[ap][0]
    dep = w1 + 30
    ev.append(Event(eid(), 15 * 60, "add_flight",
                    f"Recovery flight AU900 {HUB}-{ap} added, departs {hhmm(dep)}, E190 (100 seats), "
                    f"and AU901 {ap}-{HUB} departs {hhmm(w1 + 15)}, E190 (100 seats). Both are open for rebooking now.",
                    {"flights": [
                        {"id": "AU900", "origin": HUB, "dest": ap, "std": dep, "block": block},
                        {"id": "AU901", "origin": ap, "dest": HUB, "std": w1 + 15, "block": block},
                    ]}))

    # 6. 16:00 equipment swap makes an evening flight oversold
    f = pick(17 * 60 + 30, 20 * 60, lambda f: f.aircraft in ("ATR72", "ATR42") and f.origin == HUB
             and f.dest != ap)
    small = "SF340" if f.aircraft == "ATR42" else "ATR42"
    ev.append(Event(eid(), 16 * 60, "downgauge",
                    f"Equipment swap: {f.id} {HUB}-{f.dest} ({hhmm(f.std)}) now operated by {small} "
                    f"({AIRCRAFT[small]} seats) instead of {f.aircraft}. Passengers over capacity will be denied "
                    f"boarding at departure, latest-changed bookings first.",
                    {"flight": f.id, "aircraft": small}))

    # 7. 17:00 late-day fault (coherence test)
    f = pick(18 * 60, 20 * 60, lambda f: f.origin != HUB and f.origin not in used)
    legs = sorted([g for g in flights.values() if g.tail == f.tail and g.std >= f.std and g.std < DAY2],
                  key=lambda g: g.std)[:2]
    ev.append(Event(eid(), 17 * 60, "cancel",
                    f"Bird strike inspection on {f.tail}. Flights {', '.join(g.id for g in legs)} are CANCELLED.",
                    {"flights": [g.id for g in legs]}))

    # 8. 13:00 afternoon delay with a knock-on into the evening
    f = pick_chain(13 * 60 + 30, 16 * 60, 120, lambda f: f.origin not in used and f.dest not in (ap,))
    ev.append(Event(eid(), 13 * 60, "delay",
                    f"{f.id} {f.origin}-{f.dest} delayed 120 minutes (hydraulic leak check), aircraft {f.tail}.",
                    {"flight": f.id, "minutes": 120}))

    # 8b. 18:00 delay on an inbound feeding the evening bank
    f = pick(18 * 60 + 15, 19 * 60, lambda f: f.dest == HUB and f.origin not in used)
    ev.append(Event(eid(), 18 * 60, "delay",
                    f"{f.id} {f.origin}-{HUB} delayed 80 minutes (ATC flow restriction), aircraft {f.tail}.",
                    {"flight": f.id, "minutes": 80}))

    # 9. 21:00 tomorrow's first wave loses a flight (hits people rebooked onto it earlier)
    d2 = sorted([g for g in flights.values() if DAY2 <= g.std < DAY2 + 9 * 60 and g.origin == HUB and g.carrier == "AU"],
                key=lambda g: (-sum(1 for x in closed if flights[x].dest == g.dest), g.std, g.id))
    g = d2[0]
    ev.append(Event(eid(), 21 * 60, "cancel",
                    f"Crew duty-time limit: tomorrow's {g.id} {HUB}-{g.dest} ({hhmm(g.std)}) is CANCELLED.",
                    {"flights": [g.id]}))
    families = ["technical_cancel", "rotation_delay", "inbound_delay", "closure_recovery", "closure_recovery",
                "escalating_delay", "escalating_delay", "closure_recovery", "capacity_constraint",
                "late_fault", "hydraulic_delay", "atc_delay", "next_day_cancel"]
    assert len(ev) == len(families)
    for event, family in zip(ev, families):
        event.family = family
    ev.sort(key=lambda e: (e.at, e.id))
    for i, e in enumerate(ev):  # number alerts in the order they fire
        old = e.id
        e.id = f"OPS-{i + 1:02d}"
    return ev
