(function attach(globalScope) {
  function configureTwilioAudio(device) {
    if (!device || !device.audio) return;
    if (typeof device.audio.outgoing === 'function') {
      device.audio.outgoing(false);
    }
    if (typeof device.audio.disconnect === 'function') {
      device.audio.disconnect(false);
    }
  }

  const api = { configureTwilioAudio };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }

  globalScope.CallLockTwilioAudio = api;
})(typeof window !== 'undefined' ? window : globalThis);
