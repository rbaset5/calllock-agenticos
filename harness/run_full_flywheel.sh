#!/usr/bin/env bash
# Full flywheel: wait for current sweep → CID lookup for TBDs → second sweep
# Run from harness/ directory
set -euo pipefail

LOG=/tmp/lsa_flywheel.log
SWEEP_PID=${1:-""}
export PYTHONPATH=src
export PYTHONUNBUFFERED=1

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== FULL FLYWHEEL START ==="

# Phase 1: Wait for current sweep to finish
if [ -n "$SWEEP_PID" ] && kill -0 "$SWEEP_PID" 2>/dev/null; then
    log "Phase 1: Waiting for current sweep (PID $SWEEP_PID) to finish..."
    while kill -0 "$SWEEP_PID" 2>/dev/null; do sleep 10; done
    log "Phase 1: Current sweep finished."
else
    log "Phase 1: No active sweep, skipping wait."
fi

# Phase 2: CID lookup for TBD towns
log "Phase 2: Running CID lookup for TBD markets..."
.venv/bin/python -u -m outbound.cid_lookup 2>&1 | tee -a "$LOG"
log "Phase 2: CID lookup complete."

# Phase 3: Second sweep with newly resolved CIDs
log "Phase 3: Running second LSA discovery sweep..."
.venv/bin/python -u -m outbound.lsa_discovery --output lsa_full_sweep_r2.csv 2>&1 | tee -a "$LOG"
log "Phase 3: Second sweep complete."

# Summary
log "=== FLYWHEEL COMPLETE ==="
.venv/bin/python -c "
import sqlite3, json
from pathlib import Path
conn = sqlite3.connect('src/outbound/data/lsa_discovery.db')
total = conn.execute('SELECT COUNT(*) FROM lsa_businesses').fetchone()[0]
states = conn.execute('SELECT state, COUNT(*) FROM lsa_businesses GROUP BY state ORDER BY COUNT(*) DESC').fetchall()
conn.close()
markets = json.loads(Path('src/outbound/data/small_markets.json').read_text())
resolved = sum(1 for m in markets if m.get('data_cid') and m['data_cid'] != 'TBD')
print(f'Total businesses in DB: {total}')
print(f'Markets with CIDs: {resolved}/{len(markets)}')
print(f'By state: {dict(states)}')
" 2>&1 | tee -a "$LOG"
