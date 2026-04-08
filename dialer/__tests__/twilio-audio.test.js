const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const { configureTwilioAudio } = require('../twilio-audio.js');

describe('configureTwilioAudio', () => {
  it('disables Twilio SDK outgoing and disconnect sounds when audio helper exists', () => {
    const calls = [];
    const device = {
      audio: {
        outgoing(value) {
          calls.push(['outgoing', value]);
        },
        disconnect(value) {
          calls.push(['disconnect', value]);
        },
      },
    };

    configureTwilioAudio(device);

    assert.deepEqual(calls, [
      ['outgoing', false],
      ['disconnect', false],
    ]);
  });

  it('does nothing when the Twilio device has no audio helper', () => {
    assert.doesNotThrow(() => configureTwilioAudio({}));
  });
});
