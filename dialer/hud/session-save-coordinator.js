// dialer/hud/session-save-coordinator.js
// Coordinates delayed end-of-call saves so outcome writes can cancel stale snapshots.

export function createSessionSaveCoordinator({
  saveSession,
  setTimeoutImpl = globalThis.setTimeout,
  clearTimeoutImpl = globalThis.clearTimeout,
  delayMs = 500,
}) {
  let pendingTimerId = null;
  let pendingEndedPayload = null;

  function cancelPending() {
    if (pendingTimerId !== null) {
      clearTimeoutImpl(pendingTimerId);
      pendingTimerId = null;
    }
    pendingEndedPayload = null;
  }

  function scheduleEndedSave(state, prospectId, endedSession) {
    cancelPending();
    pendingEndedPayload = { state, prospectId, endedSession };
    pendingTimerId = setTimeoutImpl(() => {
      const payload = pendingEndedPayload;
      pendingTimerId = null;
      pendingEndedPayload = null;
      if (!payload) return;
      void saveSession(payload.state, payload.prospectId, payload.endedSession);
    }, delayMs);
  }

  async function saveOutcome(state, prospectId) {
    cancelPending();
    await saveSession(state, prospectId, null);
  }

  return {
    cancelPending,
    scheduleEndedSave,
    saveOutcome,
  };
}
