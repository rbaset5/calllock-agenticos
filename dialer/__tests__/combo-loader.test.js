const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const {
  bootstrapComboFrames,
  bootstrapMicrophoneGate,
} = require('../combo-loader.js');

describe('bootstrapComboFrames', () => {
  it('loads the HUD iframe immediately', () => {
    const hudFrame = {
      dataset: { src: '/hud/' },
      src: 'about:blank',
    };
    const dialerFrame = {
      addEventListener() {},
    };

    bootstrapComboFrames({
      dialerFrame,
      hudFrame,
    });

    assert.equal(hudFrame.src, '/hud/');
  });
});

describe('bootstrapMicrophoneGate', () => {
  it('hides the gate immediately when microphone access was already primed', () => {
    const overlay = { hidden: false };
    const storage = {
      getItem(key) {
        assert.equal(key, 'calllock-microphone-primed');
        return '1';
      },
    };

    bootstrapMicrophoneGate({
      overlay,
      button: { addEventListener() {} },
      statusEl: { textContent: '' },
      storage,
    });

    assert.equal(overlay.hidden, true);
  });

  it('primes microphone access and hides the gate after the button is clicked', async () => {
    let clickHandler = null;
    const overlay = { hidden: false };
    const statusEl = { textContent: '' };
    const writes = [];
    const button = {
      addEventListener(event, handler) {
        assert.equal(event, 'click');
        clickHandler = handler;
      },
    };
    const storage = {
      getItem() {
        return null;
      },
      setItem(key, value) {
        writes.push([key, value]);
      },
    };

    bootstrapMicrophoneGate({
      overlay,
      button,
      statusEl,
      storage,
      primeMicrophone: async () => true,
    });

    await clickHandler();
    assert.equal(overlay.hidden, true);
    assert.equal(statusEl.textContent, '');
    assert.deepEqual(writes, [['calllock-microphone-primed', '1']]);
  });

  it('keeps the gate visible and shows guidance when priming fails', async () => {
    let clickHandler = null;
    const overlay = { hidden: false };
    const statusEl = { textContent: '' };
    const button = {
      addEventListener(_event, handler) {
        clickHandler = handler;
      },
    };

    bootstrapMicrophoneGate({
      overlay,
      button,
      statusEl,
      storage: { getItem() { return null; }, setItem() {} },
      primeMicrophone: async () => false,
    });

    await clickHandler();
    assert.equal(overlay.hidden, false);
    assert.equal(statusEl.textContent, 'Allow microphone access to use the dialer.');
  });
});
