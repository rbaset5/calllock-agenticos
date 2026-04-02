// dialer/hud/risk.js
// Trajectory state and risk computation (spec Sections 6, 30)

const EXIT_PHRASES = ['gotta go', "don't call back", 'stop calling', 'leave me alone', 'hang up'];

function isExplicitExitLanguage(classification) {
  if (!classification || !classification.utterance) return false;
  const text = classification.utterance.toLowerCase();
  return EXIT_PHRASES.some(p => text.includes(p));
}

export function createTrajectoryState() {
  return {
    salvageAttemptCount: 0,
    consecutiveSameIntent: 0,
    lastPrimaryIntent: null,
    rescueMoveFailed: false,
    prospectQuestionCount: 0,
    turnsInCurrentStage: 0,
  };
}

/**
 * Compute risk level from trajectory state and current classification.
 * @param {object} trajectory - trajectory state
 * @param {object} classification - { primary: { intent }, compound, utterance? }
 * @returns {'low'|'medium'|'high'|'call_ending'}
 */
export function computeRisk(trajectory, classification) {
  if (isExplicitExitLanguage(classification)) return 'call_ending';
  if (trajectory.rescueMoveFailed && classification.primary.intent === trajectory.lastPrimaryIntent) return 'call_ending';
  if (trajectory.consecutiveSameIntent >= 3) return 'call_ending';
  if (classification.compound) return 'high';
  if (trajectory.salvageAttemptCount >= 2) return 'high';
  if (trajectory.consecutiveSameIntent >= 2) return 'medium';
  return 'low';
}

/**
 * Update trajectory state after a turn.
 * @param {object} prev - previous trajectory state
 * @param {object} classification - { primary: { intent } }
 * @param {string} stage - current stage
 * @param {boolean} wasSalvageAttempt - true if previous turn was a rescue/salvage move
 * @returns {object} updated trajectory state
 */
export function updateTrajectory(prev, classification, stage, wasSalvageAttempt) {
  const intent = classification.primary.intent;
  const sameIntent = intent === prev.lastPrimaryIntent;

  return {
    salvageAttemptCount: wasSalvageAttempt ? prev.salvageAttemptCount + 1 : prev.salvageAttemptCount,
    consecutiveSameIntent: sameIntent ? prev.consecutiveSameIntent + 1 : 1,
    lastPrimaryIntent: intent,
    rescueMoveFailed: wasSalvageAttempt && sameIntent,
    prospectQuestionCount: prev.prospectQuestionCount + (['curiosity', 'confusion'].includes(intent) ? 1 : 0),
    turnsInCurrentStage: prev.turnsInCurrentStage + 1,
  };
}
