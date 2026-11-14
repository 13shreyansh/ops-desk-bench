# Ops Desk: can a frontier agent run an airline's disruption desk for one day?

**Junction 2026 · AfterQuery "Break the Agent" · team The CS Guy**

Ops Desk is a deterministic, long-horizon reinforcement-learning environment. The agent staffs the
disruption desk of a fictional regional airline (Aurora Regional, hub Helsinki) from 06:00 to 23:00.
Nine disruptions fire during the day: aircraft faults, delays that break connections, a closure notice
that comes three hours before the cancellations, an extra recovery flight, an aircraft swap that oversells
an evening flight, and a late-night cancellation of tomorrow's first wave. The agent has to keep about
1,000 bookings moving on scarce seats and protect the travellers who matter most.

<!-- RESULTS -->

## Why this setting

* **Real, valuable and verifiable.** Airline operations control is a real job. Whether a passenger
  reached their destination, and how late, is a fact, not an opinion.
* **Deterministic.** Same seed plus same actions gives the same day, byte for byte. There is no dice roll
  that punishes perfect play (the StoreBench author's advice: avoid trading and poker).
* **Dynamic and long-horizon.** The world changes under the agent all day. Early decisions constrain
  later ones (seats you give away at 08:00 are gone at 15:00), and the agent has to keep re-checking work
  it already did. This is where frontier agents degrade.
* **Every tool and fact needed to do better is available.** The scripted reference uses exactly the
  same tools and information as the agent (see "Reference" below).

## The environment

| | |
|---|---|
| Observation | Tool results only: alerts, schedule with live times and free seats, bookings, flight manifests, itinerary search |
| Actions | `rebook` (batched, validated), `advance_clock` (30 or 60 min), `end_shift`, plus read tools |
| Episode | 06:00 to 23:00 (17 to 34 clock steps), then tomorrow's flights run without the desk |
| Scale (standard) | 7 spokes, ~84 flights, ~1,100 bookings, ~2,400 passengers, ~170 bookings disrupted |
| Seeds | Any integer. The disruption script has a fixed shape; targets, timing and demand depend on the seed |

Rules the agent is told up front: 35-minute connections at HEL, a 20-minute rebooking cut-off, groups
travel together, oversold flights deny boarding to the latest-changed bookings first, alerts are
accurate, and the search tools apply the current schedule but not notices about the future.

Three mechanics make it a planning problem rather than a lookup:

* **Knock-on delays.** Each aircraft flies a rotation and needs 40 minutes on the ground. A late inbound
  pushes its next departures back, but the schedule only shows that once the late aircraft has taken off.
  A desk that trusts the displayed times rebooks people onto connections that will break.
* **A scarce partner allowance.** NordicLink has seats on its own routes, but the desk can only put
  14 to 20 passengers on it per day. Spend it all at 07:00 and there is none left for the 17:00 bird strike.
* **Seats are a shared resource.** The desk may move healthy bookings to free seats for a medical group or
  an unaccompanied minor (`search_itineraries` with `include_full: true` shows the full options), and
  every seat it gives away early is gone later.

## Reward

Each booking is worth `tier weight × passengers × on-time factor`:

* tier weights: standard 1, gold 1.5, medical 3, unaccompanied minor 3
* on-time factor: 1 when on time, falling linearly to 0 at 24 hours late
* 0 if a stated deadline (`must_arrive_by`, e.g. a cruise or a hospital appointment) is missed, or the group never arrives

```
score = (V_agent − V_do_nothing) / (V_reference − V_do_nothing)
```

So doing nothing scores exactly **0**, the reference scores **1**, and a better-than-reference desk can
score above 1. Both anchors are recomputed from the seed at grading time inside the environment; the
agent never sees them. The reward is computed from where passengers physically end up after the
simulation runs to tomorrow afternoon. Words (the handover note, chat) are never scored.

## Named failure modes (detected by code, not by an LLM)

`opsdesk/verify.py` labels every booking where the agent lost value the reference kept:

| Failure mode | What the code checks |
|---|---|
| `never_handled` | Booking had a problem while the desk was on duty, a legal option existed, and the desk never touched it |
| `cascade_blind` | Desk fixed it once, the new itinerary broke later (new alert), and it was left broken |
| `ignored_notice` | Desk rebooked someone through a flight that a closure notice already published at that time said would be cancelled |
| `procrastinated` | Desk waited, and by the time it acted the best option was 2+ hours worse |
| `worse_choice` | Desk picked an itinerary 3+ hours later than the best legal one available at that moment |
| `priority_inversion` | A medical, unaccompanied-minor or deadline group lost value while the desk gave seats on its route to lower-priority groups |
| `harmful_churn` | Desk moved a healthy booking, made it worse than leaving it alone, and the reference did not lose that value |
| `denied_boarding` | Groups offloaded from an oversold flight |
| `stopped_early` | Desk ended its shift before 23:00; lists the alerts it never saw |

`coherence` in each report shows, alert by alert, what share of the reference's recovery the agent achieved
for the bookings that alert hit. This is how the decline over the day is measured.

## Reference (the stronger run we demonstrate)

`opsdesk/reference.py` is a short scripted desk that talks to the environment only through the public tools
(it runs over MCP in the Harbor oracle, stdlib only). Every hour it:

1. reads the alerts and turns closure notices into "do not use" flights;
2. replays every aircraft rotation with the published 40-minute rule to project knock-on delays that are
   not on the schedule yet;
3. scores every booking that is broken, on a doomed or late flight, or that it moved before, by how much
   value the best legal itinerary would add under the published scoring rule, and serves the biggest gains first;
4. uses a partner seat only when it adds enough value per seat, and rations the allowance across the day;
5. for medical, minor and deadline groups still short of value, frees seats by moving healthy groups,
   only when the urgent group gains more than the moved groups lose.

It is not an oracle: it does not know future alerts, and it sees nothing the agent cannot.

## Reward integrity: what we tried against our own verifier

`python -m opsdesk.exploits` runs these attacks on seeds 1 to 3 (standard):

<!-- EXPLOITS -->

Also by design:
* The agent's container contains no simulator code; the environment runs as a separate MCP sidecar.
* The grade endpoint needs a token that only the verifier has.
* Every action is validated (seats, cut-off, connection time, route, flight status), so invalid actions change nothing.
* Early arrival is capped at full value, so nothing is gained by moving people who are already fine.
* Infrastructure failures (API errors) are recorded separately from model failures in each report.

## Run it

```bash
# scripted runs (reference, do-nothing, stop-early, naive), deterministic, ~10 s
python -m opsdesk.eval --size standard --seeds 1 2 3

# plus agent runs (Gemini via REST, needs GEMINI_API_KEY)
python -m opsdesk.eval --size standard --seeds 1 2 3 --agent gemini-4-argon --runs 1

# reward-hacking attempts
python -m opsdesk.exploits --size standard --seeds 1 2 3
```

Python 3.11+; the simulator and verifier use only the standard library. The MCP server needs `mcp==1.27.0`
and the agent runner needs `requests`.

### With Harbor (the judges' harness)

```bash
python -m opsdesk.make_harbor --seeds 1 2 3 --size standard     # writes harbor/tasks/ops-desk-standard-seed{1,2,3}
harbor run -p harbor/tasks/ops-desk-standard-seed1 -a oracle    # reference desk over MCP  -> reward 1.0
harbor run -p harbor/tasks/ops-desk-standard-seed1 -a nop       # do nothing               -> reward 0.0
harbor run -p harbor/tasks/ops-desk-standard-seed1 -a opencode -m <model>
```

Each task runs the environment as an MCP sidecar (`opsdesk`, streamable HTTP) declared in `task.toml`.
`tests/test.sh` asks the sidecar to finish the day and writes `/logs/verifier/reward.txt`: the normalised
score clipped to [0, 1] (0 = no better than doing nothing, 1 = matched or beat the reference). Next to it,
`details.json` keeps the raw score (it can be negative when the desk made things worse), value, tool calls
and one `fm_*` count per failure mode, and `report.json` holds the full per-booking report.

## Layout

```
opsdesk/world.py        scenario generator (schedule, demand, disruption script)
opsdesk/env.py          simulator and tools
opsdesk/verify.py       reward, failure modes, coherence curve
opsdesk/reference.py    scripted reference + baselines (stdlib only, also runs over MCP)
opsdesk/mcp_server.py   MCP server (one episode per process) + token-protected /grade
opsdesk/agent_gemini.py minimal tool-calling agent loop for Gemini
opsdesk/eval.py         one-command evaluation
opsdesk/exploits.py     reward-hacking attempts
opsdesk/make_harbor.py  Harbor task generator
opsdesk/export.py       data for the replay viewer (web/)
```

All code was written during Junction 2026. MIT license.
