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

      // OPENER → BRIDGE
      if (state.stage === 'OPENER') {
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

      // BRIDGE → QUALIFIER
      if (state.stage === 'BRIDGE') {
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
          return {
            ...nextState,
            stage: 'CLOSE',
            qualifierRead: 'pain',
            now: makeNow('CLOSE', playbook.close, rule.band, 'Pain detected', 'rules'),
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

        // same bucket twice → qualifier
        if (countSame >= 2) {
          return {
            ...nextState,
            stage: 'QUALIFIER',
            objectionHistory: updatedHistory,
            lastObjectionBucket: rule.objectionBucket,
            activeObjection: rule.objectionBucket,
            now: makeNow(
              'QUALIFIER',
              playbook.qualifier,
              rule.band,
              'Same objection bucket twice',
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

        // 3rd objection + no engagement → exit
        if (
          nextState.metrics.objectionCount + 1 >= 3 &&
          !prospectHasEngagement(nextState.transcript)
        ) {
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

      // LLM only refines BRIDGE / QUALIFIER / OBJECTION
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
