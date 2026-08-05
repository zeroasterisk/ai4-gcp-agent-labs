"""Deploy Nimbus to Agent Runtime.

A thin wrapper around `nimbus.runtime.deploy`.

    export GOOGLE_GENAI_USE_ENTERPRISE=True GOOGLE_CLOUD_PROJECT=your-project-id \
           GOOGLE_CLOUD_LOCATION=global \
           GOOGLE_CLOUD_AGENT_ENGINE_LOCATION=us-central1 \
           REGISTRY_LOCATION=global
    python deploy.py     # ~10 min; writes .agent_engine (create; updates in place if it exists)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Imported after the sys.path bootstrap above, hence the E402 waiver.
from nimbus.env import bootstrap, check_auth_or_exit  # noqa: E402

# Load .env (this lab's, then the repo root's) and settle the auth mode
# BEFORE the agent modules are imported: they read GEMINI_MODEL and the
# project at import time. Real environment variables always win.
bootstrap(__file__)

from nimbus.runtime.deploy import deploy  # noqa: E402

if __name__ == "__main__":
    # Fail early and readably instead of a cloud 403 or a traceback.
    check_auth_or_exit(needs_project=True)
    deploy()
