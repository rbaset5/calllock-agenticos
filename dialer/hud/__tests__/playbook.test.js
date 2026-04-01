import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { PLAYBOOK, fillLineTemplate, linesForStage } from '../playbook.js';

describe('linesForStage', () => {
  it('returns all bridge variants plus fallback', () => {
    const lines = linesForStage('BRIDGE', PLAYBOOK);
    assert.equal(lines.length, 8);
    assert.deepEqual(
      lines.map((entry) => entry.label),
      [
        'missed_calls/voicemail',
        'missed_calls/staff',
        'missed_calls/covered',
        'competition/slow',
        'competition/competitor',
        'overwhelmed/everything',
        'overwhelmed/cantKeepUp',
        'fallback',
      ],
    );
  });

  it('returns quick follow-up lines for close', () => {
    const lines = linesForStage('CLOSE', PLAYBOOK);
    assert.deepEqual(
      lines.map((entry) => entry.label),
      ['close', 'hedge', 'yesFollowup'],
    );
  });
});

describe('fillLineTemplate', () => {
  it('fills prospect placeholders with context values', () => {
    const line = fillLineTemplate(PLAYBOOK.booked, {
      name: 'Sam',
      day: 'Thursday',
    });
    assert.equal(line, 'Perfect — invite heading your way. Talk Thursday!');
  });
});
