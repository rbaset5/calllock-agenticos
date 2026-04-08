(function attach(globalScope) {
  function createTwilioReadyGate() {
    let state = 'connecting';
    let inflightInit = null;

    return {
      getState() {
        return state;
      },
      setState(nextState) {
        state = nextState;
      },
      isReady() {
        return state === 'ready';
      },
      getInflightInit() {
        return inflightInit;
      },
      setInflightInit(promise) {
        inflightInit = promise;
      },
    };
  }

  async function ensureTwilioDeviceReady({ gate, initDevice, showToast }) {
    if (gate.isReady()) return true;

    if (!gate.getInflightInit()) {
      gate.setInflightInit(Promise.resolve()
        .then(() => initDevice())
        .finally(() => {
        gate.setInflightInit(null);
      }));
    }

    try {
      await gate.getInflightInit();
    } catch {
      // initDevice is responsible for updating gate state and logging details.
    }

    if (gate.isReady()) return true;
    showToast('Twilio not ready yet. Wait for Voice Ready and try again.');
    return false;
  }

  function attachLazyTwilioInit({ target, initDevice }) {
    let started = false;

    const run = async () => {
      if (started) return;
      started = true;
      cleanup();
      await initDevice();
    };

    const cleanup = () => {
      target.removeEventListener('pointerdown', run);
      target.removeEventListener('keydown', run);
    };

    target.addEventListener('pointerdown', run);
    target.addEventListener('keydown', run);

    return cleanup;
  }

  const api = {
    attachLazyTwilioInit,
    createTwilioReadyGate,
    ensureTwilioDeviceReady,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }

  globalScope.CallLockTwilioClient = api;
})(typeof window !== 'undefined' ? window : globalThis);
