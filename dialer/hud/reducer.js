// dialer/hud/reducer.js
// Domain type constants + hudReducer pure function.
// Vanilla JS ES module — no build step, no TypeScript.

import { resolveBridgeLine, lineForStage } from './playbook.js';
import { createTrajectoryState } from './risk.js';

// ── Domain constants ────────────────────────────────────────────

export const STAGES = [
  'IDLE',
  'GATEKEEPER',
  'OPENER',
  'PERMISSION_MOMENT',
  'MINI_PITCH',
  'WRONG_PERSON',
  'BRIDGE',
  'QUALIFIER',
  'PRICING',
  'SEED_EXIT',
  'CLOSE',
  'OBJECTION',
  'BOOKED',
  'EXIT',
  'NON_CONNECT',
  'ENDED',
];

export const BRIDGE_ANGLES = [
  'missed_calls',
  'competition',
  'overwhelmed',
  'fallback',
  'unknown',
];

export const OBJECTION_BUCKETS = [
  'timing',
  'interest',
  'info',
  'authority',
  'unknown',
];

export const QUALIFIER_READS = [
  'pain',
  'no_pain',
  'unknown_pain',
  'unknown',
];

export const CONFIDENCE_BANDS = ['high', 'medium', 'low'];

// ── Helpers ─────────────────────────────────────────────────────

/** Map a 0-1 score to a confidence band. */
export function bandFromScore(score) {
  if (score >= 0.8) return 'high';
  if (score >= 0.6) return 'medium';
  return 'low';
}

/** True when auto-classification should be suppressed (manual override window). */
export function shouldSuppressAuto(state, atMs) {
  return atMs < state.autoClassifySuppressedUntilMs;
}

/** Build a NowCard object. */
export function makeNow(stage, line, confidence, why, source = 'none') {
  return { stage, line, confidence, why, classificationSource: source };
}

/** Count how many times a given bucket appears in objection history. */
export function objectionCountForBucket(history, bucket) {
  return history.filter((x) => x.bucket === bucket).length;
}

/** Simple engagement check — did the prospect ever ask a forward question? */
export function prospectHasEngagement(transcript) {
  const prospectTurns = transcript.filter((t) => t.speaker === 'prospect');
  const text = prospectTurns.map((t) => t.text.toLowerCase()).join(' ');
  const hasQuestion =
    text.includes('?') || /\b(how|what|why|when|who)\b/.test(text);
  return hasQuestion;
}

// ── Initial state factory ───────────────────────────────────────

export function createInitialState(playbook) {
  return {
    callId: '',
    stage: 'IDLE',
    now: makeNow('IDLE', 'Press → to start call', 'low', '→ opener script', 'none'),
    prospect: null,

    transcript: [],
    bridgeAngle: 'unknown',
    qualifierRead: 'unknown',

    objectionHistory: [],
    lastObjectionBucket: null,

    pendingCallbackTime: undefined,
    collectedEmail: undefined,
    scheduledDay: undefined,

    outcome: null,
    metrics: {
      objectionCount: 0,
      manualOverrideCount: 0,
      fallbackCount: 0,
      silenceCount: 0,
      stageChanges: 0,
    },

    autoClassifySuppressedUntilMs: 0,
    lastCommittedAtMs: 0,
    latestTranscriptSeq: 0,
    lastProcessedUtteranceSeq: 0,
    ended: false,

    // v2 state fields (spec Section 12)
    tone: 'neutral',
    toneSource: 'rules',
    toneConfidence: 0.5,
    risk: 'low',
    compound: false,
    signalCount: 0,
    recommendedActionBias: null,
    previousStage: null,
    moveType: 'pause',
    deliveryModifier: null,
    nowSummary: '',
    prospectContext: null,
    activeObjection: null,
    primaryIntent: null,

    // Trajectory state (spec Section 30)
    trajectory: createTrajectoryState(),
  };
}

// ── Reducer ─────────────────────────────────────────────────────

/**
 * Pure reducer: (state, action, playbook) → newState
 *
 * Every action must carry `callSid`. The reducer rejects events when
 * `action.callSid !== state.callId` (except INIT_CALL which sets it).
 *
 * LLM_RESULT carries `seq` (or numeric `utteranceId` for backwards compatibility).
 * Rejected if that utterance has been superseded.
 */
export function hudReducer(state, action, playbook) {
  // ── Guard: reject stale callSid (except INIT_CALL) ──
  if (action.type !== 'INIT_CALL') {
    if (action.callSid !== undefined && action.callSid !== state.callId) {
      return state;
    }
  }

  switch (action.type) {
    // ────────────────────────────────────────────────────
    case 'INIT_CALL': {
      return {
        ...createInitialState(playbook),
        callId: action.callId,
        prospect: action.prospect ?? null,
        stage: 'GATEKEEPER',
        now: makeNow(
          'GATEKEEPER',
          playbook.gatekeeper.reach,
          'high',
          'Start gatekeeper flow',
          'manual',
        ),
        lastCommittedAtMs: action.atMs,
      };
    }

    // ────────────────────────────────────────────────────
    case 'CALL_CONNECTED': {
      return {
        ...state,
        stage: 'OPENER',
        now: makeNow('OPENER', playbook.opener, 'high', 'Direct connect', 'manual'),
        metrics: {
          ...state.metrics,
          stageChanges: state.metrics.stageChanges + 1,
        },
        lastCommittedAtMs: action.atMs,
      };
    }

    // ────────────────────────────────────────────────────
    case 'NO_ANSWER':
    case 'MANUAL_NON_CONNECT': {
      return {
        ...state,
        stage: 'NON_CONNECT',
        outcome: 'non_connect',
        now: makeNow('NON_CONNECT', playbook.voicemail, 'high', 'Voicemail mode', 'manual'),
        metrics: {
          ...state.metrics,
          manualOverrideCount:
            action.type === 'MANUAL_NON_CONNECT'
              ? state.metrics.manualOverrideCount + 1
              : state.metrics.manualOverrideCount,
        },
        lastCommittedAtMs: action.atMs,
      };
    }

    // ────────────────────────────────────────────────────
    case 'TRANSCRIPT_FINAL': {
      if (state.ended) return state;
      const nextTranscriptSeq =
        typeof action.seq === 'number'
          ? Math.max(state.latestTranscriptSeq, action.seq)
          : state.latestTranscriptSeq;
      if (shouldSuppressAuto(state, action.atMs)) {
        return {
          ...state,
          transcript: [...state.transcript, action.turn],
          latestTranscriptSeq: nextTranscriptSeq,
        };
      }

      const nextState = {
        ...state,
        transcript: [...state.transcript, action.turn],
        latestTranscriptSeq: nextTranscriptSeq,
      };

      const rule = action.rule;
      if (!rule || rule.band === 'low') {
        return nextState;
      }

      // Cross-stage booking: yes-intent from any advanced stage → BOOKED
      // PRICING included: "Fine Thursday at 2" during pricing should book, not just exit pricing
      if (['BRIDGE', 'QUALIFIER', 'CLOSE', 'PRICING'].includes(state.stage) && rule.detectedIntent === 'yes') {
        return {
          ...nextState,
          stage: 'BOOKED',
          outcome: 'booked',
          now: makeNow('BOOKED', playbook.booked, rule.band, 'Prospect accepted — booking confirmed', 'rules'),
          metrics: { ...nextState.metrics, stageChanges: nextState.metrics.stageChanges + 1 },
          lastCommittedAtMs: action.atMs,
        };
      }

      // Callback accepted: prospect offers a specific follow-up time from CLOSE/OBJECTION.
      // This is a soft booking — confirm the day, get the number, keep it short.
      if (['CLOSE', 'OBJECTION'].includes(state.stage) && rule.detectedIntent === 'callback_accepted') {
        return {
          ...nextState,
          stage: 'BOOKED',
          outcome: 'callback_booked',
          now: makeNow('BOOKED', playbook.callbackBooked, rule.band, 'Callback accepted — confirm and close', 'rules'),
          metrics: { ...nextState.metrics, stageChanges: nextState.metrics.stageChanges + 1 },
          lastCommittedAtMs: action.atMs,
        };
      }

      // Cross-stage special intent → OBJECTION
      // These intents have dedicated objection cards and playbook scripts.
      // Route from any non-terminal stage so the rep gets the right response.
      const SPECIAL_INTENT_BUCKETS = ['tried_ai', 'existing_coverage', 'answering_service', 'referral_only', 'competitor_comparison'];
      if (SPECIAL_INTENT_BUCKETS.includes(rule.detectedIntent)
          && !['IDLE', 'EXIT', 'ENDED', 'BOOKED', 'SEED_EXIT', 'NON_CONNECT'].includes(state.stage)
          && playbook.objections[rule.detectedIntent]) {
        // BRIDGE guard: no-pain signals should exit gracefully via SEED_EXIT, not enter objection loop
        const isBridgeNoPain = state.stage === 'BRIDGE' && (() => {
          const utt = (action.turn?.text || '').toLowerCase();
          const NO_PAIN = /\b(don'?t miss|we'?re covered|fully covered|we'?re good|we are good|not looking to change|not interested in changing|she handles everything|he handles everything|we do not miss)\b/;
          return NO_PAIN.test(utt) && !/\b\d+\b/.test(utt);
        })();
        if (!isBridgeNoPain) {
          const updatedHistory = [...nextState.objectionHistory, { bucket: rule.detectedIntent, atMs: action.atMs, utterance: action.turn.text }];
          // Same special intent twice → prospect is firm, exit gracefully
          if (state.stage === 'OBJECTION' && objectionCountForBucket(updatedHistory, rule.detectedIntent) >= 2) {
            return {
              ...nextState,
              stage: 'EXIT',
              outcome: 'not_booked',
              objectionHistory: updatedHistory,
              now: makeNow('EXIT', playbook.exit, rule.band, `Same special intent repeated: ${rule.detectedIntent}`, 'rules'),
              metrics: { ...nextState.metrics, stageChanges: nextState.metrics.stageChanges + 1, objectionCount: nextState.metrics.objectionCount + 1 },
              lastCommittedAtMs: action.atMs,
            };
          }
          return {
            ...nextState,
            stage: 'OBJECTION',
            lastObjectionBucket: rule.detectedIntent,
            activeObjection: rule.detectedIntent,
            objectionHistory: updatedHistory,
            now: makeNow('OBJECTION', playbook.objections[rule.detectedIntent].reset, rule.band, rule.why || `Special intent: ${rule.detectedIntent}`, 'rules'),
            metrics: { ...nextState.metrics, stageChanges: nextState.metrics.stageChanges + 1, objectionCount: nextState.metrics.objectionCount + 1 },
            lastCommittedAtMs: action.atMs,
          };
        }
        // isBridgeNoPain: fall through to BRIDGE handler → SEED_EXIT
      }

      // OPENER → EXIT on brush_off (DNC, wrong number, voicemail, hostile)
      if (state.stage === 'OPENER' && rule.detectedIntent === 'brush_off') {
        return {
          ...nextState,
          stage: 'EXIT',
          outcome: 'not_booked',
          now: makeNow('EXIT', playbook.exit, rule.band, 'Exit intent from opener', 'rules'),
          metrics: { ...nextState.metrics, stageChanges: nextState.metrics.stageChanges + 1 },
          lastCommittedAtMs: action.atMs,
        };
      }

      // OPENER → BRIDGE (or OBJECTION if prospect rejects)
      if (state.stage === 'OPENER') {
        // If prospect objects ("not interested", etc.), route to OBJECTION not BRIDGE
        if (rule.objectionBucket && ['timing', 'interest', 'info', 'authority'].includes(rule.objectionBucket)) {
          const bucket = rule.objectionBucket === 'unknown' ? 'interest' : rule.objectionBucket;
          return {
            ...nextState,
            stage: 'OBJECTION',
            lastObjectionBucket: bucket,
            activeObjection: bucket,
            objectionHistory: [...nextState.objectionHistory, { bucket, atMs: action.atMs, utterance: action.turn.text }],
            now: makeNow('OBJECTION', playbook.objections[bucket].reset, rule.band, rule.why, 'rules'),
            metrics: { ...nextState.metrics, stageChanges: nextState.metrics.stageChanges + 1, objectionCount: nextState.metrics.objectionCount + 1 },
            lastCommittedAtMs: action.atMs,
          };
        }
        return {
          ...nextState,
          stage: 'BRIDGE',
          now: makeNow(
            'BRIDGE',
            resolveBridgeLine(rule, playbook),
            rule.band,
            rule.why,
            'rules',
          ),
          bridgeAngle: rule.bridgeAngle ?? 'unknown',
          metrics: {
            ...nextState.metrics,
            stageChanges: nextState.metrics.stageChanges + 1,
          },
          lastCommittedAtMs: action.atMs,
        };
      }

      // MINI_PITCH → BRIDGE (any substantive response advances, pain signals get angle)
      if (state.stage === 'MINI_PITCH') {
        const bridgeLine = rule.bridgeAngle
          ? resolveBridgeLine(rule, playbook)
          : playbook.bridge.fallback;
        return {
          ...nextState,
          stage: 'BRIDGE',
          bridgeAngle: rule.bridgeAngle ?? state.bridgeAngle ?? 'unknown',
          now: makeNow('BRIDGE', bridgeLine, rule.band, 'Mini pitch delivered, entering discovery', 'rules'),
          metrics: { ...nextState.metrics, stageChanges: nextState.metrics.stageChanges + 1 },
          lastCommittedAtMs: action.atMs,
        };
      }

      // PRICING → CLOSE if qualifier pain data present, otherwise return to previousStage
      if (state.stage === 'PRICING') {
        // If the pricing redirect yielded qualifier pain (prospect answered "how many calls?"),
        // skip back to QUALIFIER and go straight to CLOSE with their number.
        if (rule.qualifierRead === 'pain') {
          const painCount = rule.painCount || null;
          const closeLine = painCount
            ? `${painCount} calls a week slipping through... that adds up fast. Worth 15 minutes? Thursday or Friday?`
            : playbook.close;
          return {
            ...nextState,
            stage: 'CLOSE',
            previousStage: null,
            qualifierRead: 'pain',
            painCount,
            now: makeNow('CLOSE', closeLine, rule.band, 'Pain quantified during pricing redirect', 'rules'),
            metrics: { ...nextState.metrics, stageChanges: nextState.metrics.stageChanges + 1 },
            lastCommittedAtMs: action.atMs,
          };
        }
        const returnStage = state.previousStage || 'QUALIFIER';
        return {
          ...nextState,
          stage: returnStage,
          previousStage: null,
          now: makeNow(returnStage, lineForStage(returnStage, playbook), rule.band, 'Pricing redirected, back to discovery', 'rules'),
          metrics: { ...nextState.metrics, stageChanges: nextState.metrics.stageChanges + 1 },
          lastCommittedAtMs: action.atMs,
        };
      }

      // WRONG_PERSON → EXIT on brush_off/exit-intent (gatekeeper says goodbye)
      if (state.stage === 'WRONG_PERSON' && rule.detectedIntent === 'brush_off') {
        return {
          ...nextState,
          stage: 'EXIT',
          outcome: 'not_booked',
          now: makeNow('EXIT', playbook.exit, rule.band, 'Gatekeeper ended the conversation', 'rules'),
          metrics: { ...nextState.metrics, stageChanges: nextState.metrics.stageChanges + 1 },
          lastCommittedAtMs: action.atMs,
        };
      }

      // WRONG_PERSON → OPENER (any substantive response means someone is engaging)
      if (state.stage === 'WRONG_PERSON') {
        return {
          ...nextState,
          stage: 'OPENER',
          now: makeNow('OPENER', playbook.opener, rule.band, 'Re-engaging from wrong person', 'rules'),
          metrics: { ...nextState.metrics, stageChanges: nextState.metrics.stageChanges + 1 },
          lastCommittedAtMs: action.atMs,
        };
      }

      // BRIDGE → OBJECTION (if prospect objects during bridge)
      if (state.stage === 'BRIDGE' && rule.objectionBucket && ['timing', 'interest', 'info', 'authority'].includes(rule.objectionBucket)) {
        const bucket = rule.objectionBucket === 'unknown' ? 'interest' : rule.objectionBucket;
        return {
          ...nextState,
          stage: 'OBJECTION',
          lastObjectionBucket: bucket,
          activeObjection: bucket,
          objectionHistory: [...nextState.objectionHistory, { bucket, atMs: action.atMs, utterance: action.turn.text }],
          now: makeNow('OBJECTION', playbook.objections[bucket].reset, rule.band, `Objection during bridge: ${bucket}`, 'rules'),
          metrics: { ...nextState.metrics, stageChanges: nextState.metrics.stageChanges + 1, objectionCount: nextState.metrics.objectionCount + 1 },
          lastCommittedAtMs: action.atMs,
        };
      }

      // BRIDGE → QUALIFIER (or SEED_EXIT if prospect explicitly denies pain)
      if (state.stage === 'BRIDGE') {
        // Check if the utterance contains explicit no-pain signal.
        // "We don't miss calls", "we're fully covered" contain bridge keywords
        // but actually indicate zero pain — should go to SEED_EXIT, not QUALIFIER.
        const utteranceText = (action.turn?.text || '').toLowerCase();
        const NO_PAIN_SIGNALS = /\b(don'?t miss|we'?re covered|fully covered|we'?re good|we are good|have a receptionist|not looking to change|not interested in changing|she handles everything|he handles everything|we do not miss)\b/;
        const hasPainDenial = NO_PAIN_SIGNALS.test(utteranceText);
        // Only trigger SEED_EXIT if there's NO quantified pain (no numbers like "5 a week")
        const hasQuantifiedPain = /\b\d+\b/.test(utteranceText);

        if (hasPainDenial && !hasQuantifiedPain) {
          return {
            ...nextState,
            stage: 'SEED_EXIT',
            qualifierRead: 'no_pain',
            outcome: 'seed_exit',
            now: makeNow(
              'SEED_EXIT',
              playbook.seedExit,
              rule.band,
              'No pain signal during bridge — prospect is covered',
              'rules',
            ),
            bridgeAngle: rule.bridgeAngle ?? state.bridgeAngle,
            metrics: {
              ...nextState.metrics,
              stageChanges: nextState.metrics.stageChanges + 1,
            },
            lastCommittedAtMs: action.atMs,
          };
        }

        return {
          ...nextState,
          stage: 'QUALIFIER',
          now: makeNow(
            'QUALIFIER',
            playbook.qualifier,
            'high',
            'Bridge delivered; qualify before close',
            'rules',
          ),
          bridgeAngle: rule.bridgeAngle ?? state.bridgeAngle,
          metrics: {
            ...nextState.metrics,
            stageChanges: nextState.metrics.stageChanges + 1,
          },
          lastCommittedAtMs: action.atMs,
        };
      }

      // QUALIFIER → CLOSE / SEED_EXIT
      if (state.stage === 'QUALIFIER') {
        if (rule.qualifierRead === 'pain') {
          const painCount = rule.painCount || null;
          const closeLine = painCount
            ? `${painCount} calls a week slipping through... that adds up fast. Worth 15 minutes? Thursday or Friday?`
            : playbook.close;
          return {
            ...nextState,
            stage: 'CLOSE',
            qualifierRead: 'pain',
            painCount,
            now: makeNow('CLOSE', closeLine, rule.band, 'Pain detected', 'rules'),
            metrics: {
              ...nextState.metrics,
              stageChanges: nextState.metrics.stageChanges + 1,
            },
            lastCommittedAtMs: action.atMs,
          };
        }

        if (rule.qualifierRead === 'no_pain') {
          return {
            ...nextState,
            stage: 'SEED_EXIT',
            qualifierRead: 'no_pain',
            outcome: 'seed_exit',
            now: makeNow(
              'SEED_EXIT',
              playbook.seedExit,
              rule.band,
              'Low pain; do not push close',
              'rules',
            ),
            metrics: {
              ...nextState.metrics,
              stageChanges: nextState.metrics.stageChanges + 1,
            },
            lastCommittedAtMs: action.atMs,
          };
        }

        if (rule.qualifierRead === 'unknown_pain') {
          return {
            ...nextState,
            stage: 'CLOSE',
            qualifierRead: 'unknown_pain',
            now: makeNow(
              'CLOSE',
              `That's usually where the problem hides. ${playbook.close}`,
              rule.band,
              'Unmeasured pain',
              'rules',
            ),
            metrics: {
              ...nextState.metrics,
              stageChanges: nextState.metrics.stageChanges + 1,
            },
            lastCommittedAtMs: action.atMs,
          };
        }
      }

      // CLOSE → OBJECTION
      if (state.stage === 'CLOSE' && rule.objectionBucket) {
        const bucket =
          rule.objectionBucket === 'unknown' ? 'interest' : rule.objectionBucket;
        const historyItem = {
          bucket: rule.objectionBucket,
          atMs: action.atMs,
          utterance: action.turn.text,
          ...(action.secondaryIntent ? { secondary: action.secondaryIntent } : {}),
        };

        return {
          ...nextState,
          stage: 'OBJECTION',
          objectionHistory: [...nextState.objectionHistory, historyItem],
          lastObjectionBucket: rule.objectionBucket,
          activeObjection: rule.objectionBucket,
          now: makeNow(
            'OBJECTION',
            playbook.objections[bucket].reset,
            rule.band,
            `Objection: ${rule.objectionBucket}`,
            'rules',
          ),
          metrics: {
            ...nextState.metrics,
            objectionCount: nextState.metrics.objectionCount + 1,
            stageChanges: nextState.metrics.stageChanges + 1,
          },
          lastCommittedAtMs: action.atMs,
        };
      }

      // OBJECTION → BRIDGE when prospect gives an engaged/pain response (no objectionBucket)
      // e.g., "Well yeah after hours goes to voicemail" while in OBJECTION
      if (state.stage === 'OBJECTION' && !rule.objectionBucket && (rule.bridgeAngle || rule.qualifierRead || rule.detectedIntent === 'yes' || rule.detectedIntent === 'engaged_answer' || rule.detectedIntent === 'curiosity')) {
        const bridgeAngle = rule.bridgeAngle || state.bridgeAngle || 'fallback';
        return {
          ...nextState,
          stage: 'BRIDGE',
          bridgeAngle,
          now: makeNow(
            'BRIDGE',
            resolveBridgeLine(rule, playbook),
            rule.band,
            'Prospect engaged after objection — advancing to discovery',
            'rules',
          ),
          metrics: { ...nextState.metrics, stageChanges: nextState.metrics.stageChanges + 1 },
          lastCommittedAtMs: action.atMs,
        };
      }

      // OBJECTION → handle follow-up objections via rules
      if (state.stage === 'OBJECTION' && rule.objectionBucket) {
        const bucket =
          rule.objectionBucket === 'unknown' ? 'interest' : rule.objectionBucket;
        const historyItem = {
          bucket: rule.objectionBucket,
          atMs: action.atMs,
          utterance: action.turn.text,
          ...(action.secondaryIntent ? { secondary: action.secondaryIntent } : {}),
        };
        const updatedHistory = [...nextState.objectionHistory, historyItem];
        const countSame = objectionCountForBucket(updatedHistory, rule.objectionBucket);

        // Pain override: if the prospect's objection ALSO contains bridge/pain signals,
        // exit to BRIDGE. Pain admission during an objection = engagement, not rejection.
        // "We miss some calls after hours" + "I don't trust AI" → pain wins.
        const utteranceText = (action.turn?.text || '').toLowerCase();
        const BRIDGE_PAIN_SIGNALS = /\b(miss\w*\s+calls?|voicemail|go(es)?\s+to\s+voicemail|can't\s+answer|unanswered|after\s*hours?|weekends?|lose\s+(calls?|jobs?|customers?)|called\s+somebody\s+else|call\w*\s+someone\s+else|ring\s+them\s+back)\b/;
        if (BRIDGE_PAIN_SIGNALS.test(utteranceText)) {
          const bridgeAngle = /\b(after\s*hours?|weekends?)\b/.test(utteranceText) ? 'after_hours' : 'missed_calls';
          return {
            ...nextState,
            stage: 'BRIDGE',
            bridgeAngle,
            objectionHistory: updatedHistory,
            now: makeNow(
              'BRIDGE',
              resolveBridgeLine({ bridgeAngle }, playbook),
              rule.band,
              'Pain signal during objection — advancing to discovery',
              'rules',
            ),
            metrics: {
              ...nextState.metrics,
              objectionCount: nextState.metrics.objectionCount + 1,
              stageChanges: nextState.metrics.stageChanges + 1,
            },
            lastCommittedAtMs: action.atMs,
          };
        }

        // same bucket twice → exit (prospect is firm, stop pushing)
        if (countSame >= 2) {
          const hasBridgeSignal = BRIDGE_PAIN_SIGNALS.test(utteranceText);
          if (hasBridgeSignal) {
            return {
              ...nextState,
              stage: 'BRIDGE',
              bridgeAngle: 'missed_calls',
              objectionHistory: updatedHistory,
              now: makeNow(
                'BRIDGE',
                resolveBridgeLine({ bridgeAngle: 'missed_calls' }, playbook),
                rule.band,
                'Bridge signal overrides same-bucket exit — pain detected',
                'rules',
              ),
              metrics: {
                ...nextState.metrics,
                objectionCount: nextState.metrics.objectionCount + 1,
                stageChanges: nextState.metrics.stageChanges + 1,
              },
              lastCommittedAtMs: action.atMs,
            };
          }

          return {
            ...nextState,
            stage: 'EXIT',
            outcome: 'not_booked',
            objectionHistory: updatedHistory,
            lastObjectionBucket: rule.objectionBucket,
            activeObjection: rule.objectionBucket,
            now: makeNow(
              'EXIT',
              playbook.exit,
              rule.band,
              'Same objection bucket repeated — prospect is firm',
              'rules',
            ),
            metrics: {
              ...nextState.metrics,
              objectionCount: nextState.metrics.objectionCount + 1,
              stageChanges: nextState.metrics.stageChanges + 1,
            },
            lastCommittedAtMs: action.atMs,
          };
        }

        // 4th+ objection overall + no engagement → exit
        // (3 different buckets is normal pushback, keep trying)
        // BUT: if the utterance also contains a bridge signal ("miss calls"),
        // the pain overrides the count-based exit — route to BRIDGE instead.
        if (
          nextState.metrics.objectionCount + 1 >= 4 &&
          !prospectHasEngagement(nextState.transcript)
        ) {
          // Check for bridge keywords in the utterance before exiting
          const utteranceText = (action.turn?.text || '').toLowerCase();
          const hasBridgeSignal = /\b(miss\w*\s+calls?|voicemail|go(es)?\s+to\s+voicemail|can't\s+answer|unanswered)\b/.test(utteranceText);
          if (hasBridgeSignal) {
            return {
              ...nextState,
              stage: 'BRIDGE',
              bridgeAngle: 'missed_calls',
              objectionHistory: updatedHistory,
              now: makeNow(
                'BRIDGE',
                resolveBridgeLine({ bridgeAngle: 'missed_calls' }, playbook),
                rule.band,
                'Bridge signal overrides objection count — pain detected',
                'rules',
              ),
              metrics: {
                ...nextState.metrics,
                objectionCount: nextState.metrics.objectionCount + 1,
                stageChanges: nextState.metrics.stageChanges + 1,
              },
              lastCommittedAtMs: action.atMs,
            };
          }

          return {
            ...nextState,
            stage: 'EXIT',
            outcome: 'not_booked',
            objectionHistory: updatedHistory,
            lastObjectionBucket: rule.objectionBucket,
            activeObjection: rule.objectionBucket,
            now: makeNow(
              'EXIT',
              playbook.exit,
              rule.band,
              'Third objection with no engagement',
              'rules',
            ),
            metrics: {
              ...nextState.metrics,
              objectionCount: nextState.metrics.objectionCount + 1,
              stageChanges: nextState.metrics.stageChanges + 1,
            },
            lastCommittedAtMs: action.atMs,
          };
        }

        // different bucket → show reset line
        return {
          ...nextState,
          objectionHistory: updatedHistory,
          lastObjectionBucket: rule.objectionBucket,
          activeObjection: rule.objectionBucket,
          now: makeNow(
            'OBJECTION',
            playbook.objections[bucket].reset,
            rule.band,
            `Objection: ${rule.objectionBucket}`,
            'rules',
          ),
          metrics: {
            ...nextState.metrics,
            objectionCount: nextState.metrics.objectionCount + 1,
          },
          lastCommittedAtMs: action.atMs,
        };
      }

      return nextState;
    }

    // ────────────────────────────────────────────────────
    case 'RULES_NO_MATCH': {
      if (state.stage === 'BRIDGE') {
        return {
          ...state,
          bridgeAngle: 'fallback',
          now: makeNow(
            'BRIDGE',
            playbook.bridge.fallback,
            'low',
            'No bridge match; fallback question',
            'fallback',
          ),
          metrics: {
            ...state.metrics,
            fallbackCount: state.metrics.fallbackCount + 1,
          },
        };
      }

      if (state.stage === 'QUALIFIER') {
        return {
          ...state,
          qualifierRead: 'unknown_pain',
          now: makeNow(
            'QUALIFIER',
            `That's usually where the problem hides. ${playbook.close}`,
            'low',
            'Qualifier unclear',
            'fallback',
          ),
          metrics: {
            ...state.metrics,
            fallbackCount: state.metrics.fallbackCount + 1,
          },
        };
      }

      if (state.stage === 'OBJECTION') {
        return {
          ...state,
          now: makeNow(
            'OBJECTION',
            playbook.qualifier,
            'low',
            'Objection unclear; route to qualifier',
            'fallback',
          ),
          metrics: {
            ...state.metrics,
            fallbackCount: state.metrics.fallbackCount + 1,
          },
        };
      }

      return state;
    }

    // ────────────────────────────────────────────────────
    case 'LLM_RESULT': {
      if (state.ended) return state;

      // Reject if manual override suppression is active (adversarial finding #12)
      if (shouldSuppressAuto(state, action.atMs)) return state;

      const incomingSeq =
        typeof action.seq === 'number'
          ? action.seq
          : typeof action.utteranceId === 'number'
            ? action.utteranceId
            : null;

      if (
        typeof incomingSeq === 'number' &&
        state.latestTranscriptSeq > 0 &&
        incomingSeq < state.latestTranscriptSeq
      ) {
        return state;
      }

      if (typeof incomingSeq === 'number' && incomingSeq <= state.lastProcessedUtteranceSeq) {
        return state;
      }

      const nextSeq =
        typeof incomingSeq === 'number'
          ? incomingSeq
          : state.lastProcessedUtteranceSeq;

      // ── Side-stage exits (LLM or rules-fallthrough) ──────────
      // MINI_PITCH: any response advances to BRIDGE
      if (state.stage === 'MINI_PITCH') {
        const bridgeAngle = action.result.bridgeAngle || state.bridgeAngle || 'fallback';
        return {
          ...state,
          stage: 'BRIDGE',
          bridgeAngle,
          now: makeNow(
            'BRIDGE',
            resolveBridgeLine(action.result, playbook),
            action.result.band,
            action.result.why || 'Advanced from mini pitch',
            action.result.confidence >= 0.6 ? 'llm' : 'rules',
          ),
          lastCommittedAtMs: action.atMs,
          lastProcessedUtteranceSeq: nextSeq,
        };
      }

      // WRONG_PERSON: advance to OPENER on any substantive response
      // (the real person may have picked up, or the gatekeeper is engaging)
      if (state.stage === 'WRONG_PERSON') {
        return {
          ...state,
          stage: 'OPENER',
          now: makeNow(
            'OPENER',
            playbook.opener,
            action.result.band,
            action.result.why || 'Re-engaging from wrong person',
            action.result.confidence >= 0.6 ? 'llm' : 'rules',
          ),
          lastCommittedAtMs: action.atMs,
          lastProcessedUtteranceSeq: nextSeq,
        };
      }

      // PRICING: return to previousStage (default QUALIFIER) on engagement
      if (state.stage === 'PRICING') {
        const returnStage = state.previousStage || 'QUALIFIER';
        const returnLine = returnStage === 'QUALIFIER'
          ? playbook.qualifier
          : returnStage === 'BRIDGE'
            ? resolveBridgeLine(action.result, playbook)
            : playbook.opener;
        return {
          ...state,
          stage: returnStage,
          previousStage: null,
          now: makeNow(
            returnStage,
            returnLine,
            action.result.band,
            action.result.why || 'Returned from pricing',
            action.result.confidence >= 0.6 ? 'llm' : 'rules',
          ),
          lastCommittedAtMs: action.atMs,
          lastProcessedUtteranceSeq: nextSeq,
        };
      }

      // CONFUSION: same as MINI_PITCH — advance to BRIDGE
      if (state.stage === 'CONFUSION') {
        const bridgeAngle = action.result.bridgeAngle || state.bridgeAngle || 'fallback';
        return {
          ...state,
          stage: 'BRIDGE',
          bridgeAngle,
          now: makeNow(
            'BRIDGE',
            resolveBridgeLine(action.result, playbook),
            action.result.band,
            action.result.why || 'Advanced from confusion',
            action.result.confidence >= 0.6 ? 'llm' : 'rules',
          ),
          lastCommittedAtMs: action.atMs,
          lastProcessedUtteranceSeq: nextSeq,
        };
      }

      // ── Existing stage refinements ─────────────────────
      if (state.stage === 'BRIDGE' && action.result.bridgeAngle) {
        return {
          ...state,
          bridgeAngle: action.result.bridgeAngle,
          now: makeNow(
            'BRIDGE',
            resolveBridgeLine(action.result, playbook),
            action.result.band,
            action.result.why,
            'llm',
          ),
          lastCommittedAtMs: action.atMs,
          lastProcessedUtteranceSeq: nextSeq,
        };
      }

      if (state.stage === 'QUALIFIER' && action.result.qualifierRead) {
        if (action.result.qualifierRead === 'pain') {
          return {
            ...state,
            stage: 'CLOSE',
            qualifierRead: 'pain',
            now: makeNow(
              'CLOSE',
              playbook.close,
              action.result.band,
              action.result.why,
              'llm',
            ),
            lastCommittedAtMs: action.atMs,
            lastProcessedUtteranceSeq: nextSeq,
          };
        }

        if (action.result.qualifierRead === 'no_pain') {
          return {
            ...state,
            stage: 'SEED_EXIT',
            qualifierRead: 'no_pain',
            outcome: 'seed_exit',
            now: makeNow(
              'SEED_EXIT',
              playbook.seedExit,
              action.result.band,
              action.result.why,
              'llm',
            ),
            lastCommittedAtMs: action.atMs,
            lastProcessedUtteranceSeq: nextSeq,
          };
        }

        // unknown_pain or anything else
        return {
          ...state,
          stage: 'CLOSE',
          qualifierRead: 'unknown_pain',
          now: makeNow(
            'CLOSE',
            `That's usually where the problem hides. ${playbook.close}`,
            action.result.band,
            action.result.why,
            'llm',
          ),
          lastCommittedAtMs: action.atMs,
          lastProcessedUtteranceSeq: nextSeq,
        };
      }

      // OBJECTION + engaged response (no objectionBucket) → advance to BRIDGE
      if (state.stage === 'OBJECTION' && !action.result.objectionBucket) {
        const bridgeAngle = action.result.bridgeAngle || state.bridgeAngle || 'fallback';
        return {
          ...state,
          stage: 'BRIDGE',
          bridgeAngle,
          now: makeNow(
            'BRIDGE',
            resolveBridgeLine(action.result, playbook),
            action.result.band,
            action.result.why || 'Prospect engaged after objection',
            action.result.confidence >= 0.6 ? 'llm' : 'rules',
          ),
          lastCommittedAtMs: action.atMs,
          lastProcessedUtteranceSeq: nextSeq,
        };
      }

      if (state.stage === 'OBJECTION' && action.result.objectionBucket) {
        const bucket =
          action.result.objectionBucket === 'unknown'
            ? 'interest'
            : action.result.objectionBucket;
        const historyItem = {
          bucket: action.result.objectionBucket,
          atMs: action.atMs,
          utterance: action.result.utterance ?? '',
        };
        const updatedHistory = [...state.objectionHistory, historyItem];
        const countSame = objectionCountForBucket(
          updatedHistory,
          action.result.objectionBucket,
        );

        // same bucket twice → qualifier
        if (countSame >= 2) {
          return {
            ...state,
            stage: 'QUALIFIER',
            objectionHistory: updatedHistory,
            lastObjectionBucket: action.result.objectionBucket,
            now: makeNow(
              'QUALIFIER',
              playbook.qualifier,
              action.result.band,
              'Same objection bucket twice',
              'llm',
            ),
            metrics: {
              ...state.metrics,
              objectionCount: state.metrics.objectionCount + 1,
            },
            lastCommittedAtMs: action.atMs,
            lastProcessedUtteranceSeq: nextSeq,
          };
        }

        // 3rd objection + no engagement → exit
        if (
          state.metrics.objectionCount + 1 >= 3 &&
          !prospectHasEngagement(state.transcript)
        ) {
          return {
            ...state,
            stage: 'EXIT',
            outcome: 'not_booked',
            objectionHistory: updatedHistory,
            lastObjectionBucket: action.result.objectionBucket,
            now: makeNow(
              'EXIT',
              playbook.exit,
              action.result.band,
              'Third objection with no engagement',
              'llm',
            ),
            metrics: {
              ...state.metrics,
              objectionCount: state.metrics.objectionCount + 1,
            },
            lastCommittedAtMs: action.atMs,
            lastProcessedUtteranceSeq: nextSeq,
          };
        }

        // different bucket → reset then close
        return {
          ...state,
          objectionHistory: updatedHistory,
          lastObjectionBucket: action.result.objectionBucket,
          now: makeNow(
            'OBJECTION',
            playbook.objections[bucket].reset,
            action.result.band,
            `Objection: ${action.result.objectionBucket}`,
            'llm',
          ),
          metrics: {
            ...state.metrics,
            objectionCount: state.metrics.objectionCount + 1,
          },
          lastCommittedAtMs: action.atMs,
          lastProcessedUtteranceSeq: nextSeq,
        };
      }

      return state;
    }

    // ────────────────────────────────────────────────────
    case 'LLM_FAILED': {
      return {
        ...state,
        metrics: {
          ...state.metrics,
          fallbackCount: state.metrics.fallbackCount + 1,
        },
      };
    }

    // ────────────────────────────────────────────────────
    case 'HEDGE_REQUESTED': {
      if (state.stage !== 'CLOSE' && state.stage !== 'OBJECTION') return state;
      return {
        ...state,
        stage: 'CLOSE',
        now: makeNow('CLOSE', playbook.hedge, 'high', '→ yes! → booked · F10 objection', 'manual'),
        lastCommittedAtMs: action.atMs,
      };
    }

    // ────────────────────────────────────────────────────
    case 'BOOKING_CONFIRMED': {
      return {
        ...state,
        stage: 'BOOKED',
        outcome: 'booked',
        collectedEmail: action.email ?? state.collectedEmail,
        scheduledDay: action.day ?? state.scheduledDay,
        now: makeNow('BOOKED', playbook.booked, 'high', 'Meeting booked', 'manual'),
        lastCommittedAtMs: action.atMs,
      };
    }

    // ────────────────────────────────────────────────────
    case 'SET_CALLBACK_TIME': {
      return {
        ...state,
        pendingCallbackTime: action.value,
        outcome: 'callback_set',
      };
    }

    // ────────────────────────────────────────────────────
    case 'MANUAL_SET_STAGE': {
      const stageHints = {
        GATEKEEPER:        '→ got owner · F10 not available',
        OPENER:            '→ when they respond',
        PERMISSION_MOMENT: '→ testing if they will give space',
        MINI_PITCH:        '→ 1-sentence answer to "what is this?"',
        WRONG_PERSON:      '→ getting referral to decision-maker',
        BRIDGE:            '→ after bridge line',
        QUALIFIER:         '→ pain → close · F10 no pain → exit',
        PRICING:           '→ redirecting from premature pricing',
        CLOSE:             '→ yes! → booked · F10 objection · ⇧ hedge',
        OBJECTION:         '→ try close · F10 give up · 1-4 new objection',
        SEED_EXIT:         '→ wrap up',
        BOOKED:            '→ call done',
        NON_CONNECT:       '→ after voicemail',
        EXIT:              'Call complete',
      };
      return {
        ...state,
        stage: action.stage,
        previousStage: null,
        // Clear activeObjection when leaving OBJECTION to prevent stale overlay
        activeObjection: action.stage === 'OBJECTION' ? state.activeObjection : null,
        // Clear objection bucket when navigating to OBJECTION so the picker shows
        lastObjectionBucket:
          action.stage === 'OBJECTION' ? null : state.lastObjectionBucket,
        now: makeNow(
          action.stage,
          lineForStage(action.stage, playbook),
          'high',
          stageHints[action.stage] || 'Manual override',
          'manual',
        ),
        autoClassifySuppressedUntilMs: action.atMs + 4000,
        metrics: {
          ...state.metrics,
          manualOverrideCount: state.metrics.manualOverrideCount + 1,
          stageChanges: state.metrics.stageChanges + 1,
        },
        lastCommittedAtMs: action.atMs,
      };
    }

    // ────────────────────────────────────────────────────
    case 'AUTO_SET_STAGE': {
      if (!STAGES.includes(action.stage)) return state;
      const stageHints = {
        MINI_PITCH: 'Prospect is confused; clarify in one sentence',
        WRONG_PERSON: 'Prospect redirected you to a different decision-maker',
        EXIT: 'Prospect signaled the conversation should end',
      };
      return {
        ...state,
        stage: action.stage,
        previousStage: action.clearPreviousStage === false ? state.previousStage : null,
        activeObjection: action.stage === 'OBJECTION' ? state.activeObjection : null,
        lastObjectionBucket:
          action.stage === 'OBJECTION' ? null : state.lastObjectionBucket,
        now: makeNow(
          action.stage,
          lineForStage(action.stage, playbook),
          action.confidence || 'high',
          action.why || stageHints[action.stage] || 'Automatic route',
          action.source || 'rules',
        ),
        metrics: {
          ...state.metrics,
          stageChanges: state.metrics.stageChanges + 1,
        },
        lastCommittedAtMs: action.atMs,
      };
    }

    // ────────────────────────────────────────────────────
    case 'MANUAL_SET_BRIDGE_ANGLE': {
      if (state.stage !== 'BRIDGE' && state.stage !== 'OPENER') return state;
      const angle = action.angle;
      const line = resolveBridgeLine({ bridgeAngle: angle }, playbook);
      return {
        ...state,
        stage: 'BRIDGE',
        bridgeAngle: angle,
        now: makeNow(
          'BRIDGE',
          line,
          'high',
          `Bridge: ${angle} · → after delivering line`,
          'manual',
        ),
        autoClassifySuppressedUntilMs: action.atMs + 4000,
        metrics: {
          ...state.metrics,
          manualOverrideCount: state.metrics.manualOverrideCount + 1,
        },
        lastCommittedAtMs: action.atMs,
      };
    }

    // ────────────────────────────────────────────────────
    case 'MANUAL_SET_OBJECTION': {
      const bucket =
        action.bucket === 'unknown' ? 'interest' : action.bucket;
      return {
        ...state,
        stage: 'OBJECTION',
        lastObjectionBucket: action.bucket,
        activeObjection: bucket,
        objectionHistory: [
          ...state.objectionHistory,
          {
            bucket: action.bucket,
            atMs: action.atMs,
            utterance: action.utterance ?? '',
          },
        ],
        now: makeNow(
          'OBJECTION',
          playbook.objections[bucket].reset,
          'high',
          'Say this, then → try close · F10 give up · 1-4 new objection',
          'manual',
        ),
        autoClassifySuppressedUntilMs: action.atMs + 4000,
        metrics: {
          ...state.metrics,
          manualOverrideCount: state.metrics.manualOverrideCount + 1,
          objectionCount: state.metrics.objectionCount + 1,
        },
        lastCommittedAtMs: action.atMs,
      };
    }

    // ────────────────────────────────────────────────────
    case 'LINE_BANK_SELECT': {
      return {
        ...state,
        now: makeNow(
          state.stage,
          action.line,
          'high',
          'Line bank pick',
          'manual',
        ),
        autoClassifySuppressedUntilMs: action.atMs + 4000,
        metrics: {
          ...state.metrics,
          manualOverrideCount: state.metrics.manualOverrideCount + 1,
        },
        lastCommittedAtMs: action.atMs,
      };
    }

    // ────────────────────────────────────────────────────
    case 'OUTCOME_RECEIVED': {
      if (!action.outcome) return state;
      return {
        ...state,
        outcome: action.outcome,
      };
    }

    // ────────────────────────────────────────────────────
    case 'MARK_DNC': {
      return {
        ...state,
        outcome: 'dnc',
        stage: 'EXIT',
        now: makeNow(
          'EXIT',
          "Understood. I won't reach out again.",
          'high',
          'DNC',
          'manual',
        ),
        lastCommittedAtMs: action.atMs,
      };
    }

    // ────────────────────────────────────────────────────
    case 'END_CALL': {
      return {
        ...state,
        stage: state.stage === 'BOOKED' ? 'BOOKED' : 'ENDED',
        outcome: state.outcome ?? 'ended_unknown',
        ended: true,
        activeObjection: null,
        lastCommittedAtMs: action.atMs,
      };
    }

    // ────────────────────────────────────────────────────
    case 'SET_TONE': {
      return {
        ...state,
        tone: action.tone,
        toneSource: action.toneSource || 'rules',
        toneConfidence: action.toneConfidence || 0.5,
      };
    }

    // ────────────────────────────────────────────────────
    case 'SET_PROSPECT_CONTEXT': {
      return {
        ...state,
        prospectContext: action.prospectContext,
      };
    }

    // ────────────────────────────────────────────────────
    case 'SET_TURN_ANALYSIS': {
      if (action.callSid && state.callId && action.callSid !== state.callId) return state;
      return {
        ...state,
        risk: action.risk ?? state.risk,
        signalCount: action.signalCount ?? state.signalCount,
        recommendedActionBias:
          action.recommendedActionBias !== undefined
            ? action.recommendedActionBias
            : state.recommendedActionBias,
        primaryIntent:
          action.primaryIntent !== undefined ? action.primaryIntent : state.primaryIntent,
        compound: action.compound ?? false,
        nowSummary:
          action.nowSummary !== undefined ? action.nowSummary : state.nowSummary,
        trajectory: action.trajectory ?? state.trajectory,
        _secondaryIntent:
          action.secondaryIntent !== undefined ? action.secondaryIntent : state._secondaryIntent,
      };
    }

    // ────────────────────────────────────────────────────
    case 'PRICING_INTERRUPT': {
      // Ignore if already in PRICING (no nested interrupts)
      if (state.stage === 'PRICING') return state;
      return {
        ...state,
        previousStage: state.previousStage === null ? state.stage : state.previousStage,
        stage: 'PRICING',
        moveType: 'reframe',
        metrics: { ...state.metrics, stageChanges: state.metrics.stageChanges + 1 },
      };
    }

    // ────────────────────────────────────────────────────
    case 'RETURN_FROM_PRICING': {
      const returnStage = state.previousStage || 'QUALIFIER';
      return {
        ...state,
        stage: returnStage,
        previousStage: null,
      };
    }

    // ────────────────────────────────────────────────────
    case 'SET_COMPOUND': {
      return {
        ...state,
        compound: action.compound || false,
        signalCount: action.signalCount || 0,
        recommendedActionBias: action.recommendedActionBias || null,
        activeObjection: action.activeObjection || state.activeObjection,
      };
    }

    default:
      return state;
  }
}
