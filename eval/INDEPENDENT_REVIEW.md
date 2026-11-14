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

## Follow-up verification, 14 November 2026

This is an appended review of the updated spec, code and named completed evidence. The original findings above remain the historical verdict on the original hashes. I inspected no ongoing stronger-model job, used no other chat or subagent, and made no implementation change. Reviewer provenance remains AI, with no human-review or distinct-model-family claim.

### Verified corrections and frozen-core scope

The knock-on omission is fixed for the reproduced case. `_record_invalidated` now runs after `_knock_on` changes the downstream times and uses the dynamic alert ID and departure time. The fourth regression asserts the missing `knock_on` record, its CONNECT dependency and subsequent successful repair releasing those seats. Running `.venv/bin/python -m unittest discover -s tests -v` passed all four methods in 0.027 seconds, including the direct delay/capacity subtests. This resolves the specific original P2 diagnostic reproduction; it is not a proof of completeness for every possible itinerary change.

The early-stop diagnostic now checks `end_time < SHIFT_END` for both agent and harness endings. I verified this against the original mini action sequence below. Its corrected count is 12 unattended later alerts; the original stored report's count of 0 remains untouched. The latest nop record similarly reports 13 unattended alerts when the harness ends at 06:00. Neither diagnostic change alters score or passenger outcomes.

The v4 manifest explicitly records `profile_seeds` as development `[1,2,3]` and final `[11,12,13]`, and records `source_unchanged: true`. This resolves the original P3 input-metadata finding for v4. It still retains four final-seed12 generator errors, 60 development rows and 8 final rows. The original coverage limitation remains. All 68 v4 rows have the same score, value, anchors and value-at-stake as their corresponding v2 rows. The same three naive row-order differences remain published.

The following current core files match the v4 manifest byte for byte:

| File | SHA256 |
| --- | --- |
| `opsdesk/env.py` | `eb532918837e953a3764c021621a6fc29ec42261cc97c597f04a4d90e3987c21` |
| `opsdesk/verify.py` | `5738fcae4dc6d18fd56ce310390d76d62c43e7b78c05c5536537c3ffc9817391` |
| `opsdesk/world.py` | `01e0b147c5ae5744180e6593768639503a5b339c66a40cf4b8081a389137d5ec` |
| `opsdesk/reference.py` | `6c24341bc6889e02753c9f371167236ba530a9bba0a6c2511d7c24a5563237e3` |

`mcp_server.py`, tools and instruction files also match v4. I compared the current simulator/verifier to the retained v3.1 oracle task copies using `diff -u`: the differences are the invalidation helper/call and the harness early-stop condition. The numerical score functions and reference are unchanged. I did not rerun all 68 trajectories again in this follow-up.

Current packaging/wrapper files differ from the v4 frozen source, as declared. The checked `make_harbor.py` hash is `7658eb73093e724fe2e080f55703047f27515975cdc99d2e0977a99f3a975842`. The checked `experiment.py` hash is `86addd87612760209395bf46c2d98f42159d027070e22f132694b2e2a0416350`. These transport/runner versions are not covered by v4's unchanged-source assertion. Both the network-proof task and latest nop task embed core source matching the above hashes, and their solution reference copies match the current reference. The v4 manifest itself hashes to `9d60ea5fe5eede2fc3ded2bcc632f4a2f6ba65ffcb28a0512044ec7a6202a126`.

### Bounded network evidence accepted

I inspected the task, probe, solve script, original oracle log, verifier details and Harbor job result under `results/harbor-runs/network-proof-loopback/`. The task declares an agent-phase host allowlist and loopback MCP. `solve.sh` uses `set -e`, runs the probe first, then the unchanged reference. The actual agent-phase oracle log records:

```json
{"agent_phase_network_probe":{"public_reference":{"network_error":"URLError"},"public_repo":{"network_error":"URLError"},"router":{"status":403},"mcp":{"status":200,"bytes":2}}}
```

The probe targets the GitHub repository, its raw reference file, Router's models endpoint and local MCP health. The job has one completed oracle trial, zero Harbor errors, raw/clipped reward 1.000, value 2187.66 and no verifier infrastructure flag. This supports the bounded statement that those two source requests failed, the request to Router produced HTTP 403, and local MCP remained usable while the reference achieved its expected outcome. The latest `results/experiments/v314-harbor-nop/` likewise has one completed trial, zero Harbor errors, no infrastructure flag and raw/clipped reward 0.000. Its wrapper `harbor_summary` agrees with the job result.

The probe records only the `URLError` class, not its underlying reason. A 403 response alone also does not authenticate which remote/proxy component produced it. I therefore do not independently attribute the failures solely to a particular firewall mechanism or approve a claim of successful authenticated Router inference from this probe. There was no unrestricted control request or exhaustive bypass test. Setup/verifier phase access, other public hosts, redirects, alternative protocols and every permitted host's capabilities are outside this finite proof. The original source-isolation finding is narrowed by this new agent-phase evidence, not erased retroactively from pre-hardening tasks.

### Original mini transcript classification verified

I parsed all 33 JSONL records in `results/harbor-runs/v31-opencode-router-gpt41mini-seed1-run1/ops-desk-standard-seed1__V42HcsJ/agent/opencode.txt`, including all text and tool inputs/outputs, and cross-checked the original grader snapshot and job configuration. Raw JSONL SHA256 is `215b08bd4e43f996efe39221ce93492ba1a6b8ae5bc8dbbaed82e1a9f2e6bc4f`.

There are exactly nine simulator tool calls. The single `advance_clock` moves to 07:00. The model observes 24 disrupted bookings, submits all 24 to a search limited to 20, receives `give 1 to 20 PNRs`, and successfully retries as batches of 20 and 4. All 24 retry results contain an own or partner option. The model then emits its proposed next steps and ends with native `step_finish.reason = "stop"`. No `rebook`, `end_shift`, second advance, timeout or provider error appears in that trajectory. The original snapshot independently records no rebook and a harness ending at minute 420.

I replayed those exact nine JSONL actions through the current core and finished with `reason='harness'`. Every final arrival and itinerary matches the original grader snapshot. Score stays 0.000, value stays 1992.36, and `never_handled` remains 18 with lost value 25.62. Only the early-stop diagnostic changes from 0 to 12. The completed Harbor job has zero runner errors and one rejected tool request; those are different measures.

`eval/ERROR_ANALYSIS.md` correctly calls this a completed scored early-stop trajectory with a recovered batching error and a plan that was never executed. It does not support a completed operational day, a stronger-model failure or a frontier/reference gap. The other infrastructure classifications listed in that document were not newly audited in this scoped follow-up, so I do not extend this transcript verification to those separate jobs.

### Wrapper/provider checks and remaining P2

The current one-command wrapper uses the real `harbor run` executable, passes model, API-key environment-variable name, concurrency and parsed native OpenCode configuration as subprocess arguments, and supplies a random transient grader token through the environment. `eval/providers/hostinger-router.json` uses `@ai-sdk/openai-compatible`, Router's `/v1` base URL and `{env:HOSTINGER_AI_ROUTER_API_KEY}`. Its SHA256 is `57e98081d40e618e21a486e7279765d442780b0cff848511dc526c7f4c2bbae6`. It contains an environment reference rather than a credential. The completed mini job used this provider/adapter pattern. Configured context/output limits are not independently measured provider limits, and I did not start new inference.

I checked `harbor run --help` for `--job-name`, `--jobs-dir`, `-k/--n-attempts`, `-n/--n-concurrent`, `--ak/--agent-kwarg` and `--api-key-name`. All wrapper flags exist. I also invoked the wrapper controller with temporary output roots and mocked only task generation/subprocess execution, feeding it synthetic Harbor result files. The complete case returned 0, an errored-trial case returned 1, and a verifier-infrastructure case returned 1. The generated arguments preserved the model, key-variable name and literal provider environment reference. No credential was printed or stored by this check.

One unresolved P2 remains in the reviewed wrapper hash. For three requested seeds, a synthetic process-exit-0 result with one completed trial, two cancelled trials and zero errored trials returns wrapper exit code 0. The success condition checks for at least one completion, errors and infrastructure flags; it does not require all expected trials to finish or inspect cancelled/pending/running counts. `harbor_summary` omits those counts. This is a reproduced controller-classification bug, not a claim that a reviewed real job had incomplete coverage. The two completed one-trial oracle/nop records above are unaffected. A wrapper success return alone cannot certify full requested coverage until this is addressed.

Exact controller reproduction run, with no Harbor launch:

```bash
.venv/bin/python - <<'PY'
import json, tempfile, sys
from pathlib import Path
from unittest.mock import patch
from opsdesk import experiment, make_harbor
provider=Path('eval/providers/hostinger-router.json').resolve()
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    def build(seeds,size,out,timeout):
        for s in seeds:
            (out/f'ops-desk-standard-seed{s}').mkdir(parents=True)
    def run(args,env):
        job=root/'results/experiments/wrapper-check/jobs/run'
        job.mkdir(parents=True)
        stats={'n_completed_trials':1,'n_errored_trials':0,
               'n_cancelled_trials':2,'n_running_trials':0,'n_pending_trials':0}
        (job/'result.json').write_text(json.dumps({'stats':stats}))
        d=job/'trial/verifier'; d.mkdir(parents=True)
        (d/'details.json').write_text(json.dumps({'infra_error':0}))
        return 0
    argv=['experiment','--suite','harbor','--name','wrapper-check',
          '--agent','opencode','--model','hostinger/gpt-5',
          '--opencode-config',str(provider),'--api-key-name',
          'HOSTINGER_AI_ROUTER_API_KEY','--seeds','1','2','3','--runs','1']
    with patch.object(experiment,'ROOT',root), \
         patch.object(make_harbor,'build',build), \
         patch.object(experiment.subprocess,'call',run), \
         patch.object(sys,'argv',argv):
        rc=experiment.main()
    m=json.loads((root/'results/experiments/wrapper-check/manifest.json').read_text())
    print(rc,m['harbor_summary'])
PY
```

The same controller case was actually executed as part of a four-case loop. Its observed result was `0` with `completed_trials: 1`, `errored_trials: 0`, `verifier_infrastructure_failures: 0`, `process_exit_code: 0`. No existing evidence was overwritten. Any later wrapper fix requires a separate verification rather than changing this reviewed hash's verdict.

### Additional follow-up, 14 November 2026: wrapper fixed, airborne case remains

I inspected the subsequently supplied v3.1.5 wrapper and `tests/test_experiment_outcome.py`. The wrapper SHA256 is `6a1dbf460b6132cf27ba83a2fcc6578d7a6121e2b37301aaa797cd47bd0caac7`. Its `harbor_outcome` now requires completed trials to equal the requested count, rejects any errored/cancelled/running/pending trial, propagates infrastructure/process failures, and records expected and actual counts. `main` passes `len(a.seeds) * a.runs` as the expected total.

I reran `.venv/bin/python -m unittest discover -s tests -v`. All six methods passed, including the outcome subtests for partial/missing/cancelled/pending/running/errored results, verifier infrastructure and nonzero process exit. I also invoked `harbor_outcome({'n_completed_trials':1,'n_cancelled_trials':2},0,0,3)` and reran the exact mocked-controller snippet printed above by extracting that code block from this report. Both now return wrapper outcome 1 with completed 1, cancelled 2 and expected 3. This resolves the specific wrapper P2 for the new hash. It does not retroactively change the earlier wrapper version or amount to a new real Harbor/inference run. The four core hashes still match v4.

A further P2 diagnostic omission remains in that unchanged core. `_record_invalidated` requires `self.problems(p)` at event time, but `problems` returns an empty list while a passenger is airborne. Cancelling the accepted onward connection during the feeder flight creates no invalidation record. Once the passenger lands, the regular scan finds the cancelled connection but does not create the omitted record. The CONNECT reservation remains occupied. This is a diagnostic reproduction, not a completed score-level loss test, and does not affect the numerical reward.

Exact reproduction run:

```bash
.venv/bin/python - <<'PY'
import sys
sys.path.insert(0,'tests')
from test_plan_retirement import desk
from opsdesk.world import Event
from opsdesk.verify import stale_plan_records

e=desk('cancel')
e.events=[];e.fired=[];e.dyn_alerts=[]
e.log=[l for l in e.log if l.kind=='rebook']
f=e.flights['FEED'];f.status='scheduled';f.etd=f.std;f.eta=f.sta
e.events=[Event('AIRBORNE-CHANGE',480,'cancel','CONNECT cancelled while feeder is airborne.',{'flights':['CONNECT']})]
e.tool('advance_clock',{'minutes':60})
print('at480','location',e.state['TEST01'].location,'remaining',e._remaining('TEST01'),'stale_records',stale_plan_records(e))
e.tool('advance_clock',{'minutes':60})
print('at540','location',e.state['TEST01'].location,'problems',e.problems('TEST01'),'CONNECT_seats',e.booked('CONNECT'),'stale_records',stale_plan_records(e))
PY
```

Observed output:

```text
at480 location None remaining ['CONNECT'] stale_records []
at540 location HEL problems ['CONNECT cancelled'] CONNECT_seats 40 stale_records []
```

Evidence: the reviewed v4 `opsdesk/env.py::problems`, `_record_invalidated` and `_scan`, plus the fixture in `tests/test_plan_retirement.py`. The earlier knock-on fix remains verified for its specific regression. Comprehensive invalidation coverage remains unsupported. The final-seed12 coverage failure, finite network-proof limits and absence of a demonstrated frontier-model gap also remain.

### Final narrow follow-up, 14 November 2026: airborne finding fixed

I inspected the optional `include_airborne=False` argument added to `OpsDesk.problems`, the diagnostic call using `include_airborne=True`, the new airborne cancellation/downgauge regression and the completed `results/experiments/c16-family-audit-v5/` evidence. This changes the diagnostic prediction path. The default path still defers airborne problems until landing. A search with `rg -n include_airborne opsdesk` found only the argument, its conditional and the diagnostic call; public tools do not enable it.

I reran the exact airborne reproduction printed above by extracting its unchanged shell block from this report. It now records one unretired cancellation invalidation at minute 480 while the passenger is airborne, and retains that record after landing at minute 540. The record names CONNECT as the invalid flight, has an empty dependent suffix because CONNECT is the final leg, and records `CONNECT cancelled`. CONNECT still has 40 booked seats before repair, as expected.

I separately checked both cancellation and downgauge at minute 480. Default `problems('TEST01')` still returns `[]`; the explicit diagnostic path returns `['CONNECT cancelled']` or `['will be denied boarding on oversold CONNECT']`. Calling the optional path leaves the snapshot unchanged. `get_booking` omits airborne problems and `find_disrupted_bookings` omits this airborne booking, preserving their previous behavior. The new parameterized regression also verifies landing, a successful HELNEW repair, record retirement and CONNECT reservations falling from 40 to 20.

Running `.venv/bin/python -m unittest discover -s tests -v` passed all seven methods in 0.040 seconds. The specific airborne P2 is resolved for this reviewed version. The historical reproductions above remain valid findings against their stated prior hashes; this result does not claim exhaustive coverage of every disruption mechanism.

The v5 manifest records version `opsdesk-v3.1.6`, `source_unchanged: true`, development seeds `[1,2,3]`, final seeds `[11,12,13]` and the same four final-seed12 generator errors. Its SHA256 is `92a2fd626b24ae99ee120d8aa678f832932ac9fb7a8d489cf7cc30248599955b`. Current core hashes match its manifest:

| File | Verified SHA256 |
| --- | --- |
| `opsdesk/env.py` | `ea380a6a1a89b44cf09529f741fc1b4aaaf123027120e4e15047ec312d794cdb` |
| `opsdesk/world.py` | `01e0b147c5ae5744180e6593768639503a5b339c66a40cf4b8081a389137d5ec` |
| `opsdesk/verify.py` | `5738fcae4dc6d18fd56ce310390d76d62c43e7b78c05c5536537c3ffc9817391` |
| `opsdesk/reference.py` | `6c24341bc6889e02753c9f371167236ba530a9bba0a6c2511d7c24a5563237e3` |

World, verifier and reference hashes are unchanged from v4. Comparing the retained v4 simulator task copy to current `env.py` showed only this optional prediction path and its diagnostic use. All 68 v5 rows match v4 on seed, profile, policy, nuisance, score, value, both anchors and value-at-stake. I checked this directly from both report files rather than rerunning all 68 trajectories. The full current source-map comparison found only `opsdesk/export.py` differing from v5; that exporter change is outside this narrow review. Thus the manifest's in-run unchanged-source assertion is distinguished from a claim that every current file still matches the frozen experiment.

No implementation code, stored prior evidence or previous review section was changed during this verification, and no other model job was inspected. No new broad security or model-performance claim follows. The disclosed seed12 coverage failure and previously stated network/model-evidence limits remain.
