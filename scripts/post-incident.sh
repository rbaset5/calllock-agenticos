#!/usr/bin/env bash
# post-incident.sh — Log an incident after fixing a bug
# Appends to knowledge/voice-pipeline/incident-log.yaml and reminds you to:
#   1. Add a golden-set call (if voice-related)
#   2. Add a smoke-test check (if deploy-related)
#
# Usage:
#   ./scripts/post-incident.sh          # Interactive incident logger
#   ./scripts/post-incident.sh --scan   # Scan for unfollowed-up incidents

set -euo pipefail

INCIDENT_LOG="knowledge/voice-pipeline/incident-log.yaml"
SMOKE_TEST="scripts/smoke-test.sh"
GOLDEN_SET="knowledge/voice-pipeline/eval/golden-set.yaml"

# Ensure incident log exists with header
if [[ ! -f "$INCIDENT_LOG" ]]; then
  mkdir -p "$(dirname "$INCIDENT_LOG")"
  cat > "$INCIDENT_LOG" << 'HEADER'
# CallLock Incident Log
# Each entry records what broke, why, and what was done to prevent recurrence.
# This file grows after every fix — it is the "memory" of the system.
version: "1.0"
incidents: []
HEADER
  echo "Created $INCIDENT_LOG"
fi

# --- Scan mode: check for unfollowed-up incidents ---
if [[ "${1:-}" == "--scan" ]]; then
  echo "=== Prevention Scan ==="
  echo ""

  if [[ ! -f "$INCIDENT_LOG" ]]; then
    echo "  No incident log found at $INCIDENT_LOG"
    exit 0
  fi

  # Find incidents where BOTH prevention booleans are false
  STALE_COUNT=0
  CURRENT_ID=""
  CURRENT_WHAT=""
  CURRENT_DATE=""
  SMOKE_FALSE=false
  GOLDEN_FALSE=false

  while IFS= read -r line; do
    if [[ "$line" =~ ^\s*-\ id:\ \"(.+)\" ]]; then
      # Check previous incident before starting new one
      if [[ -n "$CURRENT_ID" && "$SMOKE_FALSE" == "true" && "$GOLDEN_FALSE" == "true" ]]; then
        # Check if older than 3 days
        if [[ -n "$CURRENT_DATE" ]]; then
          INCIDENT_TS=$(date -j -f "%Y-%m-%d" "$CURRENT_DATE" "+%s" 2>/dev/null || echo "0")
          NOW_TS=$(date "+%s")
          AGE_DAYS=$(( (NOW_TS - INCIDENT_TS) / 86400 ))
          if [[ $AGE_DAYS -ge 3 ]]; then
            echo "  STALE  $CURRENT_ID ($CURRENT_DATE, ${AGE_DAYS}d ago): $CURRENT_WHAT"
            STALE_COUNT=$((STALE_COUNT + 1))
          fi
        fi
      fi
      CURRENT_ID="${BASH_REMATCH[1]}"
      CURRENT_WHAT=""
      CURRENT_DATE=""
      SMOKE_FALSE=false
      GOLDEN_FALSE=false
    fi
    [[ "$line" =~ what_broke:\ [\'\"]?(.+)[\'\"]?$ ]] && CURRENT_WHAT="${BASH_REMATCH[1]}"
    [[ "$line" =~ date:\ \"(.+)\" ]] && CURRENT_DATE="${BASH_REMATCH[1]}"
    [[ "$line" =~ smoke_test_added:\ false ]] && SMOKE_FALSE=true
    [[ "$line" =~ golden_set_added:\ false ]] && GOLDEN_FALSE=true
  done < "$INCIDENT_LOG"

  # Check the last incident
  if [[ -n "$CURRENT_ID" && "$SMOKE_FALSE" == "true" && "$GOLDEN_FALSE" == "true" ]]; then
    if [[ -n "$CURRENT_DATE" ]]; then
      INCIDENT_TS=$(date -j -f "%Y-%m-%d" "$CURRENT_DATE" "+%s" 2>/dev/null || echo "0")
      NOW_TS=$(date "+%s")
      AGE_DAYS=$(( (NOW_TS - INCIDENT_TS) / 86400 ))
      if [[ $AGE_DAYS -ge 3 ]]; then
        echo "  STALE  $CURRENT_ID ($CURRENT_DATE, ${AGE_DAYS}d ago): $CURRENT_WHAT"
        STALE_COUNT=$((STALE_COUNT + 1))
      fi
    fi
  fi

  echo ""
  if [[ $STALE_COUNT -gt 0 ]]; then
    echo "  $STALE_COUNT incident(s) older than 3 days with no prevention measures."
    echo "  Run ./scripts/post-incident.sh to see follow-up suggestions."
    exit 1
  else
    echo "  All clear — every incident has at least one prevention measure."
    exit 0
  fi
fi

echo "=== Post-Incident Logger ==="
echo ""

# Gather details
read -rp "What broke? (one line): " WHAT_BROKE
read -rp "Root cause? (one line): " ROOT_CAUSE
read -rp "How was it fixed? (one line): " FIX_DESCRIPTION

echo ""
echo "Which layer was affected?"
echo "  1) Voice agent (Retell prompts, state machine, tools)"
echo "  2) Backend (harness webhooks, extraction, routing)"
echo "  3) App (Vercel, dashboard, API routes)"
echo "  4) Infrastructure (Render, Supabase, env vars, DNS)"
echo "  5) Data (missing fields, wrong values, pipeline errors)"
read -rp "Layer [1-5]: " LAYER_NUM

case "$LAYER_NUM" in
  1) LAYER="voice" ;;
  2) LAYER="backend" ;;
  3) LAYER="app" ;;
  4) LAYER="infra" ;;
  5) LAYER="data" ;;
  *) LAYER="unknown" ;;
esac

read -rp "Severity [critical/moderate/minor]: " SEVERITY
SEVERITY="${SEVERITY:-moderate}"

DATE=$(date -u +%Y-%m-%d)
TIME=$(date -u +%H:%M:%S)
EXISTING=$(grep -c '^\s*- id:' "$INCIDENT_LOG" 2>/dev/null || echo "0")
NEXT_NUM=$(printf '%03d' $((EXISTING + 1)))
ID="inc-$(date +%Y%m%d)-${NEXT_NUM}"
FIX_COMMIT=$(git log -1 --format=%H 2>/dev/null || echo "")

# Append to incident log
# Escape single quotes in user input for safe YAML
esc() { printf '%s' "$1" | sed "s/'/''/g"; }

cat >> "$INCIDENT_LOG" << EOF

  - id: "$ID"
    date: "$DATE"
    time: "${TIME}Z"
    layer: "$LAYER"
    severity: "$SEVERITY"
    what_broke: '$(esc "$WHAT_BROKE")'
    root_cause: '$(esc "$ROOT_CAUSE")'
    fix: '$(esc "$FIX_DESCRIPTION")'
    fix_commit: "$FIX_COMMIT"
    prevention:
      smoke_test_added: false
      golden_set_added: false
      notes: ""
EOF

echo ""
echo "Incident logged: $ID"
echo ""

# --- Auto-skeleton smoke test for infra/backend incidents ---
if [[ "$LAYER" == "infra" || "$LAYER" == "backend" ]]; then
  if [[ -f "$SMOKE_TEST" ]]; then
    # Determine next check number
    LAST_CHECK=$(grep -o 'CHECK [0-9]*' "$SMOKE_TEST" | tail -1 | grep -o '[0-9]*' || echo "0")
    NEXT_CHECK=$((LAST_CHECK + 1))

    cat >> "$SMOKE_TEST" << SMOKE

# -------------------------------------------------------------------
# CHECK ${NEXT_CHECK}: ${WHAT_BROKE} (catches: ${ROOT_CAUSE})
# Incident: ${ID}
# -------------------------------------------------------------------
echo "--- Check ${NEXT_CHECK}: ${WHAT_BROKE} ---"
# TODO: implement the actual check for this incident
# Example: curl, query, or assertion that would have caught this
warn "Check ${NEXT_CHECK} not yet implemented — see ${ID} in incident-log.yaml"
echo ""
SMOKE

    # Flip smoke_test_added to true for this entry
    sed -i '' "/id: \"${ID}\"/,/smoke_test_added:/{s/smoke_test_added: false/smoke_test_added: true/;}" "$INCIDENT_LOG"

    echo ""
    echo "  AUTO: Skeleton smoke test check ${NEXT_CHECK} appended to $SMOKE_TEST"
    echo "  AUTO: smoke_test_added set to true in incident log"
    echo "  TODO: Edit $SMOKE_TEST and replace the TODO with an actual check."
  else
    echo ""
    echo "  WARN: $SMOKE_TEST not found — skipping auto-skeleton"
    echo "  Create the smoke test file first, then add a check manually."
  fi
fi

# Remind about follow-up actions
echo ""
echo "=== Follow-up Actions ==="
echo ""

if [[ "$LAYER" == "voice" || "$LAYER" == "data" ]]; then
  echo "  VOICE/DATA incident — add a golden-set test case:"
  echo "    1. Make a test call that triggers this bug scenario"
  echo "    2. Run: /audit-call last"
  echo "    3. Add the transcript + expected_fields to: $GOLDEN_SET"
  echo "    4. Update incident log: set golden_set_added to true"
  echo ""
fi

if [[ "$LAYER" == "infra" || "$LAYER" == "backend" ]]; then
  echo "  Smoke test skeleton was auto-added. Complete the TODO in:"
  echo "    File: $SMOKE_TEST (Check ${NEXT_CHECK:-N})"
  echo ""
fi

echo "  Run './scripts/post-incident.sh --scan' to check for unfollowed-up incidents."
echo ""
echo "Done. The system just got smarter."
