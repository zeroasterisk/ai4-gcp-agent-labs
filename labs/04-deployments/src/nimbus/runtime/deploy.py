"""Deploy the Nimbus graph to the managed Agent Runtime.

The graph is the ADK `Workflow` returned by `build_root_agent()`. It loads
history, investigates with the managed MCP tools and the managed skills,
analyzes findings by running code, then reports. This module ships that
whole workflow, not a flattened single agent, and turns tracing and
telemetry on.

Packaging has to survive cloudpickle, which otherwise fails to deploy with
"No module named nimbus". Two things guard against that. The whole
`nimbus` package travels as source through
`extra_packages=["src/nimbus"]`, the agent template approach, so the
engine can import nimbus. On top of that,
`cloudpickle.register_pickle_by_value(...)` is called for every nimbus
module the pickled graph references, namely the `load_history` function
node in nimbus.agent.agent and the `auto_save_memories` callback in
nimbus.harness.memory_manager, so the graph unpickles by value even when
the import by reference fails.

Managed toolsets are resolved at build time and travel with the app.
Sessions, memory and code execution all stay inside the engine.

    # export OPS_MCP_URL=<cloud-run-mcp-url> first so the real endpoint is
    # baked into the graph. Writes ../../../.agent_engine on success.
    python -m nimbus.runtime.deploy      # from the lab root
"""

from __future__ import annotations

import os
from importlib.metadata import version as _version
from typing import Any

import cloudpickle
import vertexai
from vertexai.agent_engines import AdkApp

# The pickled graph reaches into these modules, so they travel by value.
from .. import env as env_module
from ..agent import agent as agent_module
from ..agent import skills as skills_module
from ..agent.agent import build_root_agent
from ..env import location as model_location
from ..env import resource_location as _location
from ..env import require_project
from ..harness import memory_manager as memory_module

# Ship the graph's custom code by value so the engine can unpickle it
# without importing nimbus.
for _pickled_module in (
    agent_module,
    skills_module,
    memory_module,
    env_module,
):
    cloudpickle.register_pickle_by_value(_pickled_module)


def _staging_bucket() -> str:
    """Returns `$STAGING_BUCKET`, or the per-project default bucket."""
    return os.environ.get("STAGING_BUCKET") or (
        f"gs://{require_project()}-nimbus-agents"
    )


NAME_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", ".agent_engine"
)

# Pinned to the versions installed here: the engine unpickles the graph
# with the same stack it was pickled against.
REQUIREMENTS = [
    "google-cloud-aiplatform[adk,agent_engines]==%s" % _version(
        "google-cloud-aiplatform"
    ),
    "google-adk==%s" % _version("google-adk"),
    "mcp==%s" % _version("mcp"),
    "pydantic",
    "cloudpickle",
]


def _resource_name(remote: Any) -> str:
    """Returns the resource name carried by a deployed engine handle."""
    api = getattr(remote, "api_resource", None)
    return getattr(api, "name", None) or getattr(remote, "name", "")


def _existing_name() -> str | None:
    """Returns the name of an already-deployed engine, or None."""
    name = os.environ.get("AGENT_ENGINE_NAME")
    if not name and os.path.exists(NAME_FILE):
        with open(NAME_FILE) as f:
            name = f.read().strip()
    return name or None


def deploy() -> str:
    """Deploys (or updates) the Nimbus graph on Agent Runtime.

    Writes the resulting resource name to `.agent_engine` at the lab root
    so that `client.py` can find the engine.

    Returns:
        The `reasoningEngine` resource name of the deployed graph.
    """
    os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "True")
    # No default project: this raises with instructions if
    # GOOGLE_CLOUD_PROJECT is unset, rather than deploying somewhere
    # unexpected.
    project = require_project()
    location = _location()
    client = vertexai.Client(project=project, location=location)
    # Deploy the graph itself, the Workflow returned by
    # build_root_agent(), not a flattened single agent.
    app = AdkApp(agent=build_root_agent(), enable_tracing=True)
    env_vars = {
        "GOOGLE_GENAI_USE_ENTERPRISE": "True",
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "REGISTRY_LOCATION": os.environ.get("REGISTRY_LOCATION", "global"),
        # The MODEL location, which is not the engine's region. The engine runs
        # in us-central1; gemini-flash-latest is only served from `global`.
        # Without this the deployed graph 404s on its first model call:
        #   Publisher model .../locations/us-central1/.../gemini-flash-latest
        #   was not found
        "GOOGLE_CLOUD_LOCATION": model_location(),
    }
    if os.environ.get("GEMINI_MODEL"):
        env_vars["GEMINI_MODEL"] = os.environ["GEMINI_MODEL"]
    if os.environ.get("OPS_MCP_URL"):
        env_vars["OPS_MCP_URL"] = os.environ["OPS_MCP_URL"]
    config = {
        "staging_bucket": _staging_bucket(),
        "requirements": REQUIREMENTS,
        # Ship nimbus as source as well, so the engine can import it.
        "extra_packages": ["src/nimbus"],
        "display_name": "nimbus",
        "description": (
            "Cymbal Cloud Ops Copilot graph — managed skills + MCP, local"
            " code (Lab 04 runtime migration)."
        ),
        "env_vars": env_vars,
    }
    existing = _existing_name()
    if existing:
        print(f"Updating {existing} (update can be unreliable; prefer create + delete) ...")
        remote = client.agent_engines.update(
            name=existing, agent=app, config=config
        )
    else:
        print(
            "Deploying the Nimbus graph to Agent Runtime in"
            f" {project}/{location} (a few minutes) ..."
        )
        remote = client.agent_engines.create(agent=app, config=config)
    name = _resource_name(remote) or existing
    with open(NAME_FILE, "w") as f:
        f.write(name)
    print(f"DEPLOYED: {name}")
    return name


if __name__ == "__main__":
    deploy()
