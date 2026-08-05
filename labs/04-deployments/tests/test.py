"""Static and unit tests that run offline with no cloud calls.

These tests check that the Nimbus graph builds offline and that
`runtime/deploy.py` ships that graph, by way of `build_root_agent()` rather
than a flattened agent, to the managed Agent Runtime. The graph loads
history, investigates with the MCP tools and the skill, analyzes findings by
running code, then reports. Skills come from the managed Skill Registry and
the ops tools come from a Streamable HTTP MCP server on Cloud Run. Generated
code runs in this process, and sessions and memory are held in memory. The
tests that deploy and query the agent live are in test_live.py.
"""

from __future__ import annotations

import pathlib
import sys

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


# Graph wiring. The graph builds offline so it can ship to Agent Runtime.

def test_root_is_graph_workflow():
    assert (
        isinstance(root_agent, Workflow)
        and root_agent.name == "nimbus"
        and root_agent.edges
    )


def test_build_root_agent_returns_workflow():
    assert isinstance(build_root_agent(), Workflow)


# Skills come from the Skill Registry and the ops tools from Cloud Run,
# while the agent runs on Agent Runtime and sessions stay local.

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


def test_mcp_managed_streamable_http():
    # The ops tools come from a plain, deployable McpToolset over Streamable
    # HTTP pointing at Cloud Run, not from a local stdio subprocess.
    toolset = resolve_ops_toolset()
    assert isinstance(toolset, McpToolset)
    assert isinstance(
        getattr(toolset, "_connection_params", None),
        StreamableHTTPConnectionParams,
    ), "expected a managed (Streamable HTTP) McpToolset, not a local stdio one"


def test_resolve_ops_toolset_constructs_offline():
    # With no OPS_MCP_URL and no OPS_MCP_DISCOVER the resolver must not hit
    # the Agent Registry. It builds the toolset with a placeholder URL.
    import os

    assert os.environ.get("OPS_MCP_DISCOVER") != "1"
    # This would raise if it did a live registry lookup.
    assert isinstance(resolve_ops_toolset(), McpToolset)


def test_code_still_local():
    assert isinstance(resolve_code_executor(), UnsafeLocalCodeExecutor)


def test_sessions_and_memory_still_local():
    assert isinstance(create_session_service(), InMemorySessionService)
    assert isinstance(create_memory_service(), InMemoryMemoryService)


# The managed runtime, where deploy.py ships the graph and the client wires
# up the deployed engine.

def test_deploy_ships_the_graph_deploy_safe():
    deploy_src = (
        _LAB_ROOT / "src" / "nimbus" / "runtime" / "deploy.py"
    ).read_text()
    # The module deploys the graph, which is the Workflow.
    assert "build_root_agent" in deploy_src
    # It does not deploy the older flattened agent.
    assert "build_nimbus" not in deploy_src
    # The graph is wrapped for Agent Runtime.
    assert "AdkApp" in deploy_src
    # Packaging ships the source, pickles the nimbus modules by value, or
    # does both, so the deployed agent can still import nimbus.
    assert (
        "extra_packages" in deploy_src
        or "register_pickle_by_value" in deploy_src
    )
    # Telemetry is switched on and a staging bucket is set.
    assert "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY" in deploy_src
    assert "staging_bucket" in deploy_src


def test_runtime_client_targets_the_deployed_engine():
    from nimbus.runtime import client

    # The run and manage side of the managed runtime is wired up.
    for fn in (
        "engine_name",
        "engine_id",
        "get_deployed_agent",
        "delete_deployed",
        "ask",
    ):
        assert callable(getattr(client, fn, None)), (
            f"runtime.client.{fn} missing"
        )
    # The client reads the .agent_engine marker file that deploy.py writes.
    client_src = (
        _LAB_ROOT / "src" / "nimbus" / "runtime" / "client.py"
    ).read_text()
    assert ".agent_engine" in client_src and "04-deployments" in client_src


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


def test_ops_mcp_server_builds():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ops_mcp_server",
        _LAB_ROOT / "mcp_server" / "server.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # The server exposes an HTTP app for Cloud Run.
    assert (
        module.build_mcp_server() is not None
        and module.build_asgi_app() is not None
    )
