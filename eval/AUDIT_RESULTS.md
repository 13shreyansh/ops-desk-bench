# C-16 family audit results

Frozen protocol: [PROTOCOL.md](PROTOCOL.md). Source hashes were unchanged throughout v2. This is scripted structural evidence, not a frontier-model result.

-48 paired development checks,3 changed score/value. All3 are naive-script schedule/manifest row-order reversals. Display-name replacement, JSON key-order reversal and equivalent alert prefixes did not change value in these scripted runs.
-Reference policy value unchanged in every paired check. This does not prove model robustness.
-Final family seeds11 and13 completed. Naive scores0.8111 and0.7915; reference1 and nothing/stop-early0 on each. No final model runs yet.
-Seed12 failed scenario generation for reference, nothing, stop-early and naive. Four failed policy trials represent one shared generator failure, not four independent scenario failures. Coverage is2/3 final seeds.
-v1 aborted at that failure without persisting prior in-memory rows. Its failed manifest is retained. v2 changes recording only, preserves fixed seeds and reports all errors.

Inspect [all reports](../results/experiments/c16-family-audit-v2/reports.json), [changed nuisance pairs](../results/experiments/c16-family-audit-v2/nuisance-failures.json), [generator errors](../results/experiments/c16-family-audit-v2/errors.json) and [manifest](../results/experiments/c16-family-audit-v2/manifest.json). The final family split was introduced after builder exposure to the combined world. No reference retuning followed the final audit.
