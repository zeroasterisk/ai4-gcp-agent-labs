"""Query the deployed Nimbus on Agent Runtime.

A thin wrapper around `nimbus.runtime.client`.

    python query_deployed.py "Is checkout healthy?"
"""

import asyncio
import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Imported after the sys.path bootstrap above, hence the E402 waiver.
from nimbus.env import bootstrap, check_auth_or_exit  # noqa: E402

# Load .env (this lab's, then the repo root's) and settle the auth mode
# BEFORE the agent modules are imported: they read GEMINI_MODEL and the
# project at import time. Real environment variables always win.
bootstrap(__file__)

from nimbus.runtime import client  # noqa: E402


async def _run(remote: Any, query: str) -> None:
    """Streams one query to the deployed agent and prints the final text.

    Args:
        remote: Handle to the deployed agent, as returned by
            `client.get_deployed_agent()`. Typed `Any` because it is an
            opaque Agent Runtime object.
        query: The question to send to the deployed agent.
    """
    print(f"[nimbus @ agent-runtime] > {query}\n")
    final = ""
    async for event in remote.async_stream_query(
        user_id="oncall-ana",
        message=query,
    ):
        text = client.event_text(event)
        if text:
            final = text
    print(final or "(no text response)")


def main() -> None:
    """Sends the query from `sys.argv` (or the default) to the deployment."""
    # Build the deployed handle outside the event loop.
    remote = client.get_deployed_agent()
    query = " ".join(sys.argv[1:]) or (
        "Is checkout healthy? What's its error rate?"
    )
    asyncio.run(_run(remote, query))


if __name__ == "__main__":
    # Fail early and readably instead of a cloud 403 or a traceback.
    check_auth_or_exit(needs_project=True)
    main()
