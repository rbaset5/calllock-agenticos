import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { createTrajectoryState, computeRisk, updateTrajectory } from '../risk.js';

describe('createTrajectoryState', () => {
  test('returns zeroed-out state with all fields', () => {
    const t = createTrajectoryState();
    assert.equal(t.salvageAttemptCount, 0);
    assert.equal(t.consecutiveSameIntent, 0);
    assert.equal(t.lastPrimaryIntent, null);
    assert.equal(t.rescueMoveFailed, false);
    assert.equal(t.prospectQuestionCount, 0);
    assert.equal(t.turnsInCurrentStage, 0);
  });
});

describe('computeRisk', () => {
  test('returns low for single hedge', () => {
    const t = createTrajectoryState();
    assert.equal(computeRisk(t, { primary: { intent: 'hedge' }, compound: false }), 'low');
  });

  test('returns high for compound objection', () => {
    const t = createTrajectoryState();
    assert.equal(computeRisk(t, { primary: { intent: 'timing' }, compound: true }), 'high');
  });

  test('returns call_ending after 3 consecutive same intent', () => {
    const t = { ...createTrajectoryState(), consecutiveSameIntent: 3 };
    assert.equal(computeRisk(t, { primary: { intent: 'interest' }, compound: false }), 'call_ending');
  });

  test('returns call_ending when rescue failed + same intent repeats', () => {
    const t = { ...createTrajectoryState(), rescueMoveFailed: true, lastPrimaryIntent: 'timing' };
    assert.equal(computeRisk(t, { primary: { intent: 'timing' }, compound: false }), 'call_ending');
  });

  test('returns high after 2 salvage attempts', () => {
    const t = { ...createTrajectoryState(), salvageAttemptCount: 2 };
    assert.equal(computeRisk(t, { primary: { intent: 'interest' }, compound: false }), 'high');
  });

  test('returns medium after 2 consecutive same intent', () => {
    const t = { ...createTrajectoryState(), consecutiveSameIntent: 2 };
    assert.equal(computeRisk(t, { primary: { intent: 'timing' }, compound: false }), 'medium');
  });

  test('returns call_ending for explicit exit language', () => {
    const t = createTrajectoryState();
    assert.equal(computeRisk(t, { primary: { intent: 'brush_off' }, compound: false, utterance: 'stop calling me' }), 'call_ending');
  });
});

describe('updateTrajectory', () => {
  test('increments consecutiveSameIntent on repeated intent', () => {
    const t = { ...createTrajectoryState(), lastPrimaryIntent: 'timing', consecutiveSameIntent: 1 };
    const updated = updateTrajectory(t, { primary: { intent: 'timing' } }, 'OBJECTION', false);
    assert.equal(updated.consecutiveSameIntent, 2);
  });

  test('resets consecutiveSameIntent to 1 on new intent', () => {
    const t = { ...createTrajectoryState(), lastPrimaryIntent: 'timing', consecutiveSameIntent: 3 };
    const updated = updateTrajectory(t, { primary: { intent: 'interest' } }, 'OBJECTION', false);
    assert.equal(updated.consecutiveSameIntent, 1);
  });

  test('sets rescueMoveFailed when salvage attempt + same intent', () => {
    const t = { ...createTrajectoryState(), lastPrimaryIntent: 'timing' };
    const updated = updateTrajectory(t, { primary: { intent: 'timing' } }, 'OBJECTION', true);
    assert.equal(updated.rescueMoveFailed, true);
  });

  test('clears rescueMoveFailed when salvage attempt + different intent', () => {
    const t = { ...createTrajectoryState(), lastPrimaryIntent: 'timing', rescueMoveFailed: true };
    const updated = updateTrajectory(t, { primary: { intent: 'interest' } }, 'OBJECTION', true);
    assert.equal(updated.rescueMoveFailed, false);
  });

  test('increments prospectQuestionCount for curiosity', () => {
    const t = createTrajectoryState();
    const updated = updateTrajectory(t, { primary: { intent: 'curiosity' } }, 'BRIDGE', false);
    assert.equal(updated.prospectQuestionCount, 1);
  });

  test('increments prospectQuestionCount for confusion', () => {
    const t = createTrajectoryState();
    const updated = updateTrajectory(t, { primary: { intent: 'confusion' } }, 'OPENER', false);
    assert.equal(updated.prospectQuestionCount, 1);
  });

  test('increments turnsInCurrentStage', () => {
    const t = createTrajectoryState();
    const updated = updateTrajectory(t, { primary: { intent: 'timing' } }, 'OBJECTION', false);
    assert.equal(updated.turnsInCurrentStage, 1);
  });
});
