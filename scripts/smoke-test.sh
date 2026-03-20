#!/usr/bin/env bash
# smoke-test.sh — Post-deploy verification for CallLock
# Each check maps to a real incident. When a new class of bug burns you, add a check here.
#
# Usage:
#   RETELL_API_KEY=key_xxx HARNESS_URL=https://calllock-harness.onrender.com ./scripts/smoke-test.sh
#
# Env vars (reads from .env.local if present):
#   HARNESS_URL           — Render harness base URL (default: https://calllock-harness.onrender.com)
#   RETELL_API_KEY        — Retell API key for HMAC signing and agent config check
#   RETELL_AGENT_ID       — Retell agent ID (default: agent_4fb753a447e714064e71fadc6d)
#   RETELL_PHONE_NUMBER   — Retell phone number (default: +13126463816)

set -euo pipefail

# --- Load .env.local if present ---
ENV_FILE="${ENV_FILE:-web/.env.local}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    # Strip trailing whitespace and carriage returns
    value=$(printf '%s' "$value" | tr -d '\r\n')
    # Only set if not already defined (don't overwrite explicit env vars)
    [[ -z "${!key:-}" ]] && export "$key=$value" 2>/dev/null || true
  done < "$ENV_FILE"
  set +a
fi

HARNESS_URL="${HARNESS_URL:-https://calllock-harness.onrender.com}"
RETELL_API_KEY="${RETELL_API_KEY:-}"
RETELL_AGENT_ID="${RETELL_AGENT_ID:-agent_4fb753a447e714064e71fadc6d}"
RETELL_PHONE="${RETELL_PHONE_NUMBER:-+13126463816}"

PASS=0
FAIL=0
WARN=0

pass() { echo "  PASS  $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL  $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  WARN  $1"; WARN=$((WARN + 1)); }

echo "=== CallLock Smoke Test ==="
echo "Harness: $HARNESS_URL"
echo "Time:    $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# -------------------------------------------------------------------
# CHECK 1: Health endpoint (catches: cold start, missing env vars, dependency failures)
# Incident: 2026-03-19 — Render cold start caused Retell webhook timeout
# -------------------------------------------------------------------
echo "--- Check 1: Health endpoint ---"
HEALTH_STATUS=$(curl -s -o /tmp/smoke-health.json -w "%{http_code}" \
  --max-time 30 "$HARNESS_URL/health" 2>/dev/null) || HEALTH_STATUS="000"

if [[ "$HEALTH_STATUS" == "200" ]]; then
  STATUS=$(python3 -c "import json; print(json.load(open('/tmp/smoke-health.json')).get('status','unknown'))" 2>/dev/null || echo "unknown")
  if [[ "$STATUS" == "ok" ]]; then
    pass "Health endpoint returned 200 (status: ok)"
  else
    warn "Health returned 200 but status=$STATUS (degraded dependencies?)"
    cat /tmp/smoke-health.json 2>/dev/null
  fi
elif [[ "$HEALTH_STATUS" == "000" ]]; then
  fail "Health endpoint unreachable (cold start or service down)"
else
  fail "Health endpoint returned HTTP $HEALTH_STATUS"
fi
echo ""

# -------------------------------------------------------------------
# CHECK 2: Webhook auth (catches: HMAC signature format changes, missing RETELL_API_KEY)
# Incident: 2026-03-19 — HMAC format mismatch (v=ts,d=hex vs old format) broke all inbound calls
# -------------------------------------------------------------------
echo "--- Check 2: Webhook HMAC auth ---"
if [[ -z "$RETELL_API_KEY" ]]; then
  warn "RETELL_API_KEY not set — skipping webhook auth check"
elif [[ ${#RETELL_API_KEY} -lt 30 ]]; then
  fail "RETELL_API_KEY looks truncated (${#RETELL_API_KEY} chars) — get full key from Render env vars"
else
  BODY='{"call_id":"smoke-test-hmac","agent_id":"smoke-test","from_number":"+15551234567","to_number":"'"$RETELL_PHONE"'"}'
  TS_MS=$(python3 -c "import time; print(int(time.time()*1000))")
  SIG_DIGEST=$(printf '%s%s' "$BODY" "$TS_MS" | openssl dgst -sha256 -hmac "$RETELL_API_KEY" -hex 2>/dev/null | awk '{print $NF}')
  SIG_HEADER="v=${TS_MS},d=${SIG_DIGEST}"

  WEBHOOK_STATUS=$(curl -s -o /tmp/smoke-webhook.json -w "%{http_code}" \
    --max-time 15 \
    -X POST "$HARNESS_URL/webhook/retell/call-ended" \
    -H "Content-Type: application/json" \
    -H "x-retell-signature: $SIG_HEADER" \
    -d "$BODY" 2>/dev/null) || WEBHOOK_STATUS="000"

  if [[ "$WEBHOOK_STATUS" == "200" || "$WEBHOOK_STATUS" == "400" ]]; then
    pass "Call-ended webhook accepted HMAC signature (HTTP $WEBHOOK_STATUS)"
  elif [[ "$WEBHOOK_STATUS" == "401" || "$WEBHOOK_STATUS" == "403" ]]; then
    fail "Webhook rejected valid HMAC signature (HTTP $WEBHOOK_STATUS) — auth format may have changed"
  elif [[ "$WEBHOOK_STATUS" == "000" ]]; then
    fail "Webhook unreachable"
  else
    warn "Webhook returned unexpected HTTP $WEBHOOK_STATUS"
    cat /tmp/smoke-webhook.json 2>/dev/null
  fi
fi
echo ""

# -------------------------------------------------------------------
# CHECK 3: Retell agent config (catches: tool URLs pointing to wrong domain after migration)
# Incident: 2026-03-19 — Tool endpoints still pointed to old Vercel deployment after migration
# -------------------------------------------------------------------
echo "--- Check 3: Retell agent tool URLs ---"
if [[ -z "$RETELL_API_KEY" ]]; then
  warn "RETELL_API_KEY not set — skipping agent config check"
elif [[ ${#RETELL_API_KEY} -lt 30 ]]; then
  warn "RETELL_API_KEY truncated — skipping agent config check (fix key first)"
else
  AGENT_JSON=$(curl -s --max-time 15 \
    "https://api.retellai.com/get-agent/$RETELL_AGENT_ID" \
    -H "Authorization: Bearer $RETELL_API_KEY" 2>/dev/null || echo "{}")

  if echo "$AGENT_JSON" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
    # Check if any tool URLs point to unexpected domains
    BAD_URLS=$(echo "$AGENT_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
raw = json.dumps(data)
# Known good domains
good = ['calllock-harness.onrender.com', 'calllock-server.onrender.com']
import re
urls = re.findall(r'https?://([^/\"]+)', raw)
bad = [u for u in set(urls) if 'retellai.com' not in u and 'api.retellai.com' not in u and not any(g in u for g in good)]
for u in bad:
    print(u)
" 2>/dev/null || echo "PARSE_ERROR")

    if [[ -z "$BAD_URLS" ]]; then
      pass "All agent tool URLs point to known domains"
    elif [[ "$BAD_URLS" == "PARSE_ERROR" ]]; then
      warn "Could not parse agent config"
    else
      fail "Agent has tool URLs on unexpected domains:"
      echo "$BAD_URLS" | while read -r domain; do echo "         $domain"; done
    fi
  else
    fail "Could not fetch agent config from Retell API"
  fi
fi
echo ""

# -------------------------------------------------------------------
# CHECK 4: Post-call webhook endpoint reachable (catches: routing/deployment mismatch)
# Incident: 2026-03-19 — Post-call endpoint returned 500 due to missing RETELL_API_KEY on Render
# -------------------------------------------------------------------
echo "--- Check 4: Post-call endpoint reachable ---"
# Send a minimal request without valid auth — we expect 401, not 500 or 502
POSTCALL_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  --max-time 15 \
  -X POST "$HARNESS_URL/webhook/retell/call-ended" \
  -H "Content-Type: application/json" \
  -d '{"call_id":"smoke-test"}' 2>/dev/null) || POSTCALL_STATUS="000"

if [[ "$POSTCALL_STATUS" == "401" || "$POSTCALL_STATUS" == "403" || "$POSTCALL_STATUS" == "422" ]]; then
  pass "Post-call endpoint reachable (returned $POSTCALL_STATUS as expected without auth)"
elif [[ "$POSTCALL_STATUS" == "500" ]]; then
  fail "Post-call endpoint returned 500 — likely missing env var or import error"
elif [[ "$POSTCALL_STATUS" == "000" ]]; then
  fail "Post-call endpoint unreachable"
else
  warn "Post-call endpoint returned unexpected HTTP $POSTCALL_STATUS"
fi
echo ""

# -------------------------------------------------------------------
# CHECK 5: Supabase connectivity (catches: wrong URL, expired key, RLS misconfiguration)
# Incident: 2026-03-19 — Invalid Supabase URL in Vercel env vars caused app crash
# -------------------------------------------------------------------
echo "--- Check 5: Supabase connectivity ---"
SUPABASE_URL="${NEXT_PUBLIC_SUPABASE_URL:-${SUPABASE_URL:-}}"
SUPABASE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-}"
if [[ -z "$SUPABASE_URL" || -z "$SUPABASE_KEY" ]]; then
  warn "Supabase env vars not set — skipping"
else
  SB_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time 10 \
    "$SUPABASE_URL/rest/v1/call_records?select=id&limit=1" \
    -H "apikey: $SUPABASE_KEY" \
    -H "Authorization: Bearer $SUPABASE_KEY" 2>/dev/null) || SB_STATUS="000"

  if [[ "$SB_STATUS" == "200" ]]; then
    pass "Supabase call_records table reachable"
  elif [[ "$SB_STATUS" == "000" ]]; then
    fail "Supabase unreachable — check SUPABASE_URL"
  else
    fail "Supabase returned HTTP $SB_STATUS — check credentials or RLS"
  fi
fi
echo ""

# -------------------------------------------------------------------
# SUMMARY
# -------------------------------------------------------------------
echo "=== Results ==="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
echo "  WARN: $WARN"
echo ""

if [[ $FAIL -gt 0 ]]; then
  echo "SMOKE TEST FAILED — $FAIL check(s) need attention"
  exit 1
else
  echo "SMOKE TEST PASSED"
  exit 0
fi
