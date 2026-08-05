"""The Nimbus agent definition.

`agent/agent.py` holds the ADK `Workflow` graph and wires the local
capabilities, which are the skill toolset, the stdio MCP server and the
in-process code executor. The `harness` package provides the local session
and memory services.
"""

from .agent import (
    LOCAL_SKILL_DIR,
    OPS_MCP_PATH,
    build_root_agent,
    load_history,
    resolve_code_executor,
    resolve_ops_toolset,
    resolve_skill_toolset,
    root_agent,
)
from .config import AGENT_NAME, MODEL

__all__ = [
    "build_root_agent",
    "load_history",
    "root_agent",
    "resolve_ops_toolset",
    "resolve_skill_toolset",
    "resolve_code_executor",
    "OPS_MCP_PATH",
    "LOCAL_SKILL_DIR",
    "AGENT_NAME",
    "MODEL",
]
