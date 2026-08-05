"""Run Nimbus on your laptop against the Cloud Run MCP server.

The pipeline loads the conversation history, investigates with the ops MCP
tools and the runbook skill, analyzes the findings by running code, then
reports. `runtime.build_local_runner` drives the graph in this process,
backed by in-memory session and memory services. The ops tools come from the
Cloud Run MCP server, whose endpoint is read from `OPS_MCP_URL` or from the
`.ops_mcp_url` marker file written by the deploy script. The runbook skill
comes from the managed Skill Registry.

Deploy and register the MCP server, register the skill, and set the endpoint
before running.

    ./scripts/deploy_cloud_run.sh && ./scripts/register_in_registry.sh               # deploy and register
    export OPS_MCP_URL="$(gcloud run services describe cymbal-ops-mcp --region us-central1 \
        --format='value(status.url)')/mcp/"
    uv run --no-project --python ../../.venv/bin/python skill_admin.py register       # one-time
    export GOOGLE_GENAI_USE_ENTERPRISE=True GOOGLE_CLOUD_PROJECT=your-project-id GOOGLE_CLOUD_LOCATION=global
    uv run --no-project --python ../../.venv/bin/python run_local.py "Is checkout healthy? What's its error rate?"
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
    # The graph with in-memory sessions and memory. The ops tools come from
    # the Cloud Run MCP server.
    runner = build_local_runner()
    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )
    print(f"[nimbus] > {query}\n")
    print(await ask(runner, USER_ID, session.id, query))


if __name__ == "__main__":
    # Fail early and readably instead of a cloud 403 or a traceback.
    check_auth_or_exit(needs_project=True)
    query = " ".join(sys.argv[1:]) or (
        "Is checkout healthy? What's its error rate?"
    )
    asyncio.run(main(query))
