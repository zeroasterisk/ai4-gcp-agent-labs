"""Manage the Cymbal ops skill in the Skill Registry.

The `register` sub-command adds the skill to the registry, `list` prints
what the registry holds, and `retrieve` shows the skills that match a
natural-language query.

    export GOOGLE_CLOUD_PROJECT=your-project-id GOOGLE_CLOUD_LOCATION=global
    uv run --no-project --python ../../.venv/bin/python skill_admin.py register
    uv run --no-project --python ../../.venv/bin/python skill_admin.py list
    uv run --no-project --python ../../.venv/bin/python skill_admin.py retrieve "how do I triage a checkout incident"
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Imported after the sys.path bootstrap above, hence the E402 waiver.
from nimbus.env import bootstrap, check_auth_or_exit  # noqa: E402

# Load .env (this lab's, then the repo root's) and settle the auth mode
# BEFORE the agent modules are imported: they read GEMINI_MODEL and the
# project at import time. Real environment variables always win.
bootstrap(__file__)

from nimbus.agent.skills import (  # noqa: E402
    DEFAULT_SKILL_ID,
    DEFAULT_SKILL_PATH,
    SkillAdmin,
)


def main() -> None:
    """Runs the sub-command in `sys.argv[1]`, defaulting to `list`.

    Raises:
        SystemExit: If the sub-command is not register, list or retrieve.
    """
    command = sys.argv[1] if len(sys.argv) > 1 else "list"
    admin = SkillAdmin()

    if command == "register":
        print(
            f"Registering skill '{DEFAULT_SKILL_ID}' "
            f"from {DEFAULT_SKILL_PATH} ..."
        )
        try:
            operation = admin.register()
        except Exception as err:  # noqa: BLE001 - 409 is an expected re-run
            if "ALREADY_EXISTS" not in str(err):
                raise
            print(
                f"  '{DEFAULT_SKILL_ID}' is already registered - nothing to do."
                "\n  Skill IDs are immutable, and stay reserved for 24 hours"
                " after a delete."
                "\n  Carry on with: python skill_admin.py list"
            )
            return
        print(
            "  submitted (long-running): "
            f"{getattr(operation, 'name', operation)}"
        )
    elif command == "list":
        skills = admin.list()
        print(f"skills in registry: {len(skills)}")
        for skill in skills:
            print(f"  - {skill.display_name}  ({skill.name})")
            if skill.description:
                print(f"      {skill.description}")
    elif command == "retrieve":
        query = " ".join(sys.argv[2:]) or "triage a Cymbal service incident"
        print(f"retrieve: {query!r}")
        response = admin.retrieve(query)
        for retrieved in getattr(response, "retrieved_skills", []) or []:
            skill_name = getattr(retrieved, "skill_name", "?")
            description = getattr(retrieved, "description", "")
            print(f"  - {skill_name}: {description}")
    else:
        raise SystemExit(
            "usage: skill_admin.py [register|list|retrieve <query>]"
        )


if __name__ == "__main__":
    # Fail early and readably instead of a cloud 403 or a traceback.
    check_auth_or_exit(needs_project=True)
    main()
