"""Generate Harbor tasks (one per seed) under harbor/tasks/.

    python -m opsdesk.make_harbor --seeds 1 2 3 --size standard

Each task runs the environment as an MCP sidecar. The agent container contains no
simulator code; the verifier asks the sidecar for the grade with a secret token
that only the verifier knows.
"""
from __future__ import annotations

import argparse
import secrets
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "opsdesk"

TASK_TOML = """version = "1.0"

[metadata]
author_name = "The CS Guy (Junction 2026)"
difficulty = "hard"
category = "agentic-operations"
tags = ["mcp", "long-horizon", "dynamic", "airline-ops"]

[agent]
timeout_sec = {agent_timeout}

[verifier]
timeout_sec = 900.0
env = {{ OPSDESK_GRADER_TOKEN = "{token}" }}

[environment]
build_timeout_sec = 900.0
cpus = 1
memory_mb = 2048
allow_internet = true

[[environment.mcp_servers]]
name = "opsdesk"
transport = "streamable-http"
url = "http://mcp-server:8000/mcp"
"""

COMPOSE = """services:
  main:
    depends_on:
      mcp-server:
        condition: service_healthy
  mcp-server:
    build:
      context: ./mcp-server
    environment:
      OPSDESK_SEED: "{seed}"
      OPSDESK_SIZE: "{size}"
      OPSDESK_GRADER_TOKEN: "{token}"
    expose:
      - "8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"]
      interval: 2s
      timeout: 5s
      retries: 30
      start_period: 5s
"""

MAIN_DOCKERFILE = """FROM python:3.12-slim
WORKDIR /app
"""

SERVER_DOCKERFILE = """FROM python:3.12-slim
{dev_ca}RUN pip install --no-cache-dir "mcp==1.27.0"
WORKDIR /srv
COPY opsdesk /srv/opsdesk
ENV PORT=8000
CMD ["python", "-m", "opsdesk.mcp_server", "streamable-http"]
"""

TEST_SH = """#!/bin/bash
# Asks the environment sidecar to finish the day and grade it. The token is only in the verifier's env.
set -u
mkdir -p /logs/verifier
python3 -c "import os,urllib.request; open('/logs/verifier/grade.json','wb').write(urllib.request.urlopen('http://mcp-server:8000/grade?token='+os.environ['OPSDESK_GRADER_TOKEN'], timeout=600).read())" \
  || echo "grade request failed" >&2
if [ ! -s /logs/verifier/grade.json ]; then
  echo '{"reward": 0, "infra_error": 1}' > /logs/verifier/reward.json
  exit 0
fi
python3 - <<'EOF'
import json
g = json.load(open("/logs/verifier/grade.json"))
r = g["report"]
json.dump(r, open("/logs/verifier/report.json", "w"), indent=1)
out = {"reward": r["score"], "value": r["value"], "v_nothing": r["v_nothing"], "v_reference": r["v_reference"],
       "tool_calls": r["tool_calls"], "tool_errors": r["tool_errors"]}
for k, v in r["failure_modes"].items():
    out["fm_" + k] = v["count"]
json.dump(out, open("/logs/verifier/reward.json", "w"))
print(json.dumps(out))
EOF
"""

SOLVE_SH = """#!/bin/bash
# Oracle = the scripted reference desk, driven through the same MCP tools the agent gets.
set -e
python3 /solution/reference.py http://mcp-server:8000/mcp reference
"""

INSTR_HEAD = """The disruption-desk tools are on the MCP server named `opsdesk` (http://mcp-server:8000/mcp).
Use only those tools to do the job below.

"""


def build(seeds: list[int], size: str, out: Path, agent_timeout: int, dev_ca: str | None = None):
    out.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        d = out / f"ops-desk-{size}-seed{seed}"
        if d.exists():
            shutil.rmtree(d)
        token = secrets.token_hex(16)
        (d / "environment" / "mcp-server").mkdir(parents=True)
        (d / "tests").mkdir()
        (d / "solution").mkdir()
        (d / "task.toml").write_text(TASK_TOML.format(token=token, agent_timeout=agent_timeout))
        (d / "instruction.md").write_text(INSTR_HEAD + (PKG / "instruction.md").read_text())
        (d / "environment" / "Dockerfile").write_text(MAIN_DOCKERFILE)
        (d / "environment" / "docker-compose.yaml").write_text(COMPOSE.format(seed=seed, size=size, token=token))
        ca = ""
        if dev_ca:  # only for building behind a TLS-intercepting proxy; never used for the submitted tasks
            shutil.copy(dev_ca, d / "environment" / "mcp-server" / "dev-ca.crt")
            ca = "COPY dev-ca.crt /dev-ca.crt\nENV PIP_CERT=/dev-ca.crt\n"
        (d / "environment" / "mcp-server" / "Dockerfile").write_text(SERVER_DOCKERFILE.format(dev_ca=ca))
        shutil.copytree(PKG, d / "environment" / "mcp-server" / "opsdesk",
                        ignore=shutil.ignore_patterns("__pycache__", "make_harbor.py", "agent_gemini.py"))
        (d / "tests" / "test.sh").write_text(TEST_SH)
        (d / "solution" / "solve.sh").write_text(SOLVE_SH)
        shutil.copy(PKG / "reference.py", d / "solution" / "reference.py")
        for f in (d / "tests" / "test.sh", d / "solution" / "solve.sh"):
            f.chmod(0o755)
        print("wrote", d)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--size", default="standard")
    ap.add_argument("--out", default=str(ROOT / "harbor" / "tasks"))
    ap.add_argument("--agent-timeout", type=int, default=10800)
    ap.add_argument("--dev-ca", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()
    build(a.seeds, a.size, Path(a.out), a.agent_timeout, a.dev_ca)
