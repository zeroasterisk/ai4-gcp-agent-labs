"""Nimbus agent graph wiring.

The graph is an ADK `Workflow` with four stages that run in order.
`load_history` replays the session into a transcript. `investigate` gathers
facts using the ops MCP tools, the runbook skill and memory recall.
`analyze` runs generated code over those findings. `report` writes the
answer and persists memories.

Everything this lab needs runs on the local machine. The runbook skill is
loaded from a directory on disk. The ops MCP server runs as a local stdio
subprocess. The graph is driven by an in-process runner. Sessions and memory
are kept in memory by the harness. Generated code runs in this process.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

from google.adk import Agent, Workflow
from google.adk.code_executors import UnsafeLocalCodeExecutor
from google.adk.skills import load_skill_from_dir
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.tools.skill_toolset import SkillToolset

from ..harness.memory_manager import auto_save_memories
from .config import MODEL
from .prompts import (
    ANALYZE_DELEGATION_INSTRUCTION,
    ANALYZE_INSTRUCTION,
    INVESTIGATE_INSTRUCTION,
    REPORT_INSTRUCTION,
)

_LAB_ROOT = pathlib.Path(__file__).resolve().parents[3]
LOCAL_SKILL_DIR = _LAB_ROOT / "skills" / "cymbal-ops-runbook"
OPS_MCP_PATH = _LAB_ROOT / "mcp_server" / "server.py"


# Capability resolvers.

def resolve_skill_toolset() -> SkillToolset:
    """Returns a toolset holding the runbook skill.

    The skill is read from the local directory at `LOCAL_SKILL_DIR`.
    """
    return SkillToolset(skills=[load_skill_from_dir(str(LOCAL_SKILL_DIR))])


def resolve_ops_toolset() -> Any:
    """Returns a toolset for the ops tools, served over stdio MCP.

    The MCP server at `OPS_MCP_PATH` runs as a local subprocess.

    Returns:
        An `McpToolset` bound to a stdio subprocess running OPS_MCP_PATH.
        Typed `Any` because McpToolset is imported lazily below.
    """
    # MCP is an optional extra, so this import is deferred to keep it off
    # the module import path.
    from mcp import StdioServerParameters
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StdioConnectionParams,
    )

    params = StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[str(OPS_MCP_PATH)],
        ),
        # Generous, to avoid a cold start race when the subprocess is
        # launched on the first call.
        timeout=30,
    )
    return McpToolset(connection_params=params)


def resolve_code_executor() -> UnsafeLocalCodeExecutor:
    """Returns an executor that runs generated code in this process."""
    return UnsafeLocalCodeExecutor()


# The graph.

def load_history(node_input: str, ctx: Any) -> str:
    """Builds a history-aware input for the next node from the session.

    This node calls no model. It replays the session's events into a
    transcript so the next node can resolve references back to earlier
    turns.

    Args:
        node_input: Text arriving at this node. It is used as the transcript
            when the session has no prior events.
        ctx: The ADK node context. Typed `Any` because the concrete context
            class is an ADK runtime detail; only `ctx.session.events` is
            read.

    Returns:
        A prompt holding the conversation so far plus an instruction to
        answer the last user message.
    """
    lines: list[str] = []
    for event in getattr(ctx.session, "events", []) or []:
        content = getattr(event, "content", None)
        if not content:
            continue
        role = getattr(content, "role", None) or "user"
        text = " ".join(
            getattr(part, "text", "") or ""
            for part in (getattr(content, "parts", []) or [])
        ).strip()
        if text:
            lines.append(f"{'User' if role == 'user' else 'Nimbus'}: {text}")
    transcript = "\n".join(lines) if lines else f"User: {node_input}"
    return (
        f"Conversation so far:\n{transcript}\n\n"
        "Answer the LAST user message, resolving any references from the "
        "conversation above."
    )


def build_root_agent(
    ops_toolset: Any = None,
    skill_toolset: Any = None,
    code_executor: Any = None,
) -> Workflow:
    """Builds the Nimbus agent graph.

    By default every capability is wired locally. Pass a toolset or an
    executor to inject your own.

    `investigate` gathers facts with the ops MCP tools served over a local
    stdio subprocess, the runbook skill loaded from a local directory, and
    memory recall. `analyze` delegates any arithmetic to an inner agent
    that runs Python, which keeps the code events inside a tool call.
    `report` presents the findings and persists memories.

    Args:
        ops_toolset: Toolset providing the ops tools, or None to build the
            default via `resolve_ops_toolset()`. Typed `Any` because the
            McpToolset class is imported lazily inside that resolver.
        skill_toolset: Toolset providing the runbook skill, or None to build
            the default via `resolve_skill_toolset()`.
        code_executor: Code executor for the `analyze` node, or None to
            build the default via `resolve_code_executor()`.

    Returns:
        The wired `nimbus` Workflow.
    """
    investigate = Agent(
        name="investigate",
        model=MODEL,
        instruction=INVESTIGATE_INSTRUCTION,
        tools=[
            # The ops tools over a local stdio MCP subprocess.
            ops_toolset or resolve_ops_toolset(),
            # The runbook skill loaded from a local directory.
            skill_toolset or resolve_skill_toolset(),
            # Memory recall, backed by the harness memory service.
            PreloadMemoryTool(),
        ],
    )
    # A node may emit only one output and running code emits several events,
    # so the executor goes on an inner agent called as a tool.
    code_runner = Agent(
        name="code_runner",
        model=MODEL,
        instruction=ANALYZE_INSTRUCTION,
        code_executor=code_executor or resolve_code_executor(),
    )
    analyze = Agent(
        name="analyze",
        model=MODEL,
        instruction=ANALYZE_DELEGATION_INSTRUCTION,
        tools=[AgentTool(agent=code_runner)],
    )
    report = Agent(
        name="report",
        model=MODEL,
        instruction=REPORT_INSTRUCTION,
        # Persists memories once the run finishes. With the in-memory
        # service this does nothing lasting.
        after_agent_callback=auto_save_memories,
    )
    return Workflow(
        name="nimbus",
        description=(
            "Cymbal Cloud Ops Copilot — load_history -> investigate "
            "(MCP+skills) -> analyze (code) -> report."
        ),
        edges=[("START", load_history, investigate, analyze, report)],
    )


# Module-level graph used by run_local.py and adk web. Construction is
# offline, with no network call and no model call.
root_agent = build_root_agent()
