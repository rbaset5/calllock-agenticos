// dialer/hud/__tests__/composer.test.js
// Uses Node.js built-in test runner: node --test

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { composeActiveCard, generateNowSummary } from '../composer.js';
import { NATIVE_STAGE_CARDS, NATIVE_OBJECTION_CARDS } from '../cards.js';
import { NOW_TEMPLATES } from '../taxonomy.js';

// -------------------------
// composeActiveCard
// -------------------------

describe('composeActiveCard', () => {
  it('returns stage card when no objection or tone', () => {
    const card = composeActiveCard({
      stage: 'OPENER',
      stageCards: NATIVE_STAGE_CARDS,
      objectionCards: NATIVE_OBJECTION_CARDS,
    });

    assert.equal(card.id, 'OPENER');
    assert.equal(card.stage, 'OPENER');
    assert.equal(card.goal, NATIVE_STAGE_CARDS.OPENER.goal);
    assert.equal(card.primaryLine, NATIVE_STAGE_CARDS.OPENER.primaryLine);
    assert.equal(card.moveType, 'ask');
  });

  it('overlays objection card fields preserving stage goal', () => {
    const card = composeActiveCard({
      stage: 'BRIDGE',
      activeObjection: 'timing',
      stageCards: NATIVE_STAGE_CARDS,
      objectionCards: NATIVE_OBJECTION_CARDS,
    });

    // Objection fields override
    assert.equal(card.primaryLine, NATIVE_OBJECTION_CARDS.timing.primaryLine);
    assert.equal(card.backupLine, NATIVE_OBJECTION_CARDS.timing.backupLine);
    assert.equal(card.why, NATIVE_OBJECTION_CARDS.timing.why);
    assert.equal(card.clarifyingQuestion, NATIVE_OBJECTION_CARDS.timing.clarifyingQuestion);

    // Stage goal preserved
    assert.equal(card.goal, NATIVE_STAGE_CARDS.BRIDGE.goal);
    assert.equal(card.stage, 'BRIDGE');
  });

  it('applies tone variant to primaryLine only (goal, why unchanged)', () => {
    const card = composeActiveCard({
      stage: 'OPENER',
      tone: 'rushed',
      stageCards: NATIVE_STAGE_CARDS,
      objectionCards: NATIVE_OBJECTION_CARDS,
    });

    assert.equal(card.primaryLine, NATIVE_STAGE_CARDS.OPENER.toneVariants.rushed.primaryLine);
    assert.equal(card.goal, NATIVE_STAGE_CARDS.OPENER.goal);
    assert.equal(card.why, NATIVE_STAGE_CARDS.OPENER.why);
  });

  it('delivery modifier only affects display (deliveryModifier field set, lines unchanged)', () => {
    const card = composeActiveCard({
      stage: 'OPENER',
      deliveryModifier: 'compress',
      stageCards: NATIVE_STAGE_CARDS,
      objectionCards: NATIVE_OBJECTION_CARDS,
    });

    assert.equal(card.deliveryModifier, 'compress');
    assert.equal(card.primaryLine, NATIVE_STAGE_CARDS.OPENER.primaryLine);
    assert.equal(card.backupLine, NATIVE_STAGE_CARDS.OPENER.backupLine);
  });

  it('unknown stage returns safe fallback card', () => {
    const card = composeActiveCard({
      stage: 'DOES_NOT_EXIST',
      stageCards: NATIVE_STAGE_CARDS,
      objectionCards: NATIVE_OBJECTION_CARDS,
    });

    assert.equal(card.id, 'DOES_NOT_EXIST');
    assert.equal(card.stage, 'DOES_NOT_EXIST');
    assert.equal(card.moveType, 'pause');
    assert.equal(card.goal, '');
    assert.equal(card.primaryLine, '');
    assert.equal(card.deliveryModifier, null);
    assert.deepEqual(card.listenFor, []);
    assert.deepEqual(card.branchPreview, {});
    assert.deepEqual(card.toneVariants, {});
  });

  it('objection + tone combined (tone wins since it runs after overlay)', () => {
    // timing objection has an 'annoyed' tone variant
    const card = composeActiveCard({
      stage: 'BRIDGE',
      activeObjection: 'timing',
      tone: 'annoyed',
      stageCards: NATIVE_STAGE_CARDS,
      objectionCards: NATIVE_OBJECTION_CARDS,
    });

    // Tone variant should override the objection's primaryLine
    const timingObj = NATIVE_OBJECTION_CARDS.timing;
    const mergedVariants = { ...NATIVE_STAGE_CARDS.BRIDGE.toneVariants, ...timingObj.toneVariants };
    assert.equal(card.primaryLine, mergedVariants.annoyed.primaryLine);

    // Goal still from stage
    assert.equal(card.goal, NATIVE_STAGE_CARDS.BRIDGE.goal);
  });
});

// -------------------------
// generateNowSummary
// -------------------------

describe('generateNowSummary', () => {
  it('returns template for known intent', () => {
    const summary = generateNowSummary({ primaryIntent: 'pricing_question' });
    assert.equal(summary, NOW_TEMPLATES.pricing_question);
  });

  it('appends tone when non-neutral and confidence >= 0.6', () => {
    const summary = generateNowSummary({
      primaryIntent: 'pricing_question',
      tone: 'annoyed',
      toneConfidence: 0.8,
    });
    assert.equal(summary, `${NOW_TEMPLATES.pricing_question} Sounds annoyed.`);
  });

  it('does NOT append tone when neutral', () => {
    const summary = generateNowSummary({
      primaryIntent: 'pricing_question',
      tone: 'neutral',
      toneConfidence: 0.9,
    });
    assert.equal(summary, NOW_TEMPLATES.pricing_question);
  });

  it('does NOT append tone when confidence < 0.6', () => {
    const summary = generateNowSummary({
      primaryIntent: 'pricing_question',
      tone: 'annoyed',
      toneConfidence: 0.5,
    });
    assert.equal(summary, NOW_TEMPLATES.pricing_question);
  });

  it('returns waiting message for null intent', () => {
    const summary = generateNowSummary({ primaryIntent: null });
    assert.equal(summary, 'Waiting for prospect response.');
  });

  it('returns waiting message for unknown intent', () => {
    const summary = generateNowSummary({ primaryIntent: 'totally_unknown_intent' });
    assert.equal(summary, 'Waiting for prospect response.');
  });
});
