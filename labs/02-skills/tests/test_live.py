"""Live smoke tests for the Nimbus graph against Vertex AI Gemini.

These tests are skipped unless RUN_LIVE is set to 1. They need application
default credentials and the aiplatform API. They run the full graph, which
classifies the question, fetches health data, then reports, and they also
exercise the managed Skill Registry. That makes billable Gemini calls.
"""

from __future__ import annotations

import asyncio
import os

import pytest

RUN_LIVE = os.environ.get("RUN_LIVE") == "1"
pytestmark = pytest.mark.skipif(
    not RUN_LIVE, reason="set RUN_LIVE=1 to run the live Vertex test"
)

_APP_NAME = "nimbus"
_USER_ID = "test-user"


def test_live_graph_grounds_on_tool_data():
    os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "True")
    # No default project: a live test must never touch somebody
    # else's project, so skip instead of guessing.
    if not os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip():
        pytest.skip("set GOOGLE_CLOUD_PROJECT to run live tests")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    from nimbus.agent import root_agent

    async def run() -> str:
        runner = InMemoryRunner(node=root_agent, app_name=_APP_NAME)
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
                        # The last text seen is the report node output.
                        final = part.text
        return final

    text = asyncio.run(run())
    assert text.strip(), "empty response from the graph"
    lowered = text.lower()
    # Grounding in the checkout fixture, 4.7 percent and degraded, proves
    # the nodes actually ran.
    assert "4.7" in text, (
        f"expected the fixture error rate in the answer: {text!r}"
    )
    assert "degrad" in lowered, (
        f"expected the fixture status in the answer: {text!r}"
    )


# The managed Skill Registry, exercised live.

def _env() -> None:
    """Points the SDK at the Vertex AI project used by these live tests."""
    os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "True")
    # No default project: a live test must never touch somebody
    # else's project, so skip instead of guessing.
    if not os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip():
        pytest.skip("set GOOGLE_CLOUD_PROJECT to run live tests")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")


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


def test_register_packaged_skill_or_already_exists():
    """Registers the packaged skill; tolerant of a prior run (immutable id)."""
    _env()
    from nimbus.agent import SkillAdmin

    try:
        operation = SkillAdmin().register()
        assert getattr(operation, "name", None), (
            "expected an operation/skill resource name"
        )
    except Exception as e:
        # The skill id is immutable, so a re-run is expected to find the
        # skill already registered. The broad catch is deliberate here.
        message = str(e).lower()
        assert any(
            keyword in message for keyword in ("exist", "already", "409")
        ), repr(e)
