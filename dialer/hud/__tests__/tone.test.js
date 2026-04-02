import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { assignTone, shouldUpdateTone } from '../tone.js';

describe('assignTone', () => {
  test('short dismissive response + objection intent → rushed', () => {
    const result = assignTone('no thanks', { primaryIntent: 'interest' }, 'OPENER');
    assert.equal(result.tone_label, 'rushed');
  });

  test('repeated rejection phrases → annoyed', () => {
    const result = assignTone('I said no, not interested, stop calling', { primaryIntent: 'brush_off' }, 'OBJECTION');
    assert.equal(result.tone_label, 'annoyed');
  });

  test('follow-up question → curious', () => {
    const result = assignTone('how does that work exactly?', { primaryIntent: 'curiosity' }, 'BRIDGE');
    assert.equal(result.tone_label, 'curious');
  });

  test('curiosity intent triggers curious tone', () => {
    const result = assignTone('ok tell me about it', { primaryIntent: 'curiosity' }, 'BRIDGE');
    assert.equal(result.tone_label, 'curious');
  });

  test('premise challenge → skeptical', () => {
    const result = assignTone("that doesn't sound real, I doubt that works", { primaryIntent: 'interest' }, 'BRIDGE');
    assert.equal(result.tone_label, 'skeptical');
  });

  test('guarded signals → guarded', () => {
    const result = assignTone('we already have someone who answers the phones for us', { primaryIntent: 'existing_coverage' }, 'BRIDGE');
    assert.equal(result.tone_label, 'guarded');
  });

  test('neutral statement → neutral', () => {
    const result = assignTone('yeah we get some calls during the day', { primaryIntent: 'engaged_answer' }, 'QUALIFIER');
    assert.equal(result.tone_label, 'neutral');
  });

  test('result always has tone_source = rules', () => {
    const result = assignTone('anything', { primaryIntent: 'yes' }, 'OPENER');
    assert.equal(result.tone_source, 'rules');
    assert.equal(typeof result.tone_confidence, 'number');
  });
});

describe('shouldUpdateTone', () => {
  test('returns true when confidence exceeds current by ≥0.15', () => {
    assert.equal(shouldUpdateTone(
      { tone_label: 'neutral', tone_confidence: 0.5 },
      { tone_label: 'rushed', tone_confidence: 0.7 },
    ), true);
  });

  test('returns false when confidence delta is small (<0.15)', () => {
    assert.equal(shouldUpdateTone(
      { tone_label: 'neutral', tone_confidence: 0.6 },
      { tone_label: 'guarded', tone_confidence: 0.65 },
    ), false);
  });

  test('annoyed overrides immediately at ≥0.7 confidence', () => {
    assert.equal(shouldUpdateTone(
      { tone_label: 'neutral', tone_confidence: 0.6 },
      { tone_label: 'annoyed', tone_confidence: 0.75 },
    ), true);
  });

  test('rushed overrides immediately at ≥0.7 confidence', () => {
    assert.equal(shouldUpdateTone(
      { tone_label: 'neutral', tone_confidence: 0.6 },
      { tone_label: 'rushed', tone_confidence: 0.72 },
    ), true);
  });

  test('returns false when same label', () => {
    assert.equal(shouldUpdateTone(
      { tone_label: 'rushed', tone_confidence: 0.7 },
      { tone_label: 'rushed', tone_confidence: 0.8 },
    ), false);
  });

  test('returns true when consecutiveCount >= 2', () => {
    assert.equal(shouldUpdateTone(
      { tone_label: 'neutral', tone_confidence: 0.6 },
      { tone_label: 'guarded', tone_confidence: 0.62 },
      2,
    ), true);
  });

  test('returns false when consecutiveCount < 2 and delta < threshold', () => {
    assert.equal(shouldUpdateTone(
      { tone_label: 'neutral', tone_confidence: 0.6 },
      { tone_label: 'guarded', tone_confidence: 0.62 },
      1,
    ), false);
  });
});
