# Evidence ledger

Updated 14 November 2026, Helsinki. No current-world frontier/reference advantage is established.

## World and runner provenance

| Evidence | World | Runner | Interpretation |
| --- | --- | --- | --- |
| `results/calibration-logs/gemini-runs-world-v2/` | v2, before overnight-flight and priority-offload fixes | Gemini direct REST | Calibration only. Argon 1.268 exposed reference/world weaknesses. Flash 0.833/0.957/0.838 cannot prove a v3 gap. |
| `results/calibration-logs/gemini-runs-world-v3-partial/` | v3 | Interrupted REST runs | Partial transcripts, no completed score. |
| `results/calibration-logs/harbor/opencode-gemini-3.8-flash-small-seed1-interrupted/` | pre-handoff small task | Interrupted Harbor/OpenCode | No score. Does not meet required STANDARD completed-model evidence. |
| `results/standard/` | v3 at eaec534 | Chief, Python 3.11 in-process scripts | Original JSON retained; SHA256 in PROVENANCE.json. No model inference. |
| `results/standard/exploits.json` | v3 simulator, unchanged reward/reference | Codex, Python 3.11 in-process scripts | Fresh standard seeds 1–3, raw scores retained. |
| `results/harbor-runs/v3-oracle-seed1/` | v3, private grader-header transport patch | Harbor 0.26.0 / Docker | Standard seed1, reward 1.000, 49 seconds, zero exceptions. |
| `results/harbor-runs/v3-nop-seed1/` | same | Harbor 0.26.0 / Docker | Standard seed1, reward 0.000, 21 seconds, zero exceptions. |
| `results/experiments/c16-family-audit-v4/` | v3.1 supplemental profiles | In-process scripts | 48 paired checks,3 row-order changes in naive;2/3 final seeds complete, seed12 generator failure. Failed v1 retained. No frontier inference. |

v3.1 adds diagnostic invalidation records, optional family profiles and experiment provenance. Default `all` keeps v3 simulator/reward/reference behavior. The reference source remains unchanged from eaec534. The new stale-plan diagnostic does not change reward. Regenerate Harbor tasks to include the diagnostic; the first v3 Harbor logs above predate it and remain labelled accurately.

## Scores and failures

Original reference scores1/1/1, nothing0/0/0, stop-early0.0787/0.3084/0.2909 and naive0.5767/0.7335/0.5179. Reference is normalized to1 by construction. This is not evidence of optimality. The reference value at standard seed1 is2187.66 versus1992.36 doing nothing.

Naive-script reports show cascade blindness2/2/7 and priority inversion13/4/13 across seeds1/2/3. These are scripted failures, not model failures. Their overlapping losses must not be added. The stale-plan acceptance tests construct explicit upstream cancellation, delay, reduced capacity, failed repair and dependent-seat release cases. No human labels are invented.

Current exploit tests give churn−1.5265/−0.8798/−1.2894, parking tomorrow0.2440/0.3154/0.3252, and false claim/clock-only/malformed/double-count0. The public tables show raw scores, while Harbor reward.txt is clipped to[0,1]. A score above1 must be investigated and reported as a reference weakness, never hidden by clipping.

## Missing evidence and publication limits

- Complete STANDARD OpenCode model evidence now exists: gpt-4.1-mini, score0.000, zero Harbor runner exceptions, stopped at07:00 before rebooking. [Transcript-based error analysis](ERROR_ANALYSIS.md) distinguishes this scored early stop from infrastructure. Gemini Flash/Argon returned HTTP402; their fallback zeros are excluded. Stronger Router families are in progress.
- Repeated stochastic runs from2–3 model families. Different Gemini names alone are not independent model families. No judge-model guarantee is claimed.
- Current model failure examples read from completed transcripts. Interrupted transcripts may guide investigation but cannot support completed-run performance.
- [Independent spec/evidence-only AI review](INDEPENDENT_REVIEW.md) reproduced68 audit rows and12 original baselines. It found a missing knock-on diagnostic, seed12 failure, incomplete manifest inputs and unsupported egress confidentiality. Fixes require a scoped follow-up check. No human/model-family independence claim.
- Public demo recording, no longer than2:00, and final competition submission.
- Browser desktop/mobile inspection of the updated site. IAB is unavailable in this project chat; exact requests are in the bridge. Local syntax/data checks are not browser verification.

The site previously displayed old-world data and claimed a consistent frontier gap. The local correction removes that claim and exports only current scripted data until genuine model evidence is available. Deployment/browser status must be checked separately.

## Supplemental audit failures

See [AUDIT_RESULTS.md](AUDIT_RESULTS.md). The original generator rejects final seed12. The audit keeps that failure rather than swapping seeds. Three naive-script row-order perturbations changed value. All48 paired checks and the failed first audit are public.

## Independent review response

The knock-on route now has an explicit invalidation record and a fourth regression test. Early harness termination is also diagnosed. The audit manifest now includes each profile's exact seeds; v4 preserves fixed families/inputs and the seed12 failure. Transport-only packaging changes after that audit add supported agent-phase egress restrictions. Validation attempts and failures remain separate; no network isolation claim is made until phase-scoped tests pass. The reference policy and numerical reward remain unchanged.

## Current Harbor transport evidence

[Shared-loopback phase proof](../results/harbor-runs/network-proof-loopback/README.md) runs explicit outbound checks inside the actual agent phase, then the unchanged reference. GitHub and raw source are blocked with URLError; unauthenticated Router responds403, MCP health200; reference raw/reward1.000 with no verifier infrastructure flag. Latest nop raw/reward0.000 is in `results/experiments/v314-harbor-nop`. Zero Harbor exceptions is distinct from zero rejected tool requests; reference has40 rejected tools among18087 calls. The finite network proof is not a claim of exhaustive security.
