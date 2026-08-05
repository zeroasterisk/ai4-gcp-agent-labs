"""The Nimbus agent graph.

Skills are loaded from the managed Skill Registry. The rest of the stack,
meaning the MCP server, sessions, memory and code execution, runs locally.
"""

from .agent import (
    OPS_MCP_PATH,
    build_root_agent,
    load_history,
    resolve_code_executor,
    resolve_ops_toolset,
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
    "resolve_code_executor",
    "OPS_MCP_PATH",
    "AGENT_NAME",
    "MODEL",
    "SkillAdmin",
    "SkillInfo",
    "resolve_skill_toolset",
    "DEFAULT_SKILL_ID",
    "DEFAULT_SKILL_PATH",
]
