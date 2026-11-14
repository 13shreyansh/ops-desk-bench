#!/bin/bash
# Oracle = the scripted reference desk, driven through the same MCP tools the agent gets.
set -e
python3 /solution/network_probe.py
python3 /solution/reference.py http://127.0.0.1:8000/mcp reference
