#!/usr/bin/env bash
# Remove everything the labs created. Safe to run at any point: it checks each
# resource and skips whatever is not there, so a partial run, a full run and a
# second run all behave.
#
#   bash scripts/teardown.sh
#
# Only labs 03 and 04 create anything billable. Lab 01 is entirely local, and
# lab 02's registry entry costs nothing (it is left alone - deleting a skill
# reserves its ID for 24 hours, which only gets in your way if you re-run).
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"

PROJECT="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
if [ -z "${PROJECT}" ] || [ "${PROJECT}" = "(unset)" ]; then
  echo "GOOGLE_CLOUD_PROJECT is not set and gcloud has no default project."
  echo "  export GOOGLE_CLOUD_PROJECT=your-project-id"
  exit 1
fi
REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE="${OPS_MCP_SERVICE:-cymbal-ops-mcp}"
REG_LOCATION="${REGISTRY_LOCATION:-global}"
FOUND=0
FAILED=0

echo "Tearing down in project ${PROJECT}"
echo

# --- Lab 04: Agent Engine (billed for as long as it exists) -----------------
if [ -n "${AGENT_ENGINE_NAME:-}" ] || [ -f "${REPO}/labs/04-deployments/.agent_engine" ]; then
  FOUND=1
  echo "Lab 04: deleting the Agent Engine deployment..."
  ( cd "${REPO}/labs/04-deployments" && python delete_deployed.py ) \
    || { FAILED=1; echo "  could not delete it - check it by hand in the console"; }
else
  echo "Lab 04: no deployment found, skipping."
fi

# --- Lab 03: Cloud Run + registry entry + the built image -------------------
if gcloud run services describe "${SERVICE}" --region "${REGION}" --project "${PROJECT}" \
     --format='value(name)' >/dev/null 2>&1; then
  FOUND=1
  echo "Lab 03: deleting the Cloud Run service ${SERVICE}..."
  gcloud run services delete "${SERVICE}" --region "${REGION}" --project "${PROJECT}" --quiet \
    || { FAILED=1; echo "  delete failed - check it by hand"; }
else
  echo "Lab 03: no Cloud Run service, skipping."
fi

CODE=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE \
  -H "Authorization: Bearer $(gcloud auth print-access-token 2>/dev/null)" \
  -H "X-Goog-User-Project: ${PROJECT}" \
  "https://agentregistry.googleapis.com/v1/projects/${PROJECT}/locations/${REG_LOCATION}/services/${SERVICE}" \
  2>/dev/null)
case "${CODE}" in
  200|204) FOUND=1; echo "Lab 03: removed the Agent Registry entry." ;;
  404)     echo "Lab 03: no Agent Registry entry, skipping." ;;
  401|403) FAILED=1
           echo "Lab 03: NOT removed - the registry rejected the call (HTTP ${CODE})."
           echo "        Delete it by hand, or it stays in the catalogue." ;;
  *)       FAILED=1
           echo "Lab 03: registry delete returned HTTP ${CODE:-none} - check by hand." ;;
esac

# The image is the part that keeps costing after the service is gone.
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/cloud-run-source-deploy/${SERVICE}"
if [ -n "$(gcloud artifacts docker images list "${IMAGE}" --project "${PROJECT}" \
            --format='value(IMAGE)' 2>/dev/null)" ]; then
  FOUND=1
  echo "Lab 03: deleting the container image (Artifact Registry storage)..."
  gcloud artifacts docker images delete "${IMAGE}" --delete-tags --quiet --project "${PROJECT}" \
    >/dev/null 2>&1 || { FAILED=1; echo "  delete failed - check it by hand"; }
else
  echo "Lab 03: no container image, skipping."
fi

rm -f "${REPO}/labs/03-mcp-servers/.ops_mcp_url" "${REPO}/labs/04-deployments/.agent_engine"

echo
if [ "${FAILED}" -ne 0 ]; then
  echo "Finished WITH ERRORS - some resources above were not removed."
  echo "They may still be billing. Check them in the console."
  exit 1
elif [ "${FOUND}" -eq 0 ]; then
  echo "Nothing to remove - no billable resources from these labs exist."
else
  echo "Done. Nothing from the labs is still running."
fi
