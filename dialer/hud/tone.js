// dialer/hud/tone.js
// Rules-based tone assignment with hysteresis (spec Sections 7, 20)

import { normalize } from './classifier.js';

const RUSHED_SIGNALS = ['no thanks', 'gotta go', 'make it quick', 'busy', 'not now', "can't talk"];
const ANNOYED_SIGNALS = ['stop calling', 'i said no', 'leave me alone', "don't call", 'not interested'];
const SKEPTICAL_SIGNALS = ['doubt', "doesn't sound", 'hard to believe', 'sounds like a scam', 'too good'];
const CURIOUS_SIGNALS = ['how does', 'tell me more', 'what exactly', 'how would', 'interesting'];
const GUARDED_SIGNALS = ['we already', 'we have someone', "we're covered", 'all set'];

const IMMEDIATE_OVERRIDE_TONES = ['annoyed', 'rushed'];
const HYSTERESIS_THRESHOLD = 0.15;
const IMMEDIATE_OVERRIDE_MIN_CONFIDENCE = 0.7;

/**
 * Assign tone from utterance using rules-based heuristics.
 * @param {string} utterance
 * @param {object} classification - { primaryIntent }
 * @param {string} stage
 * @returns {{ tone_label: string, tone_confidence: number, tone_source: 'rules' }}
 */
export function assignTone(utterance, classification, stage) {
  const text = normalize(utterance);
  const words = text.split(/\s+/);
  const isShort = words.length <= 5;

  const annoyed = ANNOYED_SIGNALS.some(s => text.includes(s));
  if (annoyed) return { tone_label: 'annoyed', tone_confidence: 0.78, tone_source: 'rules' };

  const skeptical = SKEPTICAL_SIGNALS.some(s => text.includes(s));
  if (skeptical) return { tone_label: 'skeptical', tone_confidence: 0.72, tone_source: 'rules' };

  const curious = CURIOUS_SIGNALS.some(s => text.includes(s)) || classification.primaryIntent === 'curiosity';
  if (curious) return { tone_label: 'curious', tone_confidence: 0.70, tone_source: 'rules' };

  const rushed = isShort && (RUSHED_SIGNALS.some(s => text.includes(s)) || ['brush_off', 'time_pressure', 'timing'].includes(classification.primaryIntent));
  if (rushed) return { tone_label: 'rushed', tone_confidence: 0.68, tone_source: 'rules' };

  const guarded = GUARDED_SIGNALS.some(s => text.includes(s));
  if (guarded) return { tone_label: 'guarded', tone_confidence: 0.62, tone_source: 'rules' };

  return { tone_label: 'neutral', tone_confidence: 0.50, tone_source: 'rules' };
}

/**
 * Hysteresis check: should we update the displayed tone?
 * Spec Section 20:
 * - Different label required
 * - Confidence delta >= 0.15, OR same label 2+ consecutive turns, OR immediate override for annoyed/rushed at >= 0.7
 * @param {{ tone_label: string, tone_confidence: number }} current
 * @param {{ tone_label: string, tone_confidence: number }} candidate
 * @param {number} consecutiveCount - how many consecutive turns this candidate label has been seen
 * @returns {boolean}
 */
export function shouldUpdateTone(current, candidate, consecutiveCount = 0) {
  if (current.tone_label === candidate.tone_label) return false;
  if (IMMEDIATE_OVERRIDE_TONES.includes(candidate.tone_label) && candidate.tone_confidence >= IMMEDIATE_OVERRIDE_MIN_CONFIDENCE) return true;
  if (consecutiveCount >= 2) return true;
  return (candidate.tone_confidence - current.tone_confidence) >= HYSTERESIS_THRESHOLD;
}
