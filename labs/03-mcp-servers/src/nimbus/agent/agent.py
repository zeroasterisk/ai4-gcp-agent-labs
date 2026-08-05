"""Nimbus agent graph wiring.

The graph is an ADK `Workflow` with four stages that run in order.
`load_history` replays the session into a transcript. `investigate` gathers
facts using the ops MCP tools, the runbook skill and memory recall.
`analyze` runs generated code over those findings. `report` writes the
answer and persists memories.

The runbook skill comes from the managed Skill Registry, which the agent
queries at runtime through its skill toolset. The ops MCP server runs on
Cloud Run and is reached over Streamable HTTP. The graph is driven by an
in-process runner in `runtime/local_runner.py`. Sessions and memory are kept
in memory by the harness. Generated code runs in this process.

The ops tools are defined in `mcp_server/tools.py` and served by
`mcp_server/server.py`. That package is deployed to Cloud Run by
`scripts/deploy_cloud_run.sh` and catalogued in the Agent Registry by
`scripts/register_in_registry.sh`. The agent never imports the tool
functions and reaches them only over MCP. `resolve_ops_toolset()` builds the
toolset offline from the saved endpoint URL, so importing `root_agent` makes
no network call and the toolset connects only when a tool is invoked.
`resolve_ops_toolset_via_registry()` is the live alternative that asks the
Agent Registry for the URL.
"""

from __future__ import annotations

import os
import pathlib
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

_LAB_ROOT = pathlib.Path(__file__).resolve().parents[3]
# Written by scripts/deploy_cloud_run.sh. Reading the marker or the
# environment keeps root_agent construction offline.
OPS_MCP_URL_MARKER = _LAB_ROOT / ".ops_mcp_url"
# Fallback for a local uvicorn server, see mcp_server/server.py.
# Construction is offline either way and the connection opens on use.
DEFAULT_OPS_MCP_URL = "http://localhost:8080/mcp/"


# Capability resolvers.

def _ops_mcp_url() -> str:
    """Returns the Cloud Run MCP endpoint without making a network call.

    The environment variable `OPS_MCP_URL` wins, then the saved marker file,
    then the local default.
    """
    url = os.environ.get("OPS_MCP_URL", "").strip()
    if url:
        return url
    if OPS_MCP_URL_MARKER.exists():
        saved = OPS_MCP_URL_MARKER.read_text().strip()
        if saved:
            return saved
    return DEFAULT_OPS_MCP_URL


def resolve_ops_toolset(url: str | None = None) -> Any:
    """Returns a toolset for the ops tools running on Cloud Run.

    The toolset talks to the Cloud Run MCP server over Streamable HTTP. It
    is built offline from the saved endpoint URL, so constructing
    `root_agent` makes no network call and the toolset opens a connection
    only when a tool is actually invoked.

    Args:
        url: Endpoint URL override. Defaults to `_ops_mcp_url()`.

    Returns:
        An `McpToolset` for the Cloud Run endpoint. Typed `Any` because
        McpToolset is imported lazily below.
    """
    # MCP is an optional extra, so this import is deferred to keep it off
    # the module import path.
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )

    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=url or _ops_mcp_url(),
        ),
    )


def discover_mcp_server_name(registry: Any, display_name: str) -> str:
    """Finds a registered MCP server's resource name by its display name.

    This makes a live Agent Registry call.

    Args:
        registry: An `AgentRegistry` client. Typed `Any` because the class
            is imported lazily by the callers below.
        display_name: The display name to look for.

    Returns:
        The MCP server's full resource name.

    Raises:
        LookupError: If no registered server has that display name.
    """
    for server in registry.list_mcp_servers().get("mcpServers", []):
        if server.get("displayName") == display_name:
            return server["name"]
    raise LookupError(
        f"MCP server '{display_name}' not found in Agent Registry. "
        "Deploy + register it first (see scripts/)."
    )


def resolve_ops_toolset_via_registry(
    project: str | None = None,
    location: str | None = None,
    display_name: str | None = None,
    server_name: str | None = None,
) -> Any:
    """Discovers the ops MCP server and fetches its toolset from the registry.

    This makes a live Agent Registry call, so do not use it at import time.
    `root_agent` uses the offline `resolve_ops_toolset()` instead. Reach for
    this function when you want the registry to be the source of truth.

    Args:
        project: Google Cloud project. Defaults to `GOOGLE_CLOUD_PROJECT`,
            which has no fallback and must be exported.
        location: Registry location. Defaults to `REGISTRY_LOCATION`.
        display_name: Display name to discover by. Defaults to
            `OPS_MCP_DISPLAY_NAME`.
        server_name: Full resource name, skipping discovery. Defaults to
            `OPS_MCP_SERVER_NAME` from the environment.

    Returns:
        The toolset the registry returns for that MCP server. Typed `Any`
        because the registry client is imported lazily below.
    """
    # The registry client is only needed on this live path, so the import
    # is deferred.
    from google.adk.integrations.agent_registry import AgentRegistry

    project = project or require_project()
    registry = AgentRegistry(
        project_id=project,
        location=location or REGISTRY_LOCATION,
    )
    name = (
        server_name
        or os.environ.get("OPS_MCP_SERVER_NAME")
        or discover_mcp_server_name(
            registry, display_name or OPS_MCP_DISPLAY_NAME
        )
    )
    return registry.get_mcp_toolset(mcp_server_name=name)


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
            "(managed MCP + managed skills) -> analyze (code) -> report."
        ),
        edges=[("START", load_history, investigate, analyze, report)],
    )


# Module-level graph used by run_local.py and adk web. Construction is
# offline, with no network call and no model call.
root_agent = build_root_agent()
