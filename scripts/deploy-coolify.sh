#!/usr/bin/env bash
# Deploy to Coolify via API webhook
# Usage: ./scripts/deploy-coolify.sh [--force]
#
# Required env vars (set in .env.coolify or export):
#   COOLIFY_HOST        — your Coolify instance URL (e.g. http://89.167.116.18:8000)
#   COOLIFY_API_TOKEN   — API token with Deploy permission
#   COOLIFY_APP_UUID    — application UUID from Coolify dashboard
#
set -euo pipefail

# Load env from .env.coolify if it exists
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env.coolify"
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

# Validate required vars
for var in COOLIFY_HOST COOLIFY_API_TOKEN COOLIFY_APP_UUID; do
  if [ -z "${!var:-}" ]; then
    echo "ERROR: $var is not set."
    echo "Create .env.coolify with: COOLIFY_HOST, COOLIFY_API_TOKEN, COOLIFY_APP_UUID"
    echo "Or export them before running this script."
    exit 1
  fi
done

FORCE="false"
if [ "${1:-}" = "--force" ]; then
  FORCE="true"
fi

echo "Deploying to Coolify..."
echo "  Host: $COOLIFY_HOST"
echo "  App:  $COOLIFY_APP_UUID"
echo "  Force: $FORCE"

RESPONSE=$(curl --silent --fail --show-error \
  --request GET \
  "${COOLIFY_HOST}/api/v1/deploy?uuid=${COOLIFY_APP_UUID}&force=${FORCE}" \
  --header "Authorization: Bearer ${COOLIFY_API_TOKEN}" \
  --header "Accept: application/json" \
  2>&1) || {
    echo "ERROR: Deploy request failed."
    echo "$RESPONSE"
    exit 1
  }

echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# Extract deployment UUID for status polling
DEPLOY_UUID=$(echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
deps = data.get('deployments', [])
if deps:
    print(deps[0].get('deployment_uuid', ''))
" 2>/dev/null || true)

if [ -n "$DEPLOY_UUID" ]; then
  echo ""
  echo "Deployment queued: $DEPLOY_UUID"
  echo "Check status: ${COOLIFY_HOST}/api/v1/deployments/${DEPLOY_UUID}"
  echo ""
  echo "Polling for completion (Ctrl+C to stop)..."

  for i in $(seq 1 40); do
    sleep 15
    STATUS=$(curl --silent \
      "${COOLIFY_HOST}/api/v1/deployments/${DEPLOY_UUID}" \
      --header "Authorization: Bearer ${COOLIFY_API_TOKEN}" \
      --header "Accept: application/json" 2>/dev/null || echo '{}')

    STATE=$(echo "$STATUS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('status', 'unknown'))
" 2>/dev/null || echo "unknown")

    echo "  [${i}/40] Status: $STATE ($(( i * 15 ))s elapsed)"

    case "$STATE" in
      finished|running)
        echo ""
        echo "Deploy complete."
        exit 0
        ;;
      failed|cancelled)
        echo ""
        echo "ERROR: Deploy $STATE."
        echo "$STATUS" | python3 -m json.tool 2>/dev/null || echo "$STATUS"
        exit 1
        ;;
    esac
  done

  echo ""
  echo "TIMEOUT: Deploy still in progress after 10 minutes."
  echo "Check Coolify dashboard: ${COOLIFY_HOST}"
  exit 1
else
  echo ""
  echo "Deploy triggered (could not extract deployment UUID for polling)."
  echo "Check Coolify dashboard: ${COOLIFY_HOST}"
fi
