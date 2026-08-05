"""Live tests that consume the ops MCP server via the Agent Registry.

These tests need the server to be deployed with scripts/deploy_cloud_run.sh
and registered with scripts/register_in_registry.sh, and the skill to be
registered with skill_admin.py register. They are skipped unless RUN_LIVE is
set to 1. They call the MCP server, the Skill Registry and Gemini, and they
run the whole graph.
"""

from __future__ import annotations

import asyncio
import os

import pytest

RUN_LIVE = os.environ.get("RUN_LIVE") == "1"
pytestmark = pytest.mark.skipif(
    not RUN_LIVE,
    reason="set RUN_LIVE=1 (needs deployed+registered MCP server)",
)

_APP_NAME = "nimbus"
_USER_ID = "test-user"


def _env() -> None:
    """Points the SDK at the project and registry used by these live tests."""
    os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "True")
    # No default project: a live test must never touch somebody
    # else's project, so skip instead of guessing.
    if not os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip():
        pytest.skip("set GOOGLE_CLOUD_PROJECT to run live tests")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
    os.environ.setdefault("REGISTRY_LOCATION", "global")


def test_live_consume_via_registry():
    """Discovers the ops MCP server in the registry and grounds on its data."""
    _env()

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    from nimbus.agent import build_root_agent, resolve_ops_toolset_via_registry

    async def run() -> str:
        # Discover the server in the Agent Registry and get its toolset.
        ops_toolset = resolve_ops_toolset_via_registry()
        tools = await ops_toolset.get_tools()
        names = {tool.name for tool in tools}
        assert {
            "list_services",
            "get_service_health",
            "get_error_rate",
        } <= names, names

        # Inject the managed MCP toolset that came from the registry.
        root = build_root_agent(ops_toolset=ops_toolset)
        runner = InMemoryRunner(node=root, app_name=_APP_NAME)
        session = await runner.session_service.create_session(
            app_name=_APP_NAME,
            user_id=_USER_ID,
        )
        content = types.Content(
            role="user",
            parts=[
                types.Part(text="Is checkout healthy? Give the error rate."),
            ],
        )
        final = ""
        async for event in runner.run_async(
            user_id=_USER_ID,
            session_id=session.id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if getattr(part, "text", None):
                        final = part.text
        await ops_toolset.close()
        return final

    text = asyncio.run(run())
    lowered = text.lower()
    # The graph pulled data via the registry-sourced MCP tools and grounded
    # on checkout.
    assert "4.7" in text, f"expected checkout error rate in answer: {text!r}"
    assert "degrad" in lowered, f"expected checkout status in answer: {text!r}"


def test_skill_toolset_exposes_lifecycle_tools():
    """The ADK SkillToolset (GCP Skill Registry) yields lifecycle tools."""
    _env()
    from nimbus.agent import resolve_skill_toolset

    toolset = resolve_skill_toolset()

    async def names() -> list[str]:
        tools = await toolset.get_tools()
        out = [tool.name for tool in tools]
        close = getattr(toolset, "close", None)
        if close:
            result = close()
            if asyncio.iscoroutine(result):
                await result
        return out

    tool_names = asyncio.run(names())
    assert tool_names, "expected skill-lifecycle tools from the toolset"
    assert any("skill" in name.lower() for name in tool_names), tool_names
