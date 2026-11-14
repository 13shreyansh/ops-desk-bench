#!/bin/bash
# Oracle = the scripted reference desk, driven through the same MCP tools the agent gets.
set -e
python3 /solution/reference.py http://mcp-server:8000/mcp reference
