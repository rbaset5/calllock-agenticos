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
  auditTrail.push({
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
  });
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
