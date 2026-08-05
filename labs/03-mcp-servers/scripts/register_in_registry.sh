#!/usr/bin/env bash
# Register the deployed ops MCP server in Google Cloud Agent Registry (global) via REST.
#
# Uses REST rather than `gcloud agent-registry services create`, for two reasons:
#   - MCP-over-HTTP has to be registered as JSONRPC, not HTTP_JSON, and gcloud
#     sends HTTP_JSON.
#   - the tool spec must carry a full `inputSchema` per tool.
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT="${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT is not set — export it, e.g. export GOOGLE_CLOUD_PROJECT=your-project-id}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE="${OPS_MCP_SERVICE:-cymbal-ops-mcp}"
REG_LOCATION="${REGISTRY_LOCATION:-global}"   # MCP registration unsupported in us/eu multi-region

URL=$(gcloud run services describe "${SERVICE}" --region "${REGION}" --project "${PROJECT}" --format='value(status.url)')
echo "Registering ${SERVICE} -> ${URL}/mcp/ in Agent Registry (${REG_LOCATION})..."

BODY=$(python3 - "${URL}" <<'PY'
import json, sys
content = json.load(open("mcp_server/toolspec.json"))
url = sys.argv[1].rstrip("/") + "/mcp/"
print(json.dumps({
    "displayName": "cymbal-ops-mcp",
    "description": "Cymbal Ops tools (service health / error rate) served over MCP.",
    "interfaces": [{"protocolBinding": "JSONRPC", "url": url}],
    "mcpServerSpec": {"type": "TOOL_SPEC", "content": content},
}))
PY
)

RESP=$(mktemp)
CODE=$(curl -sS -o "${RESP}" -w '%{http_code}' -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "X-Goog-User-Project: ${PROJECT}" \
  -H "Content-Type: application/json" \
  -d "${BODY}" \
  "https://agentregistry.googleapis.com/v1/projects/${PROJECT}/locations/${REG_LOCATION}/services?serviceId=${SERVICE}")
cat "${RESP}"; rm -f "${RESP}"; echo
if [ "${CODE}" -lt 200 ] || [ "${CODE}" -ge 300 ]; then
  echo
  echo "REGISTRATION FAILED (HTTP ${CODE}). The agent will fall back to OPS_MCP_URL"
  echo "or the .ops_mcp_url marker, so the lab still runs - but nothing was catalogued."
  exit 1
fi
echo "Submitted. Projection into the read-only mcpServers list takes ~1 minute."
echo "Verify:"
echo "  curl -sS -H \"Authorization: Bearer \$(gcloud auth print-access-token)\" \\"
echo "    -H \"X-Goog-User-Project: ${PROJECT}\" \\"
echo "    https://agentregistry.googleapis.com/v1/projects/${PROJECT}/locations/${REG_LOCATION}/services"
