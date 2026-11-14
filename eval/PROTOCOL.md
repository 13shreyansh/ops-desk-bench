# Ops Desk v3.1 audit protocol

Frozen before running the supplemental family audit on 14 November 2026.

The original v3 standard world is development/calibration. Its script contains 13 alert events from nine operational storylines. Seeds 1–3 have already informed reference development. Earlier complete Flash/Argon runs belong to world v2; partial v3 runs have no score. They cannot establish a current-world model gap.

The supplemental audit holds out whole disruption families. Development includes technical cancellation, rotation delay, inbound delay, closure/recovery, late fault, hydraulic delay and ATC delay, seeds 1–3. Final includes escalating delay/cancellation, equipment capacity constraint and next-day cancellation, seeds 11–13. Paired escalation events and closure/recovery events stay together. Family membership is disjoint and defined in `opsdesk/world.py`. Initial schedules and demand remain drawn from the same generator.

This is a newly frozen structural audit. The builder has already seen these families in the original combined world. No result from it is evidence of generalization to an unseen task domain, and scripted policies are not frontier models. Do not retune the reference after inspecting final results without declaring a new experiment version and retiring this final set.

Run reference, nothing, stop-early and naive on every split. On development only, pair each policy with passenger display-name replacement, JSON argument-key reversal, schedule/manifest row reversal and an equivalent alert prefix. Preserve numerical data and constraints. Publish every changed score/value and every infrastructure failure. These nuisance checks test scripts, not model language robustness.

Stale-plan retirement is diagnostic only. A successful agent rebooking can be invalidated later by cancellation, delay or capacity reduction. Record its dependent flight reservations, then check whether a subsequent successful rebooking retired it. Failed rebooking is not retirement. The score-level failure count additionally requires final value loss relative to the reference. Categories overlap and their losses must not be summed.

Every experiment stores source SHA256, runner, UTC times, seeds and profile. Record raw normalized score even outside [0,1]; Harbor reward.txt is the clipped submission reward. Treat missing run logs, API failures, incomplete shifts and interrupted runs separately. Do not present interrupted-run replay scores as completed model evidence.

Acceptance tests must show an upstream cancellation leaving dependent seats occupied until repair, delay/capacity invalidation and failed repair leaving the plan stale. Freeze the source manifest before final execution. An independent reviewer receives this spec and public evidence paths only, with no builder conversation. It may refuse claims when evidence is absent. Reviewer provenance must state whether it is another AI, not a human or a distinct model family.

## Runner amendment before v2 audit

v1 encountered a generator failure at final seed12 and aborted without writing its in-memory earlier rows. Preserve that failed manifest. v2 changes only evidence recording so generator failures become explicit failed trials and remaining frozen seeds still run. Seeds, family membership, simulator and reference remain fixed. Final seed12 is not silently replaced by an easier seed. Its failure counts against audit coverage.

## v3 audit after independent diagnostic review

The independent reviewer reproduced a missed dynamic knock-on invalidation. v3.1.2 records those invalidations and adds a regression. It also diagnoses early harness termination as stopped-early, including the completed gpt-4.1-mini trajectory. No reward, policy, demand, seed or family change. Re-run the same frozen family audit as v3 and preserve v1/v2 evidence. Tighten Harbor agent-phase egress to explicit model/metadata/MCP hosts; setup and verifier remain separate phases. Existing public-internet model logs remain accurately labelled as pre-hardening evidence. Test the new task through real Harbor before claiming network isolation.

## Manifest correction for final v4 evidence

v3.1.3 adds explicit profile_seeds to the manifest after the independent reviewer found the generic seeds field omitted final inputs. No test input or policy changes. Preserve v3 alongside v4. The final record is v4 with development1/2/3 and final11/12/13, including the same generator failure.
