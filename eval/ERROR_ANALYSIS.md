# Read-from-transcript model failures

## GPT-4.1-mini, standard seed1, first completed Router run

Original evidence: [Harbor job](../results/harbor-runs/v31-opencode-router-gpt41mini-seed1-run1/). Provider is Hostinger Router, harness Harbor0.26.0/OpenCode, raw and clipped score0.000, zero Harbor runner exceptions. The model made9 simulator tool calls with1 rejected request. It stopped at07:00, so this is a completed scored early-stop trajectory, not a completed operational day.

The OpenCode JSONL records show:

1. It reads status and alerts, checks disrupted bookings, then advances from06:00 to07:00.
2. It finds24 disrupted bookings and calls `search_itineraries` on all24 despite the20-booking limit. The simulator rejects that request. It recovers by splitting the query into20 and4.
3. Having received the options, it ends with prose describing the rebooking plan it intends to prepare. There is no successful or attempted `rebook`, no further clock advance and no `end_shift` tool call. The last step has native stop reason `stop`, not a Harbor timeout or provider error.
4. The harness then finishes the world. Passenger value1992.36 equals doing nothing; reference value2187.66. Original report identifies18 `never_handled` bookings with25.62 total reference-relative lost value in that slice. This slice does not account for all later unattended disruptions.

This is plan-without-execution, supported by actual actions and final prose. It is not evidence that a stronger frontier model shares the failure. The recovered batching error is reported separately; it did not itself terminate the run.

The original report's `stopped_early` detector misses harness-triggered endings and therefore says0. The later diagnostic fix covers any ending before23:00. The replay viewer may show the corrected diagnostic for the same9 logged actions, while the original scored Harbor report remains unchanged. Reward and passenger outcomes are identical. This discrepancy is disclosed, not silently rewritten.

## Infrastructure, excluded from model scores

- First OpenAI Router adapter attempt used a Responses API path with a chat-completions provider. OpenCode exited with `t.responses is not a function`. Its fallback reward0 is not model performance.
- Gemini3.8 Flash and Gemini4 Argon returned HTTP402 before play. The account reported depleted prepayment credits. Their fallback zeros are infrastructure, not a gap.
- Initial allowlist validation lacked Docker Buildx, then encountered Compose exposure/DNS and proxy socket limits.
- GPT-5 seed1's first stronger trajectory stopped at08:00 after rebooking, but the builder had changed its live verifier assets by regenerating the task directory. ConnectionRefused/fallback0 is excluded, and a fresh immutable rerun is required. The generator now rejects overwrites. Keep those failures as packaging evidence. They are not agent failures and do not establish oracle0 performance.

The full ledger lists all world versions. Old-world Argon1.268 and Flash0.833/0.957/0.838 remain calibration. No established current-world frontier advantage is claimed.
