"""Static and unit tests that run offline with no cloud calls.

These tests check that the Nimbus graph builds offline and that every
capability resolves to a local implementation. The skill is loaded from a
local directory, the ops MCP server runs as a stdio subprocess, generated
code runs in this process, and sessions and memory are held in memory. The
tests that call the model live are in test_live.py.
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

def test_list_services_sorted_and_known():
    out = list_services()
    assert (
        "checkout" in out["services"]
        and out["services"] == sorted(out["services"])
    )


def test_get_service_health_known_is_case_insensitive():
    out = get_service_health("Checkout")
    assert out["service"] == "checkout" and out["status"] == "degraded"


def test_get_service_health_unknown_lists_known():
    out = get_service_health("does-not-exist")
    assert "error" in out and "checkout" in out["known_services"]


def test_get_error_rate_severity_bands():
    # The fixtures put checkout at 4.7 and recommendations at 0.9.
    assert get_error_rate("checkout")["severity"] == "high"
    assert get_error_rate("recommendations")["severity"] == "normal"


# Graph wiring.

def test_root_is_graph_workflow():
    assert isinstance(root_agent, Workflow)
    assert root_agent.name == "nimbus" and root_agent.edges


def test_build_root_agent_returns_workflow():
    assert isinstance(build_root_agent(), Workflow)


# Every capability resolves to a local implementation.

def test_skills_local_skill_toolset():
    # The skill is loaded from a local directory.
    assert isinstance(resolve_skill_toolset(), SkillToolset)


def test_mcp_local_stdio_toolset():
    # The ops tools come from a local stdio MCP subprocess.
    assert isinstance(resolve_ops_toolset(), McpToolset)


def test_code_local_executor():
    # Generated code runs in this process.
    assert isinstance(resolve_code_executor(), UnsafeLocalCodeExecutor)


def test_sessions_local_in_memory():
    # Sessions are stored in process, not in a managed service.
    assert isinstance(create_session_service(), InMemorySessionService)


def test_memory_local_in_memory():
    # Memory is stored in process, not in a managed service.
    assert isinstance(create_memory_service(), InMemoryMemoryService)


# The local assets exist and the stdio MCP server builds.

def test_local_assets_exist():
    assert (_LAB_ROOT / "skills" / "cymbal-ops-runbook" / "SKILL.md").exists()
    assert (_LAB_ROOT / "mcp_server" / "server.py").exists()


def test_ops_mcp_server_builds():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ops_mcp_server",
        _LAB_ROOT / "mcp_server" / "server.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (
        module.build_server() is not None
        and module.SERVER_NAME == "cymbal-ops-local"
    )
