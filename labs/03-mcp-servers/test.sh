#!/usr/bin/env bash
# Test runner. The offline tests always run. The live tests run only when
# RUN_LIVE is set to 1, and they need the server deployed and registered by
#   ./scripts/deploy_cloud_run.sh && ./scripts/register_in_registry.sh
set -euo pipefail
cd "$(dirname "$0")"

# ---------------------------------------------------------------------------
# Preflight. STEP 1 of this lab is installing ITS OWN requirements.txt, so say
# so plainly instead of letting pytest dump an ImportError traceback.
# ---------------------------------------------------------------------------
echo "Checking this lab's dependencies"
python - <<'PY' || exit 1
import warnings
warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\].*")
warnings.filterwarnings("ignore", message=r".*is deprecated.*")
import importlib
import importlib.util
import sys

# Import name -> the requirements.txt entry it comes from.
REQUIRED = {
    "google.adk": "google-adk",
    "google.adk.tools.skill_toolset": "google-adk",
    "vertexai": "google-cloud-aiplatform",
    "agentplatform": "google-cloud-aiplatform",
    "mcp": "mcp",
    "pydantic": "pydantic",
    "starlette": "starlette",
    "uvicorn": "uvicorn",
    "pytest": "pytest",
}
# These must really import, not just resolve: they are what the declared
# extras provide.
MUST_IMPORT = {
    "google.adk.integrations.agent_registry": "google-adk[agent-identity,a2a]",
}

missing = []
for module, dist in REQUIRED.items():
    try:
        found = importlib.util.find_spec(module) is not None
    except Exception:
        found = False
    if not found:
        missing.append(f"{module}  (from {dist})")
for module, dist in MUST_IMPORT.items():
    try:
        importlib.import_module(module)
    except Exception as err:
        missing.append(f"{module}  (from {dist}): {err}")

if missing:
    print()
    print("ERROR: this lab's dependencies are missing from the Python you are")
    print(f"using: {sys.executable}")
    for item in missing:
        print(f"    - {item}")
    print()
    print("Install THIS LAB's requirements first, from this lab directory:")
    print("    uv venv .venv")
    print("    source .venv/bin/activate")
    print("    uv pip install -r requirements.txt")
    print()
    sys.exit(1)
PY

echo "Compiling the sources"
python -m py_compile run_local.py demo.py skill_admin.py mcp_server/*.py $(find src/nimbus -name '*.py')

echo "Importing root_agent offline to prove construction makes no network call"
python -c "import sys; sys.path.insert(0, 'src'); import nimbus; import nimbus.agent as a; assert a.root_agent.name == 'nimbus'; print('root_agent built offline OK')"

echo "Running the offline tests"
python -m pytest tests/test.py


if [[ "${RUN_LIVE:-0}" == "1" ]]; then
  : "${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT is not set — export it, e.g. export GOOGLE_CLOUD_PROJECT=your-project-id}"
  echo "Running the live tests that reach the server through the Agent Registry"
  python -m pytest tests/test_live.py
else
  echo "Skipping the live tests. Set RUN_LIVE=1 once the server is deployed and registered."
fi

echo "ALL PASSED"
