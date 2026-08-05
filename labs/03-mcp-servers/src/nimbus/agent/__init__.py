"""The Nimbus agent graph.

The MCP tools come from a Cloud Run server discovered through the Agent
Registry. `resolve_ops_toolset` builds that toolset offline from the saved
endpoint. Skills are loaded from the managed Skill Registry. Sessions, memory
and code execution run locally.
"""

from .agent import (
    DEFAULT_OPS_MCP_URL,
    OPS_MCP_URL_MARKER,
    build_root_agent,
    discover_mcp_server_name,
    load_history,
    resolve_code_executor,
    resolve_ops_toolset,
    resolve_ops_toolset_via_registry,
    root_agent,
)
from .config import AGENT_NAME, MODEL
from .skills import (
    DEFAULT_SKILL_ID,
    DEFAULT_SKILL_PATH,
    SkillAdmin,
    SkillInfo,
    resolve_skill_toolset,
)

__all__ = [
    "build_root_agent",
    "load_history",
    "root_agent",
    "resolve_ops_toolset",
    "resolve_ops_toolset_via_registry",
    "discover_mcp_server_name",
    "resolve_code_executor",
    "OPS_MCP_URL_MARKER",
    "DEFAULT_OPS_MCP_URL",
    "AGENT_NAME",
    "MODEL",
    "SkillAdmin",
    "SkillInfo",
    "resolve_skill_toolset",
    "DEFAULT_SKILL_ID",
    "DEFAULT_SKILL_PATH",
]
