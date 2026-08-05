"""Live smoke tests for the local Nimbus graph on Vertex AI Gemini.

These tests are skipped unless RUN_LIVE is set to 1. They need application
default credentials and the aiplatform API. They run the whole graph, which
loads history, investigates using the stdio MCP tools and the local skill,
analyzes findings by running code, then reports. That makes billable Gemini
calls and launches the local MCP subprocess.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from google.adk.code_executors import UnsafeLocalCodeExecutor

RUN_LIVE = os.environ.get("RUN_LIVE") == "1"
pytestmark = pytest.mark.skipif(
    not RUN_LIVE, reason="set RUN_LIVE=1 to run the live Vertex test"
)

_USER_ID = "oncall-ana"


def _setenv() -> None:
    """Points the SDK at the Vertex AI project used by these live tests."""
    os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "True")
    # No default project: a live test must never touch somebody
    # else's project, so skip instead of guessing.
    if not os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip():
        pytest.skip("set GOOGLE_CLOUD_PROJECT to run live tests")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")


def test_live_local_graph_grounds_on_mcp_data():
    """Grounds on the checkout fixtures served by the local stdio MCP."""
    _setenv()

    from nimbus.runtime import APP_NAME, ask, build_local_runner

    async def run() -> str:
        # The graph with in-memory sessions and memory.
        runner = build_local_runner()
        session = await runner.session_service.create_session(
            app_name=APP_NAME,
            user_id=_USER_ID,
        )
        return await ask(
            runner,
            _USER_ID,
            session.id,
            "Is checkout healthy? Give its error rate and triage it.",
        )

    text = asyncio.run(run())
    lowered = text.lower()
    assert text.strip(), "empty response from the local graph"
    assert "4.7" in text, (
        f"expected the fixture error rate via local MCP: {text!r}"
    )
    assert "degrad" in lowered, f"expected the fixture status: {text!r}"


def test_live_local_analyze_runs_code():
    """The analyze step really executes Python, it does not just describe it."""
    _setenv()

    from google.adk.artifacts import InMemoryArtifactService
    from google.adk.runners import Runner
    from google.genai import types

    from nimbus.agent.agent import build_root_agent
    from nimbus.harness.memory_manager import create_memory_service
    from nimbus.harness.session_manager import create_session_service
    from nimbus.runtime import APP_NAME

    executed: list[str] = []

    class _SpyExecutor(UnsafeLocalCodeExecutor):
        """Records every snippet the agent actually runs."""

        def execute_code(self, invocation_context, code_execution_input):
            executed.append(code_execution_input.code)
            return super().execute_code(
                invocation_context, code_execution_input
            )

    async def run() -> str:
        runner = Runner(
            node=build_root_agent(code_executor=_SpyExecutor()),
            app_name=APP_NAME,
            session_service=create_session_service(),
            memory_service=create_memory_service(),
            artifact_service=InMemoryArtifactService(),
        )
        session = await runner.session_service.create_session(
            app_name=APP_NAME,
            user_id=_USER_ID,
        )
        question = (
            "For every service compute pain = error_rate_pct / "
            "p95_latency_ms * 1000 and rank them worst-first."
        )
        message = types.Content(
            role="user", parts=[types.Part(text=question)]
        )
        final = ""
        async for event in runner.run_async(
            user_id=_USER_ID, session_id=session.id, new_message=message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if getattr(part, "text", None):
                        final = part.text
        return final

    text = asyncio.run(run())
    assert executed, (
        "the analyze step answered without executing any code, so the code "
        f"executor was bypassed: {text!r}"
    )
    assert text.strip() and "checkout" in text.lower(), (
        f"expected checkout ranked worst: {text!r}"
    )
    assert any(char.isdigit() for char in text), (
        "expected computed numbers in the answer"
    )
