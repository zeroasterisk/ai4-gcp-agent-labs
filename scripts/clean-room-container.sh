#!/usr/bin/env bash
# Hermetic attendee simulation in a container. Stronger than scripts/clean-room.sh:
# no host filesystem, no host env, no gcloud, no caches, no /etc/pip.conf.
#
#   ./scripts/clean-room-container.sh [git-ref] [extra podman args...]
#
# Credentials are NOT baked in. To exercise the live model call, pass them through:
#   ./scripts/clean-room-container.sh main -e GOOGLE_API_KEY="$GOOGLE_API_KEY"
#   ./scripts/clean-room-container.sh main \
#       -v /path/to/sa-key.json:/creds.json:ro,Z \
#       -e GOOGLE_APPLICATION_CREDENTIALS=/creds.json \
#       -e GOOGLE_CLOUD_PROJECT=your-project-id -e GOOGLE_CLOUD_LOCATION=global
#
# Requires podman (docker is not used). Nothing is written outside the container.
set -uo pipefail
REF="${1:-main}"; shift || true
podman run --rm -i --unsetenv-all \
  -e HOME=/root -e PATH=/usr/local/bin:/usr/bin:/bin -e TERM=xterm \
  -e LANG=C.UTF-8 -e AI4_REF="$REF" \
  "$@" \
  docker.io/library/python:3.12-slim bash -s <<'INNER'
set -e
echo "### environment an attendee actually has ###"
env | grep -iE 'GOOGLE|GEMINI|CLOUDSDK|UV_|PIP_' || echo "  (no cloud/index env - correct)"
command -v gcloud >/dev/null && echo "  gcloud: PRESENT" || echo "  gcloud: absent (expected)"
echo
apt-get -qq update >/dev/null 2>&1 && apt-get -qq install -y git curl ca-certificates >/dev/null 2>&1
echo "### install uv the way the README says ###"
curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
export PATH="/root/.local/bin:$PATH"
uv --version
echo
echo "### clone at ${AI4_REF} ###"
git clone -q --depth 1 --branch "${AI4_REF}" https://github.com/zeroasterisk/ai4-gcp-agent-labs /w 2>/dev/null \
  || git clone -q --depth 1 https://github.com/zeroasterisk/ai4-gcp-agent-labs /w
cd /w && git log --oneline -1
echo
echo "### follow the README: uv venv + install lab 01 ###"
cd /w/labs/01-adk
time uv venv .venv >/dev/null 2>&1
time uv pip install -r requirements.txt >/dev/null 2>&1 || { echo "INSTALL FAILED"; exit 1; }
echo "install OK"
echo
echo "### check_prereqs.py with NOTHING configured ###"
cd /w && ./labs/01-adk/.venv/bin/python check_prereqs.py --lab 01 || true
INNER
