(function attach(globalScope) {
  function createCallFeedbackController({ setStatus, startRingtone, stopRingtone }) {
    return {
      onConnecting() {
        setStatus('Connecting...');
      },
      onRinging() {
        startRingtone();
        setStatus('Ringing...');
      },
      onAccepted() {
        stopRingtone();
        setStatus('Connected');
      },
      onDisconnected(durationSeconds) {
        stopRingtone();
        setStatus(`Ended (${durationSeconds}s)`);
      },
      onError() {
        stopRingtone();
        setStatus('');
      },
    };
  }

  const api = { createCallFeedbackController };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }

  globalScope.CallLockCallFeedback = api;
})(typeof window !== 'undefined' ? window : globalThis);
