// dialer/hud/session.js — Audit trail + session logging
// Vanilla JS ES module — no build step, no TypeScript.

let auditTrail = [];

/**
 * Reset the audit trail (call on CALL_STARTED).
 */
export function resetAuditTrail() {
  auditTrail = [];
}

/**
 * Log a decision to the audit trail.
 * Called on every reducer dispatch.
 */
export function logDecision(action, prevState, newState) {
  const entry = {
    ts: Date.now(),
    utteranceId: action.utteranceId ?? action.turn?.utteranceId ?? null,
    utterance: action.turn?.text ?? action.utterance ?? null,
    speaker: action.turn?.speaker ?? null,
    actionType: action.type,
    method: newState.now?.classificationSource ?? 'unknown',
    confidence: newState.now?.confidence ?? null,
    prevStage: prevState.stage,
    newStage: newState.stage,
    nowLine: newState.now?.line ?? null,
    overridden: action.type.startsWith('MANUAL_'),
    // v2 fields (spec Section 14)
    tone: newState.tone ?? null,
    toneSource: newState.toneSource ?? null,
    risk: newState.risk ?? null,
    compound: newState.compound ?? false,
    signalCount: newState.signalCount ?? 0,
    recommendedActionBias: newState.recommendedActionBias ?? null,
    moveType: newState.moveType ?? null,
    deliveryModifier: newState.deliveryModifier ?? null,
    primaryIntent: newState.primaryIntent ?? null,
  };
  // Keypress telemetry fields (from logKeypress in ui.js)
  if (action.type === 'KEYPRESS_LOG') {
    entry.key = action.key ?? null;
    entry.action = action.action ?? null;
    entry.value = action.value ?? null;
    entry.isOverride = action.isOverride ?? false;
    entry.source = action.source ?? 'manual';
    entry.stage = action.stage ?? prevState.stage;
  }
  auditTrail.push(entry);
}

/**
 * Serialize the full session payload for POST to /hud/session-log.
 */
export function serializeSession(state, trail = auditTrail) {
  return {
    callId: state.callId,
    stage: state.stage,
    outcome: state.outcome,
    bridgeAngle: state.bridgeAngle,
    qualifierRead: state.qualifierRead,
    objectionHistory: state.objectionHistory,
    metrics: state.metrics,
    auditTrail: trail,
    transcriptLength: state.transcript.length,
    endedAt: Date.now(),
  };
}

export function captureSession(state) {
  return serializeSession(state, auditTrail.slice());
}

/**
 * Save session data to the server.
 */
export async function saveSession(state, prospectId, hudSessionOverride = null) {
  const hudSession = hudSessionOverride ?? serializeSession(state);
  const callId = hudSession.callId || state.callId;
  if (!callId) return;

  try {
    const res = await fetch('/hud/session-log', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        twilio_call_sid: callId,
        prospect_id: prospectId ?? null,
        hud_session: hudSession,
      }),
    });

    if (!res.ok) {
      console.error('[hud/session] Save failed:', res.status);
    } else {
      console.log('[hud/session] Session saved for', callId);
    }
  } catch (err) {
    console.error('[hud/session] Save error:', err.message);
  }
}

/**
 * Get current audit trail (for debugging / inspection).
 */
export function getAuditTrail() {
  return auditTrail;
}

/**
 * Generate replay timeline data from the audit trail.
 * Returns an array of keypress events with relative timing.
 * Consumers render this however they like (table, visual timeline, etc.)
 */
export function generateReplayTimeline() {
  const keypresses = auditTrail.filter(e => e.actionType === 'KEYPRESS_LOG');
  // Exclude system transitions (INIT_CALL, CALL_CONNECTED, END_CALL) from replay
  const systemActions = ['INIT_CALL', 'CALL_CONNECTED', 'END_CALL', 'OUTCOME_RECEIVED'];
  const stageChanges = auditTrail.filter(e =>
    e.prevStage !== e.newStage && e.newStage !== 'IDLE' && !systemActions.includes(e.actionType)
  );
  if (keypresses.length === 0 && stageChanges.length === 0) return [];

  const allEvents = [];
  const t0 = auditTrail.length > 0 ? auditTrail[0].ts : 0;

  for (const kp of keypresses) {
    allEvents.push({
      type: 'keypress',
      offsetMs: kp.ts - t0,
      key: kp.key ?? '?',
      action: kp.action ?? kp.actionType,
      value: kp.value ?? null,
      stage: kp.stage ?? kp.newStage,
      isOverride: kp.isOverride ?? kp.overridden ?? false,
    });
  }

  for (const sc of stageChanges) {
    allEvents.push({
      type: 'stage_change',
      offsetMs: sc.ts - t0,
      from: sc.prevStage,
      to: sc.newStage,
      source: sc.overridden ? 'manual' : 'ai',
    });
  }

  allEvents.sort((a, b) => a.offsetMs - b.offsetMs);
  return allEvents;
}
