# Public video script, target 1:50

Do not record an unmeasured model-gap claim. Replace the pending-model sentence only after a complete STANDARD Harbor/OpenCode run exists, using its actual model, seed, raw score and log link.

**0:00–0:18, task.** "You run the disruption desk of a fictional Helsinki airline for one day. Flights are cancelled, connections break and seats run out. Success means passengers actually arrive. A confident handover note earns nothing."

**0:18–0:42, planning trap.** Show an alert, a rebooked connecting itinerary and its later upstream cancellation. "An accepted plan can stop being valid. The desk must replace it, including the downstream seats it reserved. Our regression test shows those seats stay occupied until the repair succeeds."

**0:42–1:04, reward.** Show recovery bars and the value formula. "The script uses the same public tools as the agent. Doing nothing is zero; matching the reference is one. We preserve the raw score when it goes below zero or above one, so a weak reference cannot hide behind the required clipped reward."

**1:04–1:28, evidence.** Open actual Harbor oracle/nop reward files, then the current model evidence state. "The real Harbor pipeline scores the reference one and nop zero. One current-world OpenCode/Harbor run completed. GPT-4.1-mini scored zero after reading options and stopping at07:00 before rebooking. Stronger-family runs remain pending. Earlier model numbers came from a world with two fixed bugs and are labelled calibration. We do not have an established frontier gap yet."

**1:28–1:50, reproduction and limit.** Show one-command experiment and family audit. "Every experiment records its source hashes and inputs. We publish exploit results, nuisance failures and the limits of the family split. Ops Desk tests whether an agent keeps repairing a changing operation, with an inspectable reward and honest evidence."

# Combined solo peer pitch, 30 seconds

"Ops Desk is my AfterQuery entry. An agent runs a fictional airline through a day of disruptions, using Harbor and MCP. It must notice when its earlier bookings become stale and release their dependent seats. Passenger arrivals determine reward. The reference and nop passed Harbor validation. One GPT-4.1-mini playthrough completed with zero reward after stopping before its plan; stronger-model evidence is still pending. The demo and public MIT repo expose the runs, failures and one-command reproduction."

# Five-minute project pitch

-0:00–0:40, show the operational problem and one cancellation.
-0:40–1:40, follow one accepted plan as a later disruption invalidates it, then show dependent seats freed by a successful repair.
-1:40–2:30, explain passenger value, do-nothing/reference anchors, raw versus clipped reward.
-2:30–3:40, open completed Harbor logs and real transcript failures when available. State missing evidence plainly.
-3:40–4:30, show the family split, nuisance audit and one published limitation.
-4:30–5:00, run the reproduction command and leave the judge on the README quick path.

Video recording/upload and final submission have not been performed. Peer review for the solo team combines projects at one table and time; use the30-second segment when space is tight.
