"""Static and unit tests that run offline with no cloud calls.

These tests check that the Nimbus graph builds offline and that
`resolve_skill_toolset()` returns a `SkillToolset` backed by the managed
Skill Registry. The ops MCP server runs as a stdio subprocess, generated
code runs in this process, and sessions and memory are held in memory. The
tests that call the Skill Registry live are in test_live.py.
"""

from __future__ import annotations

import pathlib
import sys

from google.adk import Workflow
from google.adk.code_executors import UnsafeLocalCodeExecutor
from google.adk.memory import InMemoryMemoryService
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset
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

# The tools live in the MCP server package. Import them the way
# server.py does so the tool logic is tested directly.
sys.path.insert(0, str(_LAB_ROOT / "mcp_server"))
from tools import (  # noqa: E402
    get_error_rate,
    get_service_health,
    list_services,
)


# The data tools, which the stdio MCP server serves locally.

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


# Skills come from the managed Skill Registry, while the MCP server,
# sessions, memory and code execution all run locally.

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


def test_mcp_still_local_stdio():
    assert isinstance(resolve_ops_toolset(), McpToolset)


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


def test_ops_mcp_server_builds():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ops_mcp_server",
        _LAB_ROOT / "mcp_server" / "server.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build_server() is not None
