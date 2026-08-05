"""Skill Registry access and the ADK skill toolset for Nimbus.

A skill is a versioned, semantically searchable capability package, a
`SKILL.md` file plus optional scripts and resources, that an agent can
discover and load on demand. That keeps the base prompt small while extending
what the agent can do.

This module has two sides. The management side packages a local skill
directory and registers, lists, retrieves or deletes it in the Agent Platform
Skill Registry through `agentplatform.Client().skills`, where `create` and
`delete` are long-running operations. The consumption side gives Nimbus a
`SkillToolset(registry=GCPSkillRegistry(...))` so that at runtime it can call
SearchSkills, then LoadSkill, then RunSkillScript, which is dynamic capability
loading. Semantic governance policies can intercept those calls.

Verified against `agentplatform` (SDK, 2026-07-17) and `google-adk` 2.4.0.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from ..env import resource_location as _env_resource_location
from ..env import require_project

# The packaged skill that ships with this lab is a Cymbal ops
# incident-triage runbook.
DEFAULT_SKILL_ID = "cymbal-ops-runbook"
DEFAULT_SKILL_DISPLAY_NAME = "cymbal-ops-runbook"
DEFAULT_SKILL_DESCRIPTION = (
    "Incident-triage runbook for Cymbal Cloud services: assess health, "
    "classify error-rate severity, and decide next steps and escalation."
)

# The skill lives at lab_root/skills/<id>. This file sits at
# src/nimbus/agent/skills.py, so the lab root is three directories up.
_LAB_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
DEFAULT_SKILL_PATH = os.path.join(_LAB_ROOT, "skills", DEFAULT_SKILL_ID)


@dataclass
class SkillInfo:
    """One skill as the Skill Registry reports it.

    Attributes:
        name: Full resource name of the registered skill.
        display_name: Human-readable name shown in the registry.
        description: What the skill does; this is what semantic search reads.
    """

    name: str
    display_name: str
    description: str


def _project() -> str:
    """Returns the GCP project that hosts the Skill Registry.

    There is no default. An unset `GOOGLE_CLOUD_PROJECT` raises with
    instructions instead of silently targeting somebody else's project.
    """
    return require_project()


def _location() -> str:
    """Returns the location of the Skill Registry.

    The registry is a managed regional resource, so it reads
    `$GOOGLE_CLOUD_AGENT_ENGINE_LOCATION` and not `$GOOGLE_CLOUD_LOCATION`
    (which points at the model endpoint and defaults to `global`). It falls
    back to `$GOOGLE_CLOUD_LOCATION` when that is a real region.
    """
    return _env_resource_location()


class SkillAdmin:
    """Admin surface over the Skill Registry.

    Registers, lists, retrieves and deletes skills through the
    `agentplatform` SDK. The underlying client is created on first use.
    """

    def __init__(self, project: str | None = None, location: str | None = None):
        """Initializes the instance with the registry coordinates.

        Args:
            project: GCP project holding the Skill Registry. Defaults to
                `$GOOGLE_CLOUD_PROJECT`, which has no fallback and is
                resolved lazily, on the first registry call.
            location: Registry location. Defaults to
                `$GOOGLE_CLOUD_AGENT_ENGINE_LOCATION` (falling back to
                `$GOOGLE_CLOUD_LOCATION` if regional, else `us-central1`).
        """
        self._project = project
        self.location = location or _location()
        self._client = None

    @property
    def project(self) -> str:
        """The GCP project holding the Skill Registry.

        Resolved on read, not in `__init__`, so building a `SkillAdmin`
        stays offline.
        """
        return self._project or _project()

    @property
    def client(self) -> Any:
        """The `agentplatform.Client` for this project, created on demand."""
        if self._client is None:
            # Deferred: the SDK is only needed once a registry call is made.
            import agentplatform

            self._client = agentplatform.Client(
                project=self.project,
                location=self.location,
            )
        return self._client

    def register(
        self,
        local_path: str = DEFAULT_SKILL_PATH,
        skill_id: str = DEFAULT_SKILL_ID,
        display_name: str = DEFAULT_SKILL_DISPLAY_NAME,
        description: str = DEFAULT_SKILL_DESCRIPTION,
    ) -> Any:
        """Creates a skill from a local directory (auto-zipped).

        Args:
            local_path: Directory holding the `SKILL.md` plus any scripts or
                resources; the SDK zips it for you.
            skill_id: Registry ID for the skill. Immutable once created.
            display_name: Human-readable name shown in the registry.
            description: What the skill does; drives semantic search.

        Returns:
            The long-running operation created for the call.
        """
        return self.client.skills.create(
            skill_id=skill_id,
            display_name=display_name,
            description=description,
            config={"local_path": local_path},
        )

    def list(self) -> list[SkillInfo]:
        """Returns every skill registered in this project and location."""
        return [
            SkillInfo(
                name=getattr(skill, "name", ""),
                display_name=getattr(skill, "display_name", ""),
                description=getattr(skill, "description", ""),
            )
            for skill in self.client.skills.list()
        ]

    def retrieve(self, query: str, top_k: int = 5) -> Any:
        """Runs a semantic search over the registered skills.

        This is the same lookup the agent makes when it discovers a
        capability at runtime.

        Args:
            query: Natural-language description of the capability wanted.
            top_k: Maximum number of skills to return.

        Returns:
            The registry's retrieve response.
        """
        return self.client.skills.retrieve(query=query, config={"top_k": top_k})

    def delete(self, name: str) -> Any:
        """Deletes a registered skill.

        Args:
            name: Full resource name of the skill, as reported by `list`.

        Returns:
            The long-running operation created for the call.
        """
        return self.client.skills.delete(name=name)


def resolve_skill_toolset(
    project: str | None = None,
    location: str | None = None,
) -> Any:
    """Builds an ADK `SkillToolset` backed by the GCP Skill Registry.

    Equips the agent with the skill lifecycle tools SearchSkills,
    ListSkills, LoadSkill, LoadSkillResource and RunSkillScript, so it can
    discover and load registry skills at runtime. Construction is lazy and
    makes no network calls. Tool execution reads the registry.

    Args:
        project: GCP project holding the Skill Registry. Defaults to
            `$GOOGLE_CLOUD_PROJECT`, which has no fallback and is
            resolved lazily, when a registry tool is actually called.
        location: Registry location. Defaults to
            `$GOOGLE_CLOUD_AGENT_ENGINE_LOCATION`
            (falling back to `us-central1`).

    Returns:
        A `google.adk.tools.skill_toolset.SkillToolset`. Typed as `Any`
        because the ADK imports below stay deferred.
    """
    # Deferred so importing this module does not pull in the registry
    # integration.
    from google.adk.integrations.skill_registry.gcp_skill_registry import (
        GCPSkillRegistry,
    )
    from google.adk.tools.skill_toolset import SkillToolset

    # A truthy placeholder so the base constructor's validation passes
    # with no project set. It never reaches a request: the `project_id`
    # property below raises the actionable error first.
    _DEFERRED = "<GOOGLE_CLOUD_PROJECT-not-set>"

    class LazyProjectSkillRegistry(GCPSkillRegistry):
        """A `GCPSkillRegistry` that resolves the project lazily.

        This lab builds `root_agent` at import time and the offline
        tests import it with no project set, so construction must stay
        offline. The project is demanded on first read, which is the
        first real registry call, and the error says what to export.
        """

        def __init__(self, *, project_id: str | None = None, **kwargs: Any):
            super().__init__(project_id=project_id or _DEFERRED, **kwargs)
            self._project_id = project_id or ""

        @property
        def project_id(self) -> str:
            """The GCP project, resolved on first use."""
            resolved = getattr(self, "_project_id", None)
            if resolved:
                return resolved
            if resolved is None:
                # Still inside the base constructor.
                return _DEFERRED
            return require_project()

        @project_id.setter
        def project_id(self, value: str) -> None:
            # The base constructor assigns here; the property above is
            # the source of truth afterwards.
            pass

    registry = LazyProjectSkillRegistry(
        project_id=project,
        location=location or _location(),
    )
    return SkillToolset(registry=registry)
