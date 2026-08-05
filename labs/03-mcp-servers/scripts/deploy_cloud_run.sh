#!/usr/bin/env bash
# Deploy the Cymbal Ops MCP server to Cloud Run.
#
# Deployed with --allow-unauthenticated to keep the lab short. Do not do that
# with a real tool server.
set -euo pipefail

# Resolve the lab root BEFORE changing directory: $0 may be relative, so
# dirname "$0" stops being meaningful once we cd.
LAB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${LAB_ROOT}/mcp_server"

PROJECT="${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT is not set - export it, e.g. export GOOGLE_CLOUD_PROJECT=your-project-id}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE="${OPS_MCP_SERVICE:-cymbal-ops-mcp}"

echo "Deploying ${SERVICE} to Cloud Run (${REGION}, project ${PROJECT})..."
# OTEL_TRACING=1 makes the server export spans to Cloud Trace and continue the
# caller's W3C trace, so the agent and the tool server share one trace.
gcloud run deploy "${SERVICE}" \
  --source . \
  --region "${REGION}" \
  --project "${PROJECT}" \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT},OTEL_TRACING=1" \
  --quiet

URL=$(gcloud run services describe "${SERVICE}" --region "${REGION}" --project "${PROJECT}" --format='value(status.url)')
echo "Deployed. MCP endpoint: ${URL}/mcp/   (keep the trailing slash)"

# The agent reads this marker to build its toolset without a network call.
# export OPS_MCP_URL=... overrides it.
echo "${URL}/mcp/" > "${LAB_ROOT}/.ops_mcp_url"
echo "Wrote ${LAB_ROOT}/.ops_mcp_url"
