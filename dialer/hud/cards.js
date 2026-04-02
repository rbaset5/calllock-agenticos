// dialer/hud/cards.js
// Card schema and normalizeCard adapter — bridges old playbook format to v2 card schema.
// Vanilla JS ES module — no build step, no TypeScript.
// Spec: v2 Sections 4, 21.

import { lineForStage } from './playbook.js';

// ── Card field schema ───────────────────────────────────────────

export const CARD_FIELDS = [
  'id',
  'stage',
  'moveType',
  'deliveryModifier',
  'goal',
  'primaryLine',
  'backupLine',
  'why',
  'listenFor',
  'branchPreview',
  'clarifyingQuestion',
  'valueProp',
  'proofPoint',
  'toneVariants',
];

// ── Stage → move-type mapping ───────────────────────────────────

export const STAGE_MOVE_MAP = {
  IDLE: 'pause',
  OPENER: 'ask',
  PERMISSION_MOMENT: 'ask',
  MINI_PITCH: 'clarify',
  GATEKEEPER: 'ask',
  WRONG_PERSON: 'clarify',
  BRIDGE: 'bridge',
  QUALIFIER: 'ask',
  PRICING: 'reframe',
  CLOSE: 'close',
  SEED_EXIT: 'exit',
  OBJECTION: 'reframe',
  BOOKED: 'close',
  EXIT: 'exit',
  NON_CONNECT: 'pause',
  ENDED: 'pause',
};

// ── Stage → goal mapping ────────────────────────────────────────

export const STAGE_GOAL_MAP = {
  IDLE: 'Wait for call to begin',
  OPENER: 'Land the opening question',
  PERMISSION_MOMENT: 'Earn permission to continue',
  MINI_PITCH: 'Deliver concise value statement',
  GATEKEEPER: 'Get past the gatekeeper',
  WRONG_PERSON: 'Redirect to the right contact',
  BRIDGE: 'Bridge to pain or need',
  QUALIFIER: 'Quantify the pain',
  PRICING: 'Reframe the price conversation',
  CLOSE: 'Book the meeting',
  SEED_EXIT: 'Plant a seed for future follow-up',
  OBJECTION: 'Handle the objection and reset',
  BOOKED: 'Confirm the appointment',
  EXIT: 'End the call gracefully',
  NON_CONNECT: 'Leave voicemail or text',
  ENDED: 'Call complete',
};

// ── Factory functions ───────────────────────────────────────────

/**
 * Create an empty card with all 14 fields populated with defaults.
 * @param {string} stageId
 * @returns {object}
 */
export function makeEmptyCard(stageId) {
  return {
    id: stageId,
    stage: stageId,
    moveType: STAGE_MOVE_MAP[stageId] || 'pause',
    deliveryModifier: '',
    goal: STAGE_GOAL_MAP[stageId] || '',
    primaryLine: '',
    backupLine: '',
    why: '',
    listenFor: '',
    branchPreview: '',
    clarifyingQuestion: '',
    valueProp: '',
    proofPoint: '',
    toneVariants: '',
  };
}

/**
 * Normalize a playbook stage into a v2 card.
 * Creates an empty card and fills primaryLine from the playbook.
 * @param {string} stageId
 * @param {object} playbook
 * @returns {object}
 */
export function normalizeCard(stageId, playbook) {
  const card = makeEmptyCard(stageId);
  card.primaryLine = lineForStage(stageId, playbook);
  return card;
}
