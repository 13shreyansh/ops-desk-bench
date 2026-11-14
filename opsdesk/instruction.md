# Ops Desk: you are the disruption desk for Aurora Regional

It is 06:00 at Aurora Regional's hub, Helsinki (HEL). You run the disruption desk until 23:00.
During the day, alerts arrive: technical faults, delays, closure notices, extra flights and aircraft swaps.
Your job is to get as many passengers as possible to their final destination, as early as possible.

You act only through the `opsdesk` MCP tools. Time does not move on its own: it moves only when you call
`advance_clock` (30 or 60 minutes). When you are done, call `end_shift`. If you stop before 23:00, every
remaining hour runs with no desk, and later disruptions go unhandled. Tomorrow's flights (marked `+1`) still
operate after your shift, so you can book people onto them.

## How you are scored
Each booking (a group travelling together) is worth `tier weight x passengers x on-time factor`:
- Tier weights: standard 1, gold 1.5, medical 3, unaccompanied minor (umnr) 3.
- On-time factor: 1 if the group arrives no later than originally due, then it falls linearly to 0 at 24 hours late.
- A booking with `must_arrive_by` is worth 0 if it arrives after that time. A booking that never arrives is worth 0.

Your score compares your result with doing nothing (score 0) and with a strong reference desk (score 1).
Only where passengers actually end up counts. What you say in messages or the handover is not scored.

## Rules of the world
- All times are HEL time. Minimum connection at HEL is 35 minutes. A booking can only be changed at least
  20 minutes before the new first flight departs, and not while the group is in the air.
- Seats are limited; a group of N passengers needs N free seats on every flight of its itinerary.
- If a flight is oversold at departure, the latest-changed bookings are denied boarding first.
- `find_disrupted_bookings` and `search_itineraries` work on the current schedule. They do not apply notices
  about things that will happen later; reading the alerts and acting on them is your job.
- Alerts are accurate: a notice says exactly what will happen.
