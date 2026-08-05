"""Memory management for Nimbus.

`create_memory_service()` returns an in-memory ADK memory service, so
recall works inside a single process. `auto_save_memories` is generic. It
saves the finished session to whatever memory service the runner provides,
so it works with any of them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from google.adk.memory import InMemoryMemoryService

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext


def create_memory_service() -> InMemoryMemoryService:
    """Creates the service that stores what the agent recalls.

    Memories are held in memory in this process, so recall does not
    survive a restart.

    Returns:
        A new in-memory ADK memory service.
    """
    return InMemoryMemoryService()


async def auto_save_memories(callback_context: CallbackContext) -> None:
    """Persists the finished session so it can be recalled later.

    Wired as an `after_agent_callback`. It uses the memory service already
    attached to the run, so it needs no knowledge of which service that
    is.

    Args:
        callback_context: ADK callback context for the finished
            invocation, from which the run's memory service and session
            are read.
    """
    try:
        ctx = callback_context._invocation_context
        memory_service = getattr(ctx, "memory_service", None)
        if memory_service is not None:
            await memory_service.add_session_to_memory(ctx.session)
    # The broad catch is deliberate. Saving memories is best effort here,
    # and a failure must never break the user's turn.
    except Exception as e:  # pragma: no cover
        print(f"Warning: failed to save memories: {e}")
