"""Nimbus agent graph wiring.

The graph is an ADK `Workflow` with four stages that run in order.
`load_history` replays the session into a transcript. `investigate` gathers
facts using the ops MCP tools, the runbook skill and memory recall.
`analyze` runs generated code over those findings. `report` writes the
answer and persists memories.

The runbook skill comes from the managed Skill Registry, which the agent
queries at runtime through its skill toolset. The ops MCP server runs on
Cloud Run and is reached over Streamable HTTP. Sessions and memory are kept
in memory by the harness. Generated code runs in this process.

The graph itself is deployed to the managed Agent Runtime. `runtime/deploy.py`
wraps `build_root_agent()` in an `AdkApp` and ships it, and `client.py` calls
the deployed engine. `resolve_ops_toolset()` builds a plain, deployable
`McpToolset` from the endpoint URL in `OPS_MCP_URL`, read from the
environment or a saved marker, so `build_root_agent()` and the module-level
`root_agent` construct offline with no live Agent Registry lookup. That
offline construction is exactly what lets the graph ship to Agent Runtime.
"""

from __future__ import annotations

import os
from typing import Any

from google.adk import Agent, Workflow
from google.adk.code_executors import UnsafeLocalCodeExecutor
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from ..env import require_project
from ..harness.memory_manager import auto_save_memories
from .config import MODEL, OPS_MCP_DISPLAY_NAME, REGISTRY_LOCATION
from .prompts import (
    ANALYZE_DELEGATION_INSTRUCTION,
    ANALYZE_INSTRUCTION,
    INVESTIGATE_INSTRUCTION,
    REPORT_INSTRUCTION,
)
# Loads skills from the managed Skill Registry.
from .skills import resolve_skill_toolset

# Placeholder endpoint. Constructing an McpToolset never connects, so
# build_root_agent() stays offline.
_OFFLINE_OPS_MCP_URL = "http://localhost:1/mcp/"


# Capability resolvers.

def discover_ops_mcp_url(registry: Any, display_name: str) -> str:
    """Looks up the registered ops MCP server's endpoint URL.

    This makes a live Agent Registry call.

    Args:
        registry: An `AgentRegistry` client. Typed `Any` because the class
            is imported lazily by the caller below.
        display_name: The display name to look for.

    Returns:
        The MCP server's endpoint URL.

    Raises:
        LookupError: If no registered server with that display name exposes
            a URL.
    """
    for server in registry.list_mcp_servers().get("mcpServers", []):
        if server.get("displayName") == display_name:
            interfaces = server.get("interfaces") or []
            if interfaces and interfaces[0].get("url"):
                return interfaces[0]["url"]
    raise LookupError(
        f"MCP server '{display_name}' (with a URL) not found in "
        "Agent Registry."
    )


def resolve_ops_toolset(
    project: str | None = None,
    location: str | None = None,
    display_name: str | None = None,
    url: str | None = None,
) -> Any:
    """Returns a deployable toolset for the ops MCP running on Cloud Run.

    This resolver is offline safe by design. The URL is read from
    `OPS_MCP_URL`, either the environment or a saved marker, and used to
    build a plain `McpToolset(StreamableHTTPConnectionParams(url=...))`
    directly, with no live Agent Registry lookup at construction. That keeps
    `build_root_agent()` offline and lets the graph cloudpickle for Agent
    Runtime, which a `get_mcp_toolset` toolset cannot do.
    Live registry discovery is available at deploy time by opting in
    explicitly with `OPS_MCP_DISCOVER=1`.

    Args:
        project: Google Cloud project used only by the opt-in discovery
            path. Defaults to `GOOGLE_CLOUD_PROJECT`, which has no
            fallback and must be exported.
        location: Registry location for discovery. Defaults to
            `REGISTRY_LOCATION`.
        display_name: Display name to discover by. Defaults to
            `OPS_MCP_DISPLAY_NAME`.
        url: Endpoint URL override. Defaults to `OPS_MCP_URL`, then
            discovery, then the offline placeholder.

    Returns:
        A plain `McpToolset` for the Cloud Run endpoint. Typed `Any` because
        McpToolset is imported lazily below.
    """
    # MCP is an optional extra, so this import is deferred to keep it off
    # the module import path.
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )

    url = url or os.environ.get("OPS_MCP_URL")
    if not url and os.environ.get("OPS_MCP_DISCOVER") == "1":
        # The registry client is only needed on this live path, so the
        # import is deferred.
        from google.adk.integrations.agent_registry import AgentRegistry

        registry = AgentRegistry(
            project_id=project or require_project(),
            location=location or REGISTRY_LOCATION,
        )
        url = discover_ops_mcp_url(
            registry, display_name or OPS_MCP_DISPLAY_NAME
        )
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=url or _OFFLINE_OPS_MCP_URL,
        ),
    )


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

    `investigate` gathers facts with the ops MCP tools served from Cloud
    Run, the runbook skill from the managed Skill Registry, and memory
    recall. `analyze` delegates any arithmetic to an inner agent that runs
    Python. `report` presents the findings and persists memories.

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
            # The ops tools on Cloud Run over Streamable HTTP MCP.
            ops_toolset or resolve_ops_toolset(),
            # The runbook skill from the managed Skill Registry.
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
        after_agent_callback=auto_save_memories,
    )
    return Workflow(
        name="nimbus",
        description=(
            "Cymbal Cloud Ops Copilot — load_history -> investigate "
            "(MCP + managed skills) -> analyze (code) -> report."
        ),
        edges=[("START", load_history, investigate, analyze, report)],
    )


# Module-level graph used by adk web and deploy. Construction is offline,
# with no network call and no model call.
root_agent = build_root_agent()
