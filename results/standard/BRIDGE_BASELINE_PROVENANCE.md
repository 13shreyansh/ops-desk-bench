# Bridge baseline provenance

Run by Junction Chief of Staff at 2026-11-14 18:10 Helsinki.
Source commit: eaec534, current world v3. Python3.11 on the Mac.
Command: `python3.11 -m opsdesk.eval --size standard --seeds 1 2 3`.

| Policy | Seed1 | Seed2 | Seed3 |
|---|---:|---:|---:|
| reference |1.000|1.000|1.000|
| nothing |0.000|0.000|0.000|
| stop_early |0.079|0.308|0.291|
| naive |0.577|0.734|0.518|

The adjacent JSON files are the raw outputs. These are in-process scripted policies, not Harbor oracle/nop validation, model inference, or the required scored OpenCode run. They do not establish a frontier-agent gap. Old-world calibration is separate. No API calls or credentials were used.
