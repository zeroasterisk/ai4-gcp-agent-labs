"""Run Nimbus with the runbook skill from the managed Skill Registry.

`GCPSkillRegistry` discovers and loads the runbook skill at runtime. The ops
MCP server runs as a local stdio subprocess, and sessions, memory and code
execution all stay in this process. Register the skill once first.

    export GOOGLE_CLOUD_PROJECT=your-project-id GOOGLE_CLOUD_LOCATION=global
    uv run --no-project --python ../../.venv/bin/python skill_admin.py register   # one-time
    uv run --no-project --python ../../.venv/bin/python demo.py "Is checkout healthy? Triage it."
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


async def run(prompt: str) -> str:
    """Answers one prompt in a fresh local session.

    Args:
        prompt: The question to send to Nimbus.

    Returns:
        The agent's final text response.
    """
    # The graph with in-memory sessions and memory. The skills come from
    # the registry.
    runner = build_local_runner()
    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )
    return await ask(runner, USER_ID, session.id, prompt)


def main() -> None:
    """Answers the prompt from `sys.argv` (or the default) and prints it."""
    prompt = " ".join(sys.argv[1:]) or (
        "Is checkout healthy? Triage it and recommend a next step."
    )
    print(f"Q: {prompt}\n")
    print(asyncio.run(run(prompt)))


if __name__ == "__main__":
    # Fail early and readably instead of a cloud 403 or a traceback.
    check_auth_or_exit(needs_project=True)
    main()
