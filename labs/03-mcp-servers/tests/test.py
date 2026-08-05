"""Static and unit tests that run offline with no cloud calls.

These tests check that the Nimbus graph builds offline, that
`resolve_skill_toolset()` returns a `SkillToolset` backed by the managed
Skill Registry, and that `resolve_ops_toolset()` returns a Streamable HTTP
`McpToolset` pointing at the ops server on Cloud Run, built from the saved
endpoint without a network call. Generated code runs in this process, and
sessions and memory are held in memory. The tests that deploy the server,
register it and call it through the Agent Registry are in test_live.py.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from collections.abc import Mapping, Sequence

import pytest
from google.adk import Workflow
from google.adk.code_executors import UnsafeLocalCodeExecutor
from google.adk.memory import InMemoryMemoryService
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPConnectionParams,
)
from google.adk.tools.skill_toolset import SkillToolset

from nimbus.agent import (
    DEFAULT_SKILL_ID,
    DEFAULT_SKILL_PATH,
    SkillAdmin,
    build_root_agent,
    discover_mcp_server_name,
    resolve_code_executor,
    resolve_ops_toolset,
    resolve_skill_toolset,
    root_agent,
)
from nimbus.harness import create_memory_service, create_session_service

_LAB_ROOT = pathlib.Path(__file__).resolve().parents[1]

# The tools live in the MCP server package that is deployed to Cloud
# Run. Import them the way server.py does to test the tool logic.
sys.path.insert(0, str(_LAB_ROOT / "mcp_server"))
from tools import (  # noqa: E402
    get_error_rate,
    get_service_health,
    list_services,
)


# The data tools in mcp_server, served over the MCP server on Cloud Run.

def test_data_tools():
    assert list_services()["services"] == sorted(list_services()["services"])
    assert get_service_health("Checkout")["status"] == "degraded"
    assert get_service_health("nope")["error"]
    assert get_error_rate("checkout")["severity"] == "high"


# Graph wiring.

def test_root_is_graph_workflow():
    assert (
        isinstance(root_agent, Workflow)
        and root_agent.name == "nimbus"
        and root_agent.edges
    )


def test_build_root_agent_returns_workflow():
    assert isinstance(build_root_agent(), Workflow)


# Skills come from the Skill Registry and the ops tools from Cloud Run,
# while sessions, memory and code execution stay local.

def test_skills_managed_registry_toolset():
    # Skills come from the managed Skill Registry (GCPSkillRegistry), not
    # from a local SKILL.md file.
    from google.adk.integrations.skill_registry.gcp_skill_registry import (
        GCPSkillRegistry,
    )

    toolset = resolve_skill_toolset()
    assert isinstance(toolset, SkillToolset)
    assert isinstance(
        getattr(toolset, "_registry", None), GCPSkillRegistry
    ), "expected a managed (registry-backed) SkillToolset"


def test_mcp_managed_http_toolset():
    # The ops tools come from a Streamable HTTP McpToolset pointing at
    # Cloud Run, not from a local stdio subprocess.
    toolset = resolve_ops_toolset()
    assert isinstance(toolset, McpToolset)
    assert isinstance(
        toolset._connection_params, StreamableHTTPConnectionParams
    ), "expected managed HTTP MCP (not stdio)"
    assert toolset._connection_params.url.endswith("/mcp/")


def test_code_still_local():
    assert isinstance(resolve_code_executor(), UnsafeLocalCodeExecutor)


def test_sessions_and_memory_still_local():
    assert isinstance(create_session_service(), InMemorySessionService)
    assert isinstance(create_memory_service(), InMemoryMemoryService)


# The managed skill package and its admin helper.

def test_packaged_skill_md_is_valid():
    skill_md = _LAB_ROOT / "skills" / "cymbal-ops-runbook" / "SKILL.md"
    text = skill_md.read_text()
    assert (
        text.startswith("---")
        and "name: cymbal-ops-runbook" in text
        and "description:" in text
    )


def test_default_skill_path_points_at_the_package():
    assert DEFAULT_SKILL_ID == "cymbal-ops-runbook"
    assert pathlib.Path(DEFAULT_SKILL_PATH, "SKILL.md").exists()


def test_skill_admin_defaults():
    admin = SkillAdmin(project="p", location="us-central1")
    assert admin.project == "p" and admin.location == "us-central1"


# The Cloud Run MCP server and its registry catalogue.

def test_toolspec_is_valid_and_matches_server():
    spec = json.loads((_LAB_ROOT / "mcp_server" / "toolspec.json").read_text())
    names = {tool["name"] for tool in spec["tools"]}
    assert names == {"list_services", "get_service_health", "get_error_rate"}
    for tool in spec["tools"]:
        # Registry TOOL_SPEC requires a real inputSchema per tool.
        assert tool["inputSchema"]["type"] == "object"


def test_ops_mcp_server_builds():
    spec = importlib.util.spec_from_file_location(
        "ops_mcp_server",
        _LAB_ROOT / "mcp_server" / "server.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build_mcp_server() is not None
    assert module.build_asgi_app() is not None


def test_discover_by_display_name():
    # The registry discovery helper used by
    # resolve_ops_toolset_via_registry. Nothing here touches the network.
    class FakeRegistry:
        """Stand-in for the Agent Registry client, built from fixed rows."""

        def __init__(self, servers: Sequence[Mapping[str, str]]):
            self._servers = servers

        def list_mcp_servers(self) -> dict[str, Sequence[Mapping[str, str]]]:
            return {"mcpServers": self._servers}

    registry = FakeRegistry(
        [
            {
                "displayName": "cymbal-ops-mcp",
                "name": "projects/p/locations/global/mcpServers/x",
            },
        ]
    )
    assert discover_mcp_server_name(registry, "cymbal-ops-mcp").endswith("/x")
    with pytest.raises(LookupError):
        discover_mcp_server_name(FakeRegistry([]), "cymbal-ops-mcp")
