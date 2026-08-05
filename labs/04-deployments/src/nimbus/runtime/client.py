"""Run turns on the Nimbus graph deployed to Agent Runtime.

This is the run side of the deployment. It resolves the deployed
`reasoningEngine`, either from the `AGENT_ENGINE_NAME` environment
variable or from the marker file the deploy step writes, then streams a
turn against it. Sessions and memory are still the harness in-memory
services, which now live inside the engine.
"""

from __future__ import annotations

import os
from typing import Any

import vertexai

from ..env import resource_location as _location
from ..env import require_project

# The project has no default and is resolved lazily, right before the
# call that needs it, so importing this module stays offline.

_HERE = os.path.dirname(__file__)  # .../src/nimbus/runtime
_LAB_ROOT = os.path.join(_HERE, "..", "..", "..")
_NAME_FILES = [
    os.path.join(_LAB_ROOT, ".agent_engine"),
    os.path.join(_LAB_ROOT, "..", "04-deployments", ".agent_engine"),
]


def engine_name() -> str:
    """Resolves the resource name of the deployed agent.

    Read from `AGENT_ENGINE_NAME`, falling back to the `.agent_engine`
    marker file that the deploy step writes.

    Returns:
        The full `reasoningEngine` resource name.

    Raises:
        SystemExit: If no deployed agent can be found.
    """
    name = os.environ.get("AGENT_ENGINE_NAME")
    if not name:
        for path in _NAME_FILES:
            if os.path.exists(path):
                with open(path) as f:
                    name = f.read().strip()
                break
    if not name:
        raise SystemExit(
            "No deployed agent. Deploy Lab 04 first or set"
            " AGENT_ENGINE_NAME."
        )
    return name


def engine_id() -> str:
    """Returns the trailing id of the deployed engine.

    Returns:
        The last path segment of `engine_name()`, which is the engine id
        that session services key their app name on.
    """
    return engine_name().split("/")[-1]


def get_deployed_agent() -> Any:
    """Fetches a handle to the deployed engine.

    Returns:
        The Vertex AI agent engine handle for `engine_name()`. Typed
        `Any` because the SDK returns an opaque client object.
    """
    client = vertexai.Client(project=require_project(), location=_location())
    return client.agent_engines.get(name=engine_name())


def delete_deployed(force: bool = True) -> str:
    """Deletes the deployed engine and the local `.agent_engine` marker.

    Deleting the engine is what stops it billing.

    Args:
        force: Whether to delete the engine's child resources with it.

    Returns:
        The resource name of the engine that was deleted.
    """
    name = engine_name()
    client = vertexai.Client(project=require_project(), location=_location())
    client.agent_engines.delete(name=name, force=force)
    for path in _NAME_FILES:
        if os.path.exists(path):
            os.remove(path)
    return name


def _parts(event: Any) -> list[Any]:
    """Returns the content parts of a streamed event (dict or object)."""
    if isinstance(event, dict):
        content = event.get("content")
    else:
        content = getattr(event, "content", None)
    if content is None:
        return []
    if isinstance(content, dict):
        parts = content.get("parts")
    else:
        parts = getattr(content, "parts", None)
    return parts or []


def _ptext(part: Any) -> str:
    """Returns the text of one content part, or an empty string."""
    if isinstance(part, dict):
        text = part.get("text")
    else:
        text = getattr(part, "text", None)
    return text or ""


def event_text(event: Any) -> str:
    """Joins the text parts of a streamed event.

    Args:
        event: One event from the engine's stream, as a dict or an object
            exposing `content.parts`.

    Returns:
        The event's text, stripped; empty if it carried no text.
    """
    texts = [_ptext(part) for part in _parts(event)]
    return " ".join(text for text in texts if text).strip()


def event_author(event: Any) -> str:
    """Returns the author of a streamed event.

    Args:
        event: One event from the engine's stream, as a dict or an object
            exposing `author`.

    Returns:
        The author name, or "?" when the event does not carry one.
    """
    if isinstance(event, dict):
        author = event.get("author")
    else:
        author = getattr(event, "author", None)
    return author or "?"


async def ask(remote: Any, user_id: str, session_id: str, message: str) -> str:
    """Runs one turn on the deployed app.

    The turn is persisted to the session held inside the engine.

    Args:
        remote: Handle to the deployed engine (see `get_deployed_agent`).
        user_id: Identifier of the end user.
        session_id: Identifier of the session the turn belongs to.
        message: The user's message for this turn.

    Returns:
        The final text streamed back, or an empty string if there was
        none.
    """
    final = ""
    async for event in remote.async_stream_query(
        user_id=user_id, session_id=session_id, message=message
    ):
        for part in _parts(event):
            text = _ptext(part)
            if text:
                final = text
    return final
