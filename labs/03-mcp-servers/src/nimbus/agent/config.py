"""Configuration for the Nimbus agent.

Holds the agent identity and the model name, plus the Agent Registry
coordinates used to discover the managed ops MCP server. Prompts live in
prompts.py and the ops tools live in the mcp_server/ package.
"""

import os

AGENT_NAME = "nimbus"
AGENT_DESCRIPTION = (
    "Cymbal Cloud Ops Copilot — reads service health "
    "via the ops MCP server (from Agent Registry)."
)

# The default model was verified in the lab project, but it is NOT guaranteed
# to exist in every project or region (the gemini-flash-latest alias 404s in
# some projects). GEMINI_MODEL is the escape hatch:
#   export GEMINI_MODEL=gemini-2.5-flash   (or whatever --probe-models finds)
# `python check_prereqs.py` at the repo root makes one real ~5-token call to
# prove the model works before you start. The agent never probes.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
# The Agent Registry lives in the `global` location, because MCP
# registration is not supported in the us and eu multi-regions.
REGISTRY_LOCATION = os.environ.get("REGISTRY_LOCATION", "global")
OPS_MCP_DISPLAY_NAME = os.environ.get("OPS_MCP_DISPLAY_NAME", "cymbal-ops-mcp")
