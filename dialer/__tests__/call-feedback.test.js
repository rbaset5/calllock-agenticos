const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const { createCallFeedbackController } = require('../call-feedback.js');

describe('createCallFeedbackController', () => {
  it('does not play ringback until the remote leg is actually ringing', () => {
    const events = [];
    const controller = createCallFeedbackController({
      setStatus: (value) => events.push(['status', value]),
      startRingtone: () => events.push(['ring', 'start']),
      stopRingtone: () => events.push(['ring', 'stop']),
    });

    controller.onConnecting();
    controller.onRinging();

    assert.deepEqual(events, [
      ['status', 'Connecting...'],
      ['ring', 'start'],
      ['status', 'Ringing...'],
    ]);
  });

  it('stops ringback when the call is accepted', () => {
    const events = [];
    const controller = createCallFeedbackController({
      setStatus: (value) => events.push(['status', value]),
      startRingtone: () => events.push(['ring', 'start']),
      stopRingtone: () => events.push(['ring', 'stop']),
    });

    controller.onRinging();
    controller.onAccepted();

    assert.deepEqual(events, [
      ['ring', 'start'],
      ['status', 'Ringing...'],
      ['ring', 'stop'],
      ['status', 'Connected'],
    ]);
  });

  it('stops ringback and reports the ended duration on disconnect', () => {
    const events = [];
    const controller = createCallFeedbackController({
      setStatus: (value) => events.push(['status', value]),
      startRingtone: () => events.push(['ring', 'start']),
      stopRingtone: () => events.push(['ring', 'stop']),
    });

    controller.onRinging();
    controller.onDisconnected(0);

    assert.deepEqual(events, [
      ['ring', 'start'],
      ['status', 'Ringing...'],
      ['ring', 'stop'],
      ['status', 'Ended (0s)'],
    ]);
  });
});
