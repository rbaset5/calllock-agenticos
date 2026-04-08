const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const {
  attachLazyTwilioInit,
  createTwilioReadyGate,
  ensureTwilioDeviceReady,
} = require('../twilio-client.js');

describe('createTwilioReadyGate', () => {
  it('tracks Twilio readiness state transitions', () => {
    const gate = createTwilioReadyGate();

    assert.equal(gate.getState(), 'connecting');
    assert.equal(gate.isReady(), false);

    gate.setState('ready');
    assert.equal(gate.getState(), 'ready');
    assert.equal(gate.isReady(), true);

    gate.setState('error');
    assert.equal(gate.getState(), 'error');
    assert.equal(gate.isReady(), false);
  });
});

describe('ensureTwilioDeviceReady', () => {
  it('returns immediately when the device is already ready', async () => {
    const gate = createTwilioReadyGate();
    gate.setState('ready');

    let initCalls = 0;
    const ready = await ensureTwilioDeviceReady({
      gate,
      initDevice: async () => { initCalls += 1; },
      showToast: () => {},
    });

    assert.equal(ready, true);
    assert.equal(initCalls, 0);
  });

  it('re-initializes once when the device is not ready and succeeds after registration', async () => {
    const gate = createTwilioReadyGate();
    let initCalls = 0;

    const ready = await ensureTwilioDeviceReady({
      gate,
      initDevice: async () => {
        initCalls += 1;
        gate.setState('ready');
      },
      showToast: () => {},
    });

    assert.equal(ready, true);
    assert.equal(initCalls, 1);
  });

  it('surfaces a toast when re-initialization still does not produce a ready device', async () => {
    const gate = createTwilioReadyGate();
    const toasts = [];

    const ready = await ensureTwilioDeviceReady({
      gate,
      initDevice: async () => {
        gate.setState('error');
      },
      showToast: (message) => {
        toasts.push(message);
      },
    });

    assert.equal(ready, false);
    assert.deepEqual(toasts, ['Twilio not ready yet. Wait for Voice Ready and try again.']);
  });

  it('deduplicates concurrent re-initialization attempts', async () => {
    const gate = createTwilioReadyGate();
    let initCalls = 0;

    const initDevice = async () => {
      initCalls += 1;
      await new Promise((resolve) => setTimeout(resolve, 5));
      gate.setState('ready');
    };

    const [first, second] = await Promise.all([
      ensureTwilioDeviceReady({ gate, initDevice, showToast: () => {} }),
      ensureTwilioDeviceReady({ gate, initDevice, showToast: () => {} }),
    ]);

    assert.equal(first, true);
    assert.equal(second, true);
    assert.equal(initCalls, 1);
  });
});

describe('attachLazyTwilioInit', () => {
  it('initializes once on the first user interaction', async () => {
    const listeners = new Map();
    let initCalls = 0;
    const target = {
      addEventListener(event, handler) {
        listeners.set(event, handler);
      },
      removeEventListener(event) {
        listeners.delete(event);
      },
    };

    attachLazyTwilioInit({
      target,
      initDevice: async () => {
        initCalls += 1;
      },
    });

    await listeners.get('pointerdown')();
    assert.equal(initCalls, 1);
    assert.equal(listeners.size, 0);
  });

  it('does not re-enter while initialization is already in flight', async () => {
    const listeners = new Map();
    let resolveInit;
    let initCalls = 0;
    const target = {
      addEventListener(event, handler) {
        listeners.set(event, handler);
      },
      removeEventListener(event) {
        listeners.delete(event);
      },
    };

    attachLazyTwilioInit({
      target,
      initDevice: () => {
        initCalls += 1;
        return new Promise((resolve) => {
          resolveInit = resolve;
        });
      },
    });

    const keydown = listeners.get('keydown');
    keydown();
    keydown();
    assert.equal(initCalls, 1);
    resolveInit();
    await Promise.resolve();
  });
});
