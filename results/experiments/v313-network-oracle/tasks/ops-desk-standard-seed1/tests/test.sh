#!/bin/bash
# Asks the environment sidecar to finish the day and grade it. The token is only in the verifier's env.
set -u
mkdir -p /logs/verifier
python3 -c "import os,urllib.request; open('/logs/verifier/grade.json','wb').write(urllib.request.urlopen(urllib.request.Request('http://mcp-server:8000/grade', headers={'Authorization': 'Bearer '+os.environ['OPSDESK_GRADER_TOKEN']}), timeout=600).read())"   || echo "grade request failed" >&2
if [ ! -s /logs/verifier/grade.json ]; then
  echo 0 > /logs/verifier/reward.txt
  echo '{"reward": 0, "infra_error": 1}' > /logs/verifier/details.json
  exit 0
fi
python3 - <<'EOF'
import json
g = json.load(open("/logs/verifier/grade.json"))
r = g["report"]
json.dump(r, open("/logs/verifier/report.json", "w"), indent=1)
# reward.txt is the 0-1 task reward: share of the reference's recovery achieved, clipped to [0, 1].
# details.json keeps the raw normalised score (it can go below 0 if the desk made things worse,
# or above 1 if it beat the reference) and the failure-mode counts.
reward = min(1.0, max(0.0, r["score"]))
open("/logs/verifier/reward.txt", "w").write(f"{reward:.4f}")
out = {"reward": round(reward, 4), "raw_score": r["score"], "value": r["value"], "v_nothing": r["v_nothing"], "v_reference": r["v_reference"],
       "tool_calls": r["tool_calls"], "tool_errors": r["tool_errors"]}
for k, v in r["failure_modes"].items():
    out["fm_" + k] = v["count"]
json.dump(out, open("/logs/verifier/details.json", "w"))
print(json.dumps(out))
EOF
