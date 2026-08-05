"""Nimbus, the Cymbal Cloud Ops Copilot.

The package follows the module organization in docs/_agent_template. The
`agent` package holds the graph, meaning the config, the prompts, the
schemas, the tools and the Workflow wiring. The `harness` package holds the
capability subsystems for sessions and memory. The `runtime` package is where
the graph runs, which here is the local process.

Sessions, memory, skills, the ops MCP server and the code executor all run
locally in this lab.
"""

# ADK emits [EXPERIMENTAL] UserWarnings and a BaseAgentConfig DeprecationWarning
# on almost every call. They are cosmetic, they scroll the real output off the
# screen, and in a workshop they read as errors. Set NIMBUS_SHOW_WARNINGS=1 to
# see them again.
import os as _os
import warnings as _warnings

if not _os.environ.get("NIMBUS_SHOW_WARNINGS"):
    _warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\].*")
    _warnings.filterwarnings("ignore", message=r".*BaseAgentConfig is deprecated.*")

# ADK logs a warning when it asks for mTLS and gets ordinary TLS. That is the
# normal case against Cloud Run and it is not actionable, so drop just that one
# message - the logger keeps reporting everything else.
import logging as _logging


class _DropMtlsNotice(_logging.Filter):
    def filter(self, record):
        return "channel is not mTLS" not in record.getMessage()


_logging.getLogger(
    "google_adk.google.adk.tools.mcp_tool.mcp_session_manager"
).addFilter(_DropMtlsNotice())

# Settle the auth mode as soon as anything imports `nimbus`, not just when an
# entry-point script runs. `adk web` and Agent Runtime import the agent module
# directly, so without this google-genai never learns it should use Vertex and
# fails with "No API key was provided". Loads `.env`, sets
# GOOGLE_GENAI_USE_ENTERPRISE, and requires nothing - project stays lazy.
try:
    from .env import bootstrap as _bootstrap

    _bootstrap(__file__)
except Exception:  # pragma: no cover - never let this break an import
    pass

# Best effort: importing `nimbus` must work without the agent's optional
# dependencies, so a failed import just skips the re-exports.
try:
    from .agent import build_root_agent, root_agent
    from .agent.config import AGENT_NAME, MODEL

    __all__ = ["build_root_agent", "root_agent", "AGENT_NAME", "MODEL"]
except Exception:  # pragma: no cover
    pass
