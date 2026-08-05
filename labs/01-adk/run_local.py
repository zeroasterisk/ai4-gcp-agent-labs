"""Run Nimbus on your laptop.

The pipeline loads the conversation history, investigates with the ops MCP
tools and the runbook skill, analyzes the findings by running code, then
reports. An ADK `Runner` drives the graph in this process, backed by
in-memory session and memory services.

    export GOOGLE_GENAI_USE_ENTERPRISE=True GOOGLE_CLOUD_PROJECT=your-project-id GOOGLE_CLOUD_LOCATION=global
    uv run --no-project --python ../../.venv/bin/python run_local.py "Is checkout healthy? Triage it."
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Imported after the sys.path bootstrap above, hence the E402 waiver.
from nimbus.env import bootstrap, check_auth_or_exit  # noqa: E402

# Load .env (this lab's, then the repo root's) and settle the auth mode
# BEFORE the agent modules are imported: they read GEMINI_MODEL and the
# project at import time. Real environment variables always win.
bootstrap(__file__)

from nimbus.runtime import APP_NAME, ask, build_local_runner  # noqa: E402

USER_ID = "oncall-ana"


async def main(query: str) -> None:
    """Runs one Nimbus query in a fresh local session and prints the answer.

    Args:
        query: The question to send to Nimbus.
    """
    # The graph with in-memory sessions and memory.
    runner = build_local_runner()
    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )
    print(f"[nimbus] > {query}\n")
    print(await ask(runner, USER_ID, session.id, query))


if __name__ == "__main__":
    # Fail early and readably instead of a cloud 403 or a traceback.
    check_auth_or_exit(needs_project=False)
    query = " ".join(sys.argv[1:]) or (
        "Is checkout healthy? Triage it and recommend a next step."
    )
    asyncio.run(main(query))
