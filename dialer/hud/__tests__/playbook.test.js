import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { PLAYBOOK, fillLineTemplate, linesForStage } from '../playbook.js';

describe('linesForStage', () => {
  it('returns all bridge variants plus fallback', () => {
    const lines = linesForStage('BRIDGE', PLAYBOOK);
    assert.equal(lines.length, 8);
    // All bridge lines should have labels and non-empty text
    for (const entry of lines) {
      assert.ok(entry.label, 'bridge line missing label');
      assert.ok(entry.line, 'bridge line missing text');
    }
  });

  it('returns close lines plus power lines', () => {
    const lines = linesForStage('CLOSE', PLAYBOOK);
    assert.ok(lines.length >= 3, 'CLOSE should have at least 3 lines');
    // First 3 should be close, hedge, yesFollowup
    assert.ok(lines[0].line.includes('15 minutes'), 'first line should be the close');
    assert.ok(lines[1].line.includes('leave you alone'), 'second line should be the hedge');
    assert.ok(lines[2].line.includes('email'), 'third line should be yes followup');
  });

  it('opener includes power lines for "what do you do" moments', () => {
    const lines = linesForStage('OPENER', PLAYBOOK);
    assert.ok(lines.length >= 4, 'OPENER should have opener + power lines');
    assert.ok(lines[0].line.includes('cold call'), 'first line should be the opener');
    // Should have elevator pitch
    const hasElevator = lines.some(l => l.line.includes('AI that answers'));
    assert.ok(hasElevator, 'OPENER should include elevator pitch');
  });

  it('qualifier includes power lines for explanation moments', () => {
    const lines = linesForStage('QUALIFIER', PLAYBOOK);
    assert.ok(lines.length >= 3, 'QUALIFIER should have qualifier + bridge + power lines');
    assert.ok(lines[0].line.includes('unanswered'), 'first line should be the qualifier question');
  });

  it('power lines are accessible from key stages', () => {
    for (const stage of ['OPENER', 'QUALIFIER', 'CLOSE', 'OBJECTION']) {
      const lines = linesForStage(stage, PLAYBOOK);
      const hasElevator = lines.some(l => l.line && l.line.includes('AI that answers'));
      assert.ok(hasElevator, `${stage} should include elevator pitch line`);
    }
  });

  it('returns empty array for unknown stage', () => {
    const lines = linesForStage('UNKNOWN', PLAYBOOK);
    assert.deepEqual(lines, []);
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
