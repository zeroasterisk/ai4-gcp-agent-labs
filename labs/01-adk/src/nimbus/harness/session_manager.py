"""Session management for Nimbus.

`create_session_service()` returns an in-memory ADK session service, so a
conversation lives only for as long as the process does. `SessionManager`
is a thin lifecycle facade over that service for creating, reading and
deleting sessions.
"""

from __future__ import annotations

from typing import Any

from google.adk.sessions import InMemorySessionService


def create_session_service() -> InMemorySessionService:
    """Creates the service that stores conversation history.

    Sessions are held in memory in this process, so they are ephemeral.

    Returns:
        A new in-memory ADK session service.
    """
    return InMemorySessionService()


class SessionManager:
    """Lifecycle facade over an injected session service.

    Used by the demos, the CLI and the tests to create, read and delete
    sessions without caring which session service is underneath.
    """

    def __init__(
        self,
        app_name: str = "nimbus",
        session_service: InMemorySessionService | None = None,
    ):
        """Initializes the facade over a session service.

        Args:
            app_name: ADK application name used for every session call.
            session_service: Session service to drive. Defaults to a new
                in-memory service from `create_session_service()`.
        """
        self.app_name = app_name
        self.session_service = session_service or create_session_service()

    async def create(self, user_id: str) -> str:
        """Creates a session for a user.

        Args:
            user_id: Identifier of the end user owning the session.

        Returns:
            The id of the newly created session.
        """
        session = await self.session_service.create_session(
            app_name=self.app_name, user_id=user_id
        )
        return session.id

    async def history(self, user_id: str, session_id: str) -> list[Any]:
        """Reads the events recorded on a session.

        Args:
            user_id: Identifier of the end user owning the session.
            session_id: Identifier of the session to read.

        Returns:
            The session's ADK events, oldest first.
        """
        session = await self.session_service.get_session(
            app_name=self.app_name, user_id=user_id, session_id=session_id
        )
        return list(session.events)

    async def delete(self, user_id: str, session_id: str) -> None:
        """Deletes a session.

        Args:
            user_id: Identifier of the end user owning the session.
            session_id: Identifier of the session to delete.
        """
        await self.session_service.delete_session(
            app_name=self.app_name, user_id=user_id, session_id=session_id
        )
