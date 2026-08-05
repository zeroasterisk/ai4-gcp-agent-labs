"""Delete the deployed Nimbus (Agent Runtime) to stop billing.

Run this only when you are done with the deployment. Bringing the agent back
means running the deploy script again.

    python delete_deployed.py
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

from nimbus.runtime import client  # noqa: E402

if __name__ == "__main__":
    # Fail early and readably instead of a cloud 403 or a traceback.
    check_auth_or_exit(needs_project=True)
    print("Deleted", client.delete_deployed())
