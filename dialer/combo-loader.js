(function attach(globalScope) {
  function createTimeoutPromise(timeoutMs) {
    return new Promise((_, reject) => {
      globalScope.setTimeout(() => reject(new Error('Microphone permission timeout')), timeoutMs);
    });
  }

  async function primeMicrophoneAccess({
    mediaDevices = globalScope.navigator ? globalScope.navigator.mediaDevices : undefined,
    timeoutMs = 4000,
  } = {}) {
    if (!mediaDevices || typeof mediaDevices.getUserMedia !== 'function') {
      return false;
    }

    try {
      const stream = await Promise.race([
        mediaDevices.getUserMedia({ audio: true }),
        createTimeoutPromise(timeoutMs),
      ]);
      for (const track of stream.getTracks()) {
        track.stop();
      }
      return true;
    } catch (error) {
      console.error('[combo] microphone priming failed:', error);
      return false;
    }
  }

  function bootstrapMicrophoneGate({
    overlay,
    button,
    statusEl,
    storage = globalScope.sessionStorage,
    storageKey = 'calllock-microphone-primed',
    primeMicrophone = primeMicrophoneAccess,
  }) {
    if (!overlay || !button) return;

    const hide = () => {
      overlay.hidden = true;
      if (statusEl) statusEl.textContent = '';
    };

    try {
      if (storage && storage.getItem(storageKey) === '1') {
        hide();
        return;
      }
    } catch {}

    button.addEventListener('click', async () => {
      if (statusEl) statusEl.textContent = 'Requesting microphone...';
      const ok = await primeMicrophone();
      if (!ok) {
        if (statusEl) statusEl.textContent = 'Allow microphone access to use the dialer.';
        return;
      }

      try {
        if (storage) storage.setItem(storageKey, '1');
      } catch {}
      hide();
    });
  }

  function activateDeferredFrame(frame) {
    if (!frame) return;
    const deferredSrc = frame.dataset ? frame.dataset.src : null;
    if (deferredSrc && frame.src !== deferredSrc) {
      frame.src = deferredSrc;
    }
  }

  function bootstrapComboFrames({
    dialerFrame,
    hudFrame,
  }) {
    if (!dialerFrame || !hudFrame) return;
    activateDeferredFrame(hudFrame);
  }

  const api = {
    activateDeferredFrame,
    bootstrapComboFrames,
    bootstrapMicrophoneGate,
    primeMicrophoneAccess,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }

  globalScope.CallLockComboLoader = api;
})(typeof window !== 'undefined' ? window : globalThis);
