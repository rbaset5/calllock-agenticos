// dialer/hud/composer.js
// Card composition engine (spec Sections 16–17).
// Pure functions — no side effects, no DOM, no state.

import { NOW_TEMPLATES } from './taxonomy.js';

/**
 * Compose the active card for the current moment.
 * Precedence: stage card → objection overlay → tone variant → delivery modifier
 */
export function composeActiveCard({
  stage,
  activeObjection = null,
  tone = null,
  deliveryModifier = null,
  stageCards,
  objectionCards,
}) {
  // Step 1: Start with stage card
  const stageCard = stageCards[stage];
  if (!stageCard) {
    return { id: stage, stage, moveType: 'pause', deliveryModifier: null, goal: '', primaryLine: '', backupLine: null, why: '', listenFor: [], branchPreview: {}, clarifyingQuestion: null, valueProp: null, proofPoint: null, toneVariants: {} };
  }
  let card = { ...stageCard };

  // Step 2: Overlay objection card if active
  if (activeObjection && objectionCards[activeObjection]) {
    const objCard = objectionCards[activeObjection];
    card = {
      ...card,
      primaryLine: objCard.primaryLine,
      backupLine: objCard.backupLine,
      why: objCard.why,
      clarifyingQuestion: objCard.clarifyingQuestion,
      valueProp: objCard.valueProp ?? card.valueProp,
      proofPoint: objCard.proofPoint ?? card.proofPoint,
      listenFor: objCard.listenFor.length > 0 ? objCard.listenFor : card.listenFor,
      branchPreview: Object.keys(objCard.branchPreview).length > 0 ? objCard.branchPreview : card.branchPreview,
      toneVariants: { ...(card.toneVariants || {}), ...(objCard.toneVariants || {}) },
    };
  }

  // Step 3: Apply tone variant (line fields only)
  if (tone && tone !== 'neutral' && tone !== 'unknown' && card.toneVariants[tone]) {
    const variant = card.toneVariants[tone];
    if (variant.primaryLine) card = { ...card, primaryLine: variant.primaryLine };
    if (variant.backupLine) card = { ...card, backupLine: variant.backupLine };
  }

  // Step 4: Delivery modifier (presentation only)
  if (deliveryModifier) {
    card = { ...card, deliveryModifier };
  }

  return card;
}

/**
 * Generate one-line NOW summary from classification result.
 * Template-based, max 1 sentence, no jargon.
 */
export function generateNowSummary({ primaryIntent, tone = 'neutral', toneConfidence = 0 }) {
  if (!primaryIntent || !NOW_TEMPLATES[primaryIntent]) {
    return 'Waiting for prospect response.';
  }
  let summary = NOW_TEMPLATES[primaryIntent];
  if (tone && tone !== 'neutral' && tone !== 'unknown' && toneConfidence >= 0.6) {
    summary += ` Sounds ${tone}.`;
  }
  return summary;
}
