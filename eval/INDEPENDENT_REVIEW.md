# Independent evidence review

Reviewed 14 November 2026. I am a fresh-context AI reviewer, not a human reviewer. I received the protocol, claims and specified evidence paths without the builder's prior conversation. I did not use other chats or subagents. This does not establish independence between model families. I used the plain-writing skill when preparing this report.

This verdict concerns the original v3.1.1 evidence and source hashes below. Later implementation fixes, new audit versions and later model runs are unverified by this review. I did not change implementation code or inspect ongoing current-world model runs.

## Verdict

Approve the following scoped claims:

- The supplemental development/final profiles have disjoint, whole disruption families. Paired escalation events remain together, as do closure, cancellation and recovery events. Schedules and demand are identical across profiles for the same successfully generated seed.
- The 68 retained v2 audit reports reproduce exactly, including all 48 development nuisance variants. The audit completed 60 development rows and 8 final rows. Final seed12 failed before simulation for all four policies. Final coverage is two of three seeds and eight of twelve intended policy trials.
- All 12 original standard scripted baseline rows reproduce on their numerical reward/value fields. Their recorded file hashes match `results/standard/PROVENANCE.json`. The reference source matches commit `eaec534`.
- The three acceptance test methods pass. They establish direct-event cancellation, delay and capacity invalidation, successful replacement releasing dependent seats, and failed replacement leaving the prior plan stale.
- The original Harbor oracle and nop records each contain one completed trial and zero Harbor errors. Rewards are 1 and 0. The completed v3.1 Harbor oracle also has reward 1 and zero Harbor errors. These are scripted/container checks, not frontier-agent performance.
- Raw scores remain visible separately from clipped Harbor reward. Local endpoint checks reject absent and incorrect grading tokens and accept the correct token. Generated agent-image instructions do not copy simulator/reference source or inject the grader token into the main service.

Do not approve a current-world model/reference gap, reference optimality, unseen-domain or unseen-family model generalization, model-language robustness, complete final-seed coverage, comprehensive stale-plan detection, or source confidentiality against internet retrieval. No reviewed result establishes those claims.

## Findings

### P2: knock-on delays bypass the stale-plan diagnostic

`opsdesk/env.py` records `plan_invalidated` only in `_fire_events`. `_knock_on` changes a downstream flight's times and publishes a dynamic alert without recording invalidated plans. `stale_plan_records` reads only those records. An accepted itinerary can therefore become infeasible through a published rotation delay while retaining dependent reservations and producing no stale-plan diagnostic.

I reproduced this using the acceptance fixture. After restoring its accepted FEED/CONNECT plan and replacing the direct cancellation with a consistent 30-minute upstream delay, FEED moves to departure 530 and arrival 590. CONNECT departs at 600, leaving 10 minutes instead of the required 35. A knock-on alert exists, CONNECT still has 40 booked seats, and `stale_plan_records` is empty. This reproduction tests diagnostic omission, not a completed score-level value-loss case. The score-level label necessarily cannot count an omitted record, even if a completed case later satisfies its loss threshold.

Evidence: `opsdesk/env.py::_fire_events`, `opsdesk/env.py::_knock_on`, `opsdesk/verify.py::stale_plan_records`, `tests/test_plan_retirement.py`. The direct-event acceptance tests pass but do not cover this route. Any later fix needs new evidence; it is not approved here.

Exact reproduction run:

```bash
.venv/bin/python - <<'PY'
import sys
sys.path.insert(0,'tests')
from test_plan_retirement import desk
from opsdesk.world import Flight
from opsdesk.verify import stale_plan_records

e=desk('cancel')
e.events=[]; e.fired=[]; e.dyn_alerts=[]
e.log=[l for l in e.log if l.kind not in ['event','plan_invalidated']]
f=e.flights['FEED']; f.status='scheduled'; f.etd=f.std; f.eta=f.sta
# Same 60-minute block time, with a 30-minute upstream departure/arrival delay.
up=Flight('UP','CPH','ARN',400,460,430,490,'E190',100,f.tail)
e.flights['UP']=up
e.now=420
e._fly_until(440); e.now=440; e._scan()
print('rotation_delay_repro','up_status',up.status,'feed_etd',f.etd,'feed_eta',f.eta,'problems',e.problems('TEST01'),'knock_on_alerts',len(e.dyn_alerts),'stale_records',stale_plan_records(e),'dependent_seats',e.booked('CONNECT'))
PY
```

Observed output:

```text
rotation_delay_repro up_status departed feed_etd 530 feed_eta 590 problems ['misconnect onto CONNECT (needs 35 min, has 10)'] knock_on_alerts 1 stale_records [] dependent_seats 40
```

### P2: seed12 is a real coverage failure

`generate(12, profile=...)` raises `RuntimeError: scenario generation: no candidate flight` for `all`, `development` and `final`. The final seed is not replaced. The v1 failed manifest explicitly retains the abort and lost in-memory rows; v2 contains four explicit final-seed12 errors and the surviving rows. This is honest failure recording, but it does not satisfy complete execution of the frozen three-seed final set. README's unrestricted "Any integer" seed claim is also false for the reviewed generator.

Evidence: `opsdesk/world.py::_disruptions`, `results/experiments/c16-family-audit-v1/manifest.json`, `results/experiments/c16-family-audit-v2/errors.json`, `results/experiments/c16-family-audit-v2/reports.json`, `README.md`.

### P2 limitation: filesystem isolation does not establish egress isolation

The generated main image contains only the base Python image and working-directory declaration. Simulator/reference source is copied into the sidecar, while the oracle solution receives its reference separately. The grader token is an environment placeholder, supplied to the sidecar and verifier rather than the main service. This supports the filesystem/injection design claim.

However, generated `task.toml` has `allow_internet = true`. Local `git remote -v` identifies `https://github.com/13shreyansh/ops-desk-bench.git`. If simulator/reference files are publicly readable there, an internet-enabled agent could retrieve them without breaking container filesystem isolation. No reviewed task configuration establishes an egress restriction that prevents this.

I attempted to verify unauthenticated GitHub access using the required Codex in-app browser, with `cua.createBrowserTab("iab", "https://github.com/13shreyansh/ops-desk-bench", {visible: false})`. The tool returned `Browser is not available: iab`. I did not use another browser or an HTTP fallback. Live public source accessibility is therefore unverified by me, and I do not claim a demonstrated retrieval exploit or a token leak. Source confidentiality remains unsupported.

Evidence: `opsdesk/make_harbor.py`, `results/experiments/v31-harbor-oracle/tasks/ops-desk-standard-seed1/environment/Dockerfile`, its `docker-compose.yaml`, and its `task.toml`.

### P3: audit manifest's seed field omits the final inputs

The v2 audit manifest records `seeds: [1,2,3]`, but the audit runner independently hardcodes development 1/2/3 and final 11/12/13. Its `--seeds` argument does not select audit seeds. Reports, errors and the protocol together recover the actual inputs, so this does not conceal the seed12 failure. The manifest alone is an incomplete experiment-input record.

Evidence: `opsdesk/experiment.py::main`, `results/experiments/c16-family-audit-v2/manifest.json`.

## Nuisance and reward results

All reference, nothing and stop-early nuisance rows preserve recorded score and value. Naive name/key-order/prefix variants also preserve them. All three naive row reversals change the result, and every change is present in the published reports:

| Development seed | Original naive score/value | Row-reversed score/value |
| --- | --- | --- |
| 1 | 0.5881 / 2165.79 | 0.6470 / 2175.24 |
| 2 | 0.7092 / 2171.72 | 0.7400 / 2175.45 |
| 3 | 0.5978 / 2079.95 | 0.5954 / 2079.46 |

These are script checks. The transformations replace display names, reverse top-level argument-key order, reverse returned schedule/booking row lists, and prepend an alert prefix. They do not test free paraphrases, changed numerical constraints, recursively reordered JSON, or frontier model robustness. A blanket claim that every policy is nuisance-invariant would be false.

I executed the generated verifier's Python grading block on synthetic raw scores -1.5265 and 1.25. It wrote rewards 0.0000 and 1.0000, while both `details.json` and `report.json` retained the raw inputs. The above-one input is a clipping check, not evidence that a policy achieved 1.25. Current standard exploit JSON preserves negative churn scores. No claim of exhaustively secure reward handling follows from this finite attack set.

The Harbor oracle reports `tool_errors: 40` and `tool_calls: 18087`. "Zero exceptions" is supported only as zero recorded Harbor runner exceptions, not zero rejected tool actions. The old Harbor records predate the new diagnostic; only the v3.1 oracle details include `fm_stale_plan_retirement`.

## Provenance and checks actually performed

All task shell checks ran in `/Users/shreyansh/Documents/ChatGPT/Junction/afterquery` using its Python 3.11 virtual environment. I also read the required local plain-writing skill. I read `eval/PROTOCOL.md` first, then `README.md` and `eval/LEDGER.md`; inspected the named tests, source files, manifests, scripted JSON and completed Harbor evidence. I did not read the bridge, handoff, builder conversation or calibration model transcripts.

The following reviewed source hashes matched the v2 manifest and the then-current files. v1/v2 manifest source maps differed only for `opsdesk/experiment.py`; the v2 map had no mismatch with current source at the time of the check.

| File | Reviewed SHA256 |
| --- | --- |
| `opsdesk/env.py` | `0af9f2c29a53eb86d4a17cc134c15ce314a2d9d3dc4fc2dff5816af526d210be` |
| `opsdesk/verify.py` | `213e9d3dbf891cbd2dc8f5968dd1040b1826e0174f85e0e1b30cb14997ba04dc` |
| `opsdesk/world.py` | `01e0b147c5ae5744180e6593768639503a5b339c66a40cf4b8081a389137d5ec` |
| `opsdesk/reference.py` | `6c24341bc6889e02753c9f371167236ba530a9bba0a6c2511d7c24a5563237e3` |
| `opsdesk/experiment.py` | `21004e39b366dd519efce6da0b79591df93a4221f865c71c82314e63df1a6149` |
| `opsdesk/make_harbor.py` | `d65193deed6e26a160e1b4371906bf92d3704acbd0654f3bbbe9b44e92e22576` |
| `opsdesk/mcp_server.py` | `07fbf5d55891c879d85c3c34f13078648994f8f1d1d8369ac9b23dc68913c97e` |

Hash equality supports source/file consistency, not independent attestation of who ran a historical job or its clock timestamps. The standard provenance's Chief attribution is recorded provenance, not an identity assertion I independently proved. The original and v3.1 Harbor outputs contain normal Harbor result/config/lock files, verifier artifacts and oracle logs. I did not launch a new Docker/Harbor run.

Commands/checks run, with their actual outcomes:

```bash
.venv/bin/python -m unittest discover -s tests -v
# 3 methods passed, including delay and downgauge subtests.
git diff eaec534 -- opsdesk/env.py opsdesk/world.py opsdesk/verify.py opsdesk/reference.py
# Default-all generator/reward/reference behavior unchanged; profile metadata and diagnostics added.
git remote -v
# origin https://github.com/13shreyansh/ops-desk-bench.git
```

The hash/JSON check used `hashlib.sha256(Path(f).read_bytes()).hexdigest()` for every entry of `results/standard/PROVENANCE.json['sha256']` and both audit manifest source maps. It compared the reference to `hashlib.sha256(subprocess.check_output(['git','show','eaec534:opsdesk/reference.py'])).hexdigest()`. Standard hashes, current v2 source hashes and reference commit comparison all matched. It also read `result.json` and every `*/verifier/details.json` under the two specified old Harbor directories and `results/experiments/v31-harbor-oracle/jobs/run`, confirming the results summarized above.

The exact replay loop used for all retained audit rows was:

```python
rows=json.loads(Path('results/experiments/c16-family-audit-v2/reports.json').read_text())
mismatches=[]
for i,row in enumerate(rows):
    got=scripted(row['policy'],row['seed'],row['profile'],row['nuisance'])
    expected={k:row[k] for k in got}
    if got!=expected:
        mismatches.append((i,row['profile'],row['seed'],row['policy'],row['nuisance']))
# 68 rows, mismatches=[]
```

The same Python invocation generated every combination of seeds 1/2/3/11/12/13 and profiles `all`/`development`/`final`, checked family membership, and asserted `s.flights==generate(seed,profile='all').flights` and equivalent booking equality for successful generations. Family-set intersection was empty. Seed12 failed in all profiles; all other combinations passed. Development contains 9 event rows and final 4; the original all profile contains 13.

For standard baseline replays I invoked `scripted(policy,row['seed'])` for each row of `results/standard/{reference,nothing,stop_early,naive}.json`, asserting equality of `score`, `value`, `v_nothing`, `v_reference` and `value_at_stake`. All 12 passed.

For clipping I extracted the Python heredoc from `opsdesk.make_harbor.TEST_SH`, replaced `/logs/verifier` with a temporary directory, wrote synthetic grade JSON, and executed that same block. Both boundary checks passed without changing stored evidence.

For endpoint isolation I set an ephemeral random `OPSDESK_GRADER_TOKEN` in a fresh Python process, imported `opsdesk.mcp_server`, and used `starlette.testclient.TestClient(mcp_server.mcp.streamable_http_app())`. `GET /grade` without a token returned 403, a wrong bearer token returned 403, and the correct bearer token returned 200 with do-nothing score 0. `asyncio.run(mcp_server.mcp.list_tools())` listed the 10 documented operation tools and no grading tool. Starlette/httpx deprecation and Pydantic annotation warnings appeared, but requests completed. No credential was printed or persisted. This local route test does not establish a complete hostile-container security audit.
