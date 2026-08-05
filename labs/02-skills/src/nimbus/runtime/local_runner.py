"""Local runtime for Nimbus.

The graph runs in this process behind an ADK `Runner`, wired to the
in-memory session and memory services from the harness and to an in-memory
artifact store. Nothing here leaves the machine.
"""

from __future__ import annotations

from google.adk.artifacts import InMemoryArtifactService
from google.adk.runners import Runner
from google.genai import types

from ..agent.agent import root_agent
from ..harness.memory_manager import create_memory_service
from ..harness.session_manager import create_session_service

APP_NAME = "nimbus"


def build_local_runner() -> Runner:
    """Builds the in-process runner for the Nimbus graph.

    The runner is wired with the local harness services, so nothing leaves
    this process.

    Returns:
        An ADK `Runner` that executes the graph locally.
    """
    return Runner(
        node=root_agent,
        app_name=APP_NAME,
        # Conversation history is kept in memory in this process.
        session_service=create_session_service(),
        # Recall across sessions is kept in memory in this process.
        memory_service=create_memory_service(),
        # Artifacts stay in memory. The code executor writes here.
        artifact_service=InMemoryArtifactService(),
    )


async def ask(runner: Runner, user_id: str, session_id: str, text: str) -> str:
    """Runs one turn through the graph.

    Args:
        runner: Runner that owns the graph and its services.
        user_id: Identifier of the end user.
        session_id: Identifier of the session the turn belongs to.
        text: The user's message for this turn.

    Returns:
        The final node's text output, or an empty string if the run
        produced no text.
    """
    content = types.Content(role="user", parts=[types.Part(text=text)])
    final = ""
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=content
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    # The last text seen is the report node's output.
                    final = part.text
    return final
