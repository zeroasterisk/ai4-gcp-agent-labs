"""Nimbus agent harness, the capability subsystems around the graph.

This package provides the services the agent runs on. Sessions and memory
are both in-memory implementations that live in this process, together
with the `SessionManager` facade over the session service and the
`auto_save_memories` callback that writes a finished session into memory.
"""

from .memory_manager import auto_save_memories, create_memory_service
from .session_manager import SessionManager, create_session_service

__all__ = [
    "create_session_service",
    "SessionManager",
    "create_memory_service",
    "auto_save_memories",
]
