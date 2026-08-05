"""Live test that queries the deployed Nimbus on Agent Runtime.

This test needs deploy.py to have run first, because that is what writes the
.agent_engine marker file. It is skipped unless RUN_LIVE is set to 1.
"""

from __future__ import annotations

import asyncio
import os
import pathlib

import pytest

RUN_LIVE = os.environ.get("RUN_LIVE") == "1"
_LAB_ROOT = pathlib.Path(__file__).resolve().parents[1]
_NAME_FILE = _LAB_ROOT / ".agent_engine"

pytestmark = pytest.mark.skipif(
    not RUN_LIVE or not _NAME_FILE.exists(),
    reason="set RUN_LIVE=1 and deploy first (deploy.py writes .agent_engine)",
)


def test_deployed_agent_answers():
    # No default project: a live test must never touch somebody
    # else's project, so skip instead of guessing.
    if not os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip():
        pytest.skip("set GOOGLE_CLOUD_PROJECT to run live tests")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
    import vertexai

    name = _NAME_FILE.read_text().strip()
    client = vertexai.Client(
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ["GOOGLE_CLOUD_LOCATION"],
    )
    remote = client.agent_engines.get(name=name)

    async def run() -> str:
        final = ""
        async for event in remote.async_stream_query(
            user_id="test-user",
            message="Is checkout healthy? Give the error rate.",
        ):
            parts = (
                (event.get("content") or {}).get("parts", [])
                if isinstance(event, dict)
                else []
            )
            for part in parts:
                if isinstance(part, dict) and part.get("text"):
                    final = part["text"]
        return final

    text = asyncio.run(run())
    lowered = text.lower()
    assert "4.7" in text or "degrad" in lowered, (
        f"deployed agent not grounded: {text!r}"
    )
