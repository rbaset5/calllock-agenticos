import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { PLAYBOOK, fillLineTemplate, linesForStage, lineForStage } from '../playbook.js';
import { NATIVE_STAGE_CARDS } from '../cards.js';

describe('linesForStage', () => {
  it('returns 4 non-overlapping bridge angles', () => {
    const lines = linesForStage('BRIDGE', PLAYBOOK);
    assert.equal(lines.length, 4);
    for (const entry of lines) {
      assert.ok(entry.label, 'bridge line missing label');
      assert.ok(entry.line, 'bridge line missing text');
    }
  });

  it('CLOSE shows next-step alternatives, not center-panel duplicates', () => {
    const lines = linesForStage('CLOSE', PLAYBOOK);
    assert.equal(lines.length, 4);
    assert.ok(lines[0].line.includes('email'), 'first line should be yes followup');
    assert.ok(lines[3].line.includes('$297'), 'last line should be $297 anchor');
  });

  it('OPENER shows pitch lines for "what do you do" moments', () => {
    const lines = linesForStage('OPENER', PLAYBOOK);
    assert.equal(lines.length, 4);
    // First line should be elevator pitch, not the opener itself
    assert.ok(lines[0].line.includes('we answer it'), 'first line should be elevator pitch');
    // Should have after-hours angle
    const hasAfterHours = lines.some(l => l.line.includes('6 PM'));
    assert.ok(hasAfterHours, 'OPENER should include after-hours angle');
  });

  it('QUALIFIER shows qualifier-specific lines only', () => {
    const lines = linesForStage('QUALIFIER', PLAYBOOK);
    assert.ok(lines.length >= 2, 'QUALIFIER should have at least 2 lines');
    assert.ok(lines[0].line.includes('unanswered'), 'first line should be the qualifier question');
  });

  it('OBJECTION returns 4 smart-ordered resets', () => {
    const lines = linesForStage('OBJECTION', PLAYBOOK);
    assert.equal(lines.length, 4);
    assert.ok(lines[0].label.includes('EXISTING COVERAGE'), 'first should be existing coverage');
    assert.ok(lines[1].label.includes('TIMING'), 'second should be timing');
  });

  it('deduped stages: left rail does not duplicate center panel primaryLine', () => {
    // Only test stages where this plan specifically deduped left rail from center panel.
    // Other stages still have pre-existing duplication (future cleanup).
    const dedupedStages = ['OPENER', 'MINI_PITCH', 'BRIDGE', 'CLOSE'];
    for (const stage of dedupedStages) {
      const lines = linesForStage(stage, PLAYBOOK);
      const primary = NATIVE_STAGE_CARDS[stage].primaryLine;
      const dup = lines.find(l => l.line === primary);
      assert.equal(dup, undefined, `${stage} left rail duplicates center panel`);
    }
  });

  it('returns empty array for unknown stage', () => {
    const lines = linesForStage('UNKNOWN', PLAYBOOK);
    assert.deepEqual(lines, []);
  });
});

describe('lineForStage', () => {
  it('MINI_PITCH returns cards.js primaryLine (single source of truth)', () => {
    const line = lineForStage('MINI_PITCH', PLAYBOOK);
    assert.equal(line, NATIVE_STAGE_CARDS.MINI_PITCH.primaryLine);
  });

  it('returns empty string for unknown stages', () => {
    assert.equal(lineForStage('UNKNOWN', PLAYBOOK), '');
  });
});

describe('PLAYBOOK.faq', () => {
  it('has 7 FAQ items', () => {
    assert.equal(PLAYBOOK.faq.length, 7);
  });

  it('every item has id, question, and answer', () => {
    for (const item of PLAYBOOK.faq) {
      assert.ok(typeof item.id === 'string' && item.id.length > 0, 'missing id');
      assert.ok(typeof item.question === 'string' && item.question.length > 0, 'missing question');
      assert.ok(typeof item.answer === 'string' && item.answer.length > 0, 'missing answer');
    }
  });

  it('FAQ ids are unique', () => {
    const ids = PLAYBOOK.faq.map(f => f.id);
    assert.equal(new Set(ids).size, ids.length, 'duplicate FAQ ids');
  });
});

describe('PLAYBOOK.competitors', () => {
  it('has entries for known competitors', () => {
    for (const key of ['servicetitan', 'sameday', 'smithai', 'answering_service']) {
      assert.ok(key in PLAYBOOK.competitors, `missing competitor: ${key}`);
      assert.ok(PLAYBOOK.competitors[key].name, `${key} missing name`);
      assert.ok(PLAYBOOK.competitors[key].line, `${key} missing line`);
    }
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

  it('fills {LOCATION} with provided location', () => {
    const line = fillLineTemplate('Rashid over in {LOCATION}', { location: 'Houston' });
    assert.equal(line, 'Rashid over in Houston');
  });

  it('falls back to Detroit when no location provided', () => {
    const line = fillLineTemplate('Rashid over in {LOCATION}', {});
    assert.equal(line, 'Rashid over in Detroit');
  });

  it('fills both {NAME} and {LOCATION} in opener', () => {
    const line = fillLineTemplate(PLAYBOOK.opener, {
      name: 'Mike',
      location: 'Orlando',
    });
    assert.ok(line.includes('Hey Mike'));
    assert.ok(line.includes('over in Orlando'));
    assert.ok(!line.includes('{NAME}'));
    assert.ok(!line.includes('{LOCATION}'));
  });
});
