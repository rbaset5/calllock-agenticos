// dialer/hud/__tests__/reducer.test.js
// ~18 tests for the HUD reducer.  Run with: node --test

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { PLAYBOOK } from '../playbook.js';
import {
  hudReducer,
  createInitialState,
  shouldSuppressAuto,
} from '../reducer.js';

// ── Helpers ─────────────────────────────────────────────────────

const SID = 'CA-test-001';
const T = 1000; // base timestamp

function init(prospect = null) {
  return hudReducer(createInitialState(PLAYBOOK), {
    type: 'INIT_CALL',
    callId: SID,
    callSid: SID,
    prospect,
    atMs: T,
  }, PLAYBOOK);
}

function connect(state) {
  return hudReducer(state, {
    type: 'CALL_CONNECTED',
    callSid: SID,
    atMs: T + 100,
  }, PLAYBOOK);
}

function makeTurn(text, speaker = 'prospect') {
  return {
    id: `utt-${Math.random().toString(36).slice(2, 8)}`,
    speaker,
    text,
    atMs: T + 200,
    isFinal: true,
  };
}

function transcriptFinal(state, text, rule, atMs) {
  return hudReducer(state, {
    type: 'TRANSCRIPT_FINAL',
    callSid: SID,
    turn: makeTurn(text),
    rule,
    seq: Math.floor((atMs ?? T + 300) / 100),
    atMs: atMs ?? T + 300,
  }, PLAYBOOK);
}

// ── Tests ───────────────────────────────────────────────────────

describe('hudReducer', () => {
  // 1. INIT_CALL → GATEKEEPER
  it('INIT_CALL transitions to GATEKEEPER', () => {
    const s = init();
    assert.equal(s.stage, 'GATEKEEPER');
    assert.equal(s.callId, SID);
    assert.equal(s.now.stage, 'GATEKEEPER');
    assert.ok(s.now.line.includes('Rashid'));
  });

  // 2. CALL_CONNECTED → OPENER
  it('CALL_CONNECTED transitions to OPENER', () => {
    const s = connect(init());
    assert.equal(s.stage, 'OPENER');
    assert.ok(s.now.line.includes('cold call'));
  });

  // 3-6. OPENER → BRIDGE (missed_calls, competition, overwhelmed, fallback)
  it('OPENER → BRIDGE with missed_calls (voicemail variant)', () => {
    const s = connect(init());
    const next = transcriptFinal(s, 'it usually goes to voicemail', {
      band: 'high',
      bridgeAngle: 'missed_calls',
      utterance: 'it usually goes to voicemail',
      why: 'coverage signal',
    });
    assert.equal(next.stage, 'BRIDGE');
    assert.equal(next.bridgeAngle, 'missed_calls');
    assert.ok(next.now.line.includes('competitor'));
  });

  it('OPENER → BRIDGE with competition', () => {
    const s = connect(init());
    const next = transcriptFinal(s, 'we are losing bids to competitors', {
      band: 'high',
      bridgeAngle: 'competition',
      utterance: 'we are losing bids to competitors',
      why: 'competition signal',
    });
    assert.equal(next.stage, 'BRIDGE');
    assert.equal(next.bridgeAngle, 'competition');
    assert.ok(next.now.line.includes('responds first'));
  });

  it('OPENER → BRIDGE with overwhelmed', () => {
    const s = connect(init());
    const next = transcriptFinal(s, 'I do everything myself around here', {
      band: 'high',
      bridgeAngle: 'overwhelmed',
      utterance: 'I do everything myself around here',
      why: 'overwhelmed signal',
    });
    assert.equal(next.stage, 'BRIDGE');
    assert.equal(next.bridgeAngle, 'overwhelmed');
    assert.ok(next.now.line.includes('every call you answer'));
  });

  it('OPENER → BRIDGE with fallback', () => {
    const s = connect(init());
    const next = transcriptFinal(s, 'yeah I dunno', {
      band: 'medium',
      bridgeAngle: 'fallback',
      utterance: 'yeah I dunno',
      why: 'unclear signal',
    });
    assert.equal(next.stage, 'BRIDGE');
    assert.equal(next.bridgeAngle, 'fallback');
    assert.ok(next.now.line.includes('tied up and a new customer calls'));
  });

  // 7. BRIDGE → QUALIFIER
  it('BRIDGE → QUALIFIER on prospect response', () => {
    let s = connect(init());
    s = transcriptFinal(s, 'goes to voicemail a lot', {
      band: 'high',
      bridgeAngle: 'missed_calls',
      utterance: 'goes to voicemail a lot',
      why: 'coverage',
    });
    assert.equal(s.stage, 'BRIDGE');
    // Now the prospect responds to the bridge line
    s = transcriptFinal(s, 'yeah that makes sense', {
      band: 'medium',
      why: 'acknowledgment',
    });
    assert.equal(s.stage, 'QUALIFIER');
    assert.ok(s.now.line.includes('How many calls'));
  });

  // 8. QUALIFIER → CLOSE (pain)
  it('QUALIFIER → CLOSE on pain detected', () => {
    let s = connect(init());
    // Fast-forward to QUALIFIER via manual override
    s = hudReducer(s, {
      type: 'MANUAL_SET_STAGE',
      callSid: SID,
      stage: 'QUALIFIER',
      atMs: T + 100,
    }, PLAYBOOK);

    s = transcriptFinal(s, 'more than I would like honestly', {
      band: 'high',
      qualifierRead: 'pain',
      utterance: 'more than I would like honestly',
      why: 'pain keyword',
    }, T + 5000); // past suppression window
    assert.equal(s.stage, 'CLOSE');
    assert.equal(s.qualifierRead, 'pain');
    assert.ok(s.now.line.includes('Worth 15 minutes'));
  });

  // 9. QUALIFIER → SEED_EXIT (no_pain)
  it('QUALIFIER → SEED_EXIT on no pain', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'MANUAL_SET_STAGE',
      callSid: SID,
      stage: 'QUALIFIER',
      atMs: T + 100,
    }, PLAYBOOK);

    s = transcriptFinal(s, 'not many we are pretty covered', {
      band: 'high',
      qualifierRead: 'no_pain',
      utterance: 'not many we are pretty covered',
      why: 'low pain',
    }, T + 5000);
    assert.equal(s.stage, 'SEED_EXIT');
    assert.equal(s.qualifierRead, 'no_pain');
    assert.ok(s.now.line.includes('ever changes'));
  });

  // 10. QUALIFIER → CLOSE (unknown_pain)
  it('QUALIFIER → CLOSE on unknown pain', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'MANUAL_SET_STAGE',
      callSid: SID,
      stage: 'QUALIFIER',
      atMs: T + 100,
    }, PLAYBOOK);

    s = transcriptFinal(s, 'eh I am not sure really', {
      band: 'medium',
      qualifierRead: 'unknown_pain',
      utterance: 'eh I am not sure really',
      why: 'unmeasured pain',
    }, T + 5000);
    assert.equal(s.stage, 'CLOSE');
    assert.equal(s.qualifierRead, 'unknown_pain');
    assert.ok(s.now.line.includes('problem hides'));
  });

  // 11. CLOSE → OBJECTION (all 4 buckets)
  it('CLOSE → OBJECTION for each bucket', () => {
    const buckets = ['timing', 'interest', 'info', 'authority'];
    for (const bucket of buckets) {
      let s = connect(init());
      s = hudReducer(s, {
        type: 'MANUAL_SET_STAGE',
        callSid: SID,
        stage: 'CLOSE',
        atMs: T + 100,
      }, PLAYBOOK);

      s = transcriptFinal(s, `test ${bucket}`, {
        band: 'high',
        objectionBucket: bucket,
        utterance: `test ${bucket}`,
        why: `${bucket} objection`,
      }, T + 5000);

      assert.equal(s.stage, 'OBJECTION', `Expected OBJECTION for ${bucket}`);
      assert.equal(s.lastObjectionBucket, bucket);
      assert.ok(
        s.now.line === PLAYBOOK.objections[bucket].reset,
        `Expected reset line for ${bucket}`,
      );
    }
  });

  // 12. OBJECTION same-bucket-twice → QUALIFIER
  it('same objection bucket twice routes to QUALIFIER via LLM_RESULT', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'MANUAL_SET_STAGE',
      callSid: SID,
      stage: 'OBJECTION',
      atMs: T + 100,
    }, PLAYBOOK);

    // Seed two timing objections in history
    s = {
      ...s,
      objectionHistory: [
        { bucket: 'timing', atMs: T + 50, utterance: 'busy' },
        { bucket: 'timing', atMs: T + 80, utterance: 'busy again' },
      ],
      metrics: { ...s.metrics, objectionCount: 2 },
    };

    s = hudReducer(s, {
      type: 'LLM_RESULT',
      callSid: SID,
      result: {
        band: 'medium',
        objectionBucket: 'timing',
        utterance: 'still busy',
        why: 'same bucket',
      },
      utteranceId: 10,
      atMs: T + 5000,
    }, PLAYBOOK);

    assert.equal(s.stage, 'QUALIFIER');
    assert.ok(s.now.line.includes('How many calls'));
  });

  // 13. OBJECTION 3rd + no engagement → EXIT
  it('3rd objection with no engagement routes to EXIT', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'MANUAL_SET_STAGE',
      callSid: SID,
      stage: 'OBJECTION',
      atMs: T + 100,
    }, PLAYBOOK);

    // Set up: 3 objections already counted, no prospect questions
    s = {
      ...s,
      objectionHistory: [
        { bucket: 'timing', atMs: T + 50, utterance: 'busy' },
        { bucket: 'interest', atMs: T + 60, utterance: 'not interested' },
        { bucket: 'info', atMs: T + 70, utterance: 'email me' },
      ],
      transcript: [
        { id: 'u1', speaker: 'prospect', text: 'no', atMs: T + 50, isFinal: true },
        { id: 'u2', speaker: 'prospect', text: 'nope', atMs: T + 60, isFinal: true },
      ],
      metrics: { ...s.metrics, objectionCount: 3 },
    };

    s = hudReducer(s, {
      type: 'LLM_RESULT',
      callSid: SID,
      result: {
        band: 'medium',
        objectionBucket: 'authority',
        utterance: 'not my call',
        why: 'authority',
      },
      utteranceId: 10,
      atMs: T + 5000,
    }, PLAYBOOK);

    assert.equal(s.stage, 'EXIT');
    assert.equal(s.outcome, 'not_booked');
  });

  // 14. MANUAL_SET_STAGE + suppression window
  it('MANUAL_SET_STAGE sets stage and suppresses auto-classify', () => {
    const s = connect(init());
    const overridden = hudReducer(s, {
      type: 'MANUAL_SET_STAGE',
      callSid: SID,
      stage: 'CLOSE',
      atMs: T + 500,
    }, PLAYBOOK);

    assert.equal(overridden.stage, 'CLOSE');
    assert.equal(overridden.now.classificationSource, 'manual');
    assert.ok(shouldSuppressAuto(overridden, T + 500 + 3000));
    assert.ok(!shouldSuppressAuto(overridden, T + 500 + 5000));
  });

  // 15. MANUAL_SET_OBJECTION
  it('MANUAL_SET_OBJECTION sets objection bucket and shows reset', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'MANUAL_SET_OBJECTION',
      callSid: SID,
      bucket: 'info',
      utterance: 'just email me',
      atMs: T + 600,
    }, PLAYBOOK);

    assert.equal(s.stage, 'OBJECTION');
    assert.equal(s.lastObjectionBucket, 'info');
    assert.ok(s.now.line.includes("What's your email"));
    assert.equal(s.metrics.objectionCount, 1);
  });

  // 16. NO_ANSWER → NON_CONNECT
  it('NO_ANSWER transitions to NON_CONNECT', () => {
    const s = init();
    const next = hudReducer(s, {
      type: 'NO_ANSWER',
      callSid: SID,
      atMs: T + 200,
    }, PLAYBOOK);
    assert.equal(next.stage, 'NON_CONNECT');
    assert.equal(next.outcome, 'non_connect');
    assert.ok(next.now.line.includes('Rashid calling from Houston'));
  });

  // 17. HEDGE_REQUESTED only in CLOSE
  it('HEDGE_REQUESTED works in CLOSE but is ignored elsewhere', () => {
    let s = connect(init());
    // Try hedge in OPENER — should be no-op
    const hedgedOpener = hudReducer(s, {
      type: 'HEDGE_REQUESTED',
      callSid: SID,
      atMs: T + 300,
    }, PLAYBOOK);
    assert.equal(hedgedOpener.stage, 'OPENER');

    // Now set stage to CLOSE
    s = hudReducer(s, {
      type: 'MANUAL_SET_STAGE',
      callSid: SID,
      stage: 'CLOSE',
      atMs: T + 400,
    }, PLAYBOOK);

    const hedgedClose = hudReducer(s, {
      type: 'HEDGE_REQUESTED',
      callSid: SID,
      atMs: T + 5000,
    }, PLAYBOOK);
    assert.equal(hedgedClose.stage, 'CLOSE');
    assert.ok(hedgedClose.now.line.includes('Thursday at 2'));
  });

  // 18. BOOKING_CONFIRMED → BOOKED
  it('BOOKING_CONFIRMED transitions to BOOKED', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'MANUAL_SET_STAGE',
      callSid: SID,
      stage: 'CLOSE',
      atMs: T + 100,
    }, PLAYBOOK);

    s = hudReducer(s, {
      type: 'BOOKING_CONFIRMED',
      callSid: SID,
      email: 'test@hvac.com',
      day: 'Thursday',
      atMs: T + 5000,
    }, PLAYBOOK);

    assert.equal(s.stage, 'BOOKED');
    assert.equal(s.outcome, 'booked');
    assert.equal(s.collectedEmail, 'test@hvac.com');
    assert.ok(s.now.line.includes('invite heading your way'));
  });

  // 19. END_CALL
  it('END_CALL marks call as ended', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'END_CALL',
      callSid: SID,
      atMs: T + 9000,
    }, PLAYBOOK);

    assert.equal(s.ended, true);
    assert.equal(s.stage, 'ENDED');
    assert.equal(s.outcome, 'ended_unknown');
  });

  // 20. END_CALL preserves BOOKED stage
  it('END_CALL preserves BOOKED stage', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'BOOKING_CONFIRMED',
      callSid: SID,
      atMs: T + 5000,
    }, PLAYBOOK);

    s = hudReducer(s, {
      type: 'END_CALL',
      callSid: SID,
      atMs: T + 9000,
    }, PLAYBOOK);

    assert.equal(s.stage, 'BOOKED');
    assert.equal(s.outcome, 'booked');
    assert.equal(s.ended, true);
  });

  // 20b. END_CALL clears activeObjection
  it('END_CALL clears activeObjection', () => {
    let s = connect(init());
    // Manually set activeObjection as if we entered OBJECTION stage
    s = { ...s, stage: 'OBJECTION', activeObjection: 'timing', lastObjectionBucket: 'timing' };
    s = hudReducer(s, {
      type: 'END_CALL',
      callSid: SID,
      atMs: T + 9000,
    }, PLAYBOOK);

    assert.equal(s.ended, true);
    assert.equal(s.activeObjection, null);
  });

  // 21. Stale callSid rejection
  it('rejects actions with wrong callSid', () => {
    const s = connect(init());
    const stale = hudReducer(s, {
      type: 'CALL_CONNECTED',
      callSid: 'CA-wrong-id',
      atMs: T + 500,
    }, PLAYBOOK);

    // State should be unchanged
    assert.equal(stale.stage, s.stage);
    assert.equal(stale.callId, s.callId);
  });

  // 22. Stale sequence rejection on LLM_RESULT
  it('rejects LLM_RESULT with stale sequence', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'MANUAL_SET_STAGE',
      callSid: SID,
      stage: 'BRIDGE',
      atMs: T + 100,
    }, PLAYBOOK);

    // Process an LLM result with seq=5
    s = hudReducer(s, {
      type: 'LLM_RESULT',
      callSid: SID,
      result: {
        band: 'high',
        bridgeAngle: 'missed_calls',
        utterance: 'voicemail',
        why: 'coverage',
      },
      utteranceId: 'utt-5',
      seq: 5,
      atMs: T + 5000,
    }, PLAYBOOK);
    assert.equal(s.lastProcessedUtteranceSeq, 5);

    // Now send a stale result with seq=3 — should be rejected
    const stale = hudReducer(s, {
      type: 'LLM_RESULT',
      callSid: SID,
      result: {
        band: 'high',
        bridgeAngle: 'competition',
        utterance: 'losing bids',
        why: 'competition',
      },
      utteranceId: 'utt-3',
      seq: 3,
      atMs: T + 5500,
    }, PLAYBOOK);

    assert.equal(stale.bridgeAngle, 'missed_calls'); // unchanged
    assert.equal(stale.lastProcessedUtteranceSeq, s.lastProcessedUtteranceSeq);
  });

  it('rejects an older LLM result once a newer transcript has arrived', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'MANUAL_SET_STAGE',
      callSid: SID,
      stage: 'QUALIFIER',
      atMs: T + 100,
    }, PLAYBOOK);

    s = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL',
      callSid: SID,
      turn: makeTurn('depends on the week'),
      rule: { band: 'low', qualifierRead: 'unknown_pain', why: 'ambiguous' },
      seq: 5,
      atMs: T + 5000,
    }, PLAYBOOK);

    s = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL',
      callSid: SID,
      turn: makeTurn('probably 5 or 6'),
      rule: { band: 'high', qualifierRead: 'pain', why: 'number' },
      seq: 6,
      atMs: T + 5200,
    }, PLAYBOOK);

    const stale = hudReducer(s, {
      type: 'LLM_RESULT',
      callSid: SID,
      result: {
        band: 'medium',
        qualifierRead: 'unknown_pain',
        utterance: 'depends on the week',
        why: 'late llm',
      },
      utteranceId: 'utt-5',
      seq: 5,
      atMs: T + 5400,
    }, PLAYBOOK);

    assert.equal(stale.stage, 'CLOSE');
    assert.equal(stale.qualifierRead, 'pain');
    assert.equal(stale.lastProcessedUtteranceSeq, s.lastProcessedUtteranceSeq);
  });

  it('LINE_BANK_SELECT keeps the stage but swaps the line', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'MANUAL_SET_STAGE',
      callSid: SID,
      stage: 'BRIDGE',
      atMs: T + 100,
    }, PLAYBOOK);

    const next = hudReducer(s, {
      type: 'LINE_BANK_SELECT',
      callSid: SID,
      line: 'Custom bridge line',
      atMs: T + 200,
    }, PLAYBOOK);

    assert.equal(next.stage, 'BRIDGE');
    assert.equal(next.now.line, 'Custom bridge line');
    assert.equal(next.now.classificationSource, 'manual');
    assert.equal(next.metrics.manualOverrideCount, s.metrics.manualOverrideCount + 1);
    assert.ok(next.autoClassifySuppressedUntilMs > T + 200);
  });
});

// ── v2 reducer actions ──────────────────────────────────────────

describe('v2 reducer actions', () => {
  it('AUTO_SET_STAGE transitions without enabling manual suppression', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'AUTO_SET_STAGE',
      callSid: SID,
      stage: 'WRONG_PERSON',
      atMs: T + 150,
      why: 'Authority mismatch detected',
    }, PLAYBOOK);

    assert.equal(s.stage, 'WRONG_PERSON');
    assert.equal(shouldSuppressAuto(s, T + 500), false);
  });

  it('AUTO_SET_STAGE allows the next transcript to classify immediately', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'AUTO_SET_STAGE',
      callSid: SID,
      stage: 'WRONG_PERSON',
      atMs: T + 150,
      why: 'Authority mismatch detected',
    }, PLAYBOOK);

    s = transcriptFinal(s, 'yeah we miss calls', {
      band: 'high',
      bridgeAngle: 'missed_calls',
      utterance: 'yeah we miss calls',
      why: 'pain signal after transfer',
    }, T + 400);

    assert.equal(s.stage, 'OPENER');
  });

  it('SET_TONE updates tone fields', () => {
    const s = createInitialState(PLAYBOOK);
    s.callId = 'test-1';
    const next = hudReducer(s, { type: 'SET_TONE', callSid: 'test-1', tone: 'rushed', toneSource: 'rules', toneConfidence: 0.7 }, PLAYBOOK);
    assert.equal(next.tone, 'rushed');
    assert.equal(next.toneSource, 'rules');
    assert.equal(next.toneConfidence, 0.7);
  });

  it('SET_PROSPECT_CONTEXT populates context', () => {
    const s = createInitialState(PLAYBOOK);
    s.callId = 'test-1';
    const ctx = { name: 'John', company: 'Smith Plumbing' };
    const next = hudReducer(s, { type: 'SET_PROSPECT_CONTEXT', callSid: 'test-1', prospectContext: ctx }, PLAYBOOK);
    assert.deepEqual(next.prospectContext, ctx);
  });

  it('PRICING_INTERRUPT saves previousStage and enters PRICING', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'QUALIFIER' };
    const next = hudReducer(s, { type: 'PRICING_INTERRUPT', callSid: 'test-1' }, PLAYBOOK);
    assert.equal(next.stage, 'PRICING');
    assert.equal(next.previousStage, 'QUALIFIER');
  });

  it('PRICING_INTERRUPT no-ops if already in PRICING', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'PRICING', previousStage: 'BRIDGE' };
    const next = hudReducer(s, { type: 'PRICING_INTERRUPT', callSid: 'test-1' }, PLAYBOOK);
    assert.equal(next.stage, 'PRICING');
    assert.equal(next.previousStage, 'BRIDGE');
  });

  it('PRICING_INTERRUPT does not overwrite existing previousStage', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'OBJECTION', previousStage: 'BRIDGE' };
    const next = hudReducer(s, { type: 'PRICING_INTERRUPT', callSid: 'test-1' }, PLAYBOOK);
    assert.equal(next.stage, 'PRICING');
    assert.equal(next.previousStage, 'BRIDGE');
  });

  it('RETURN_FROM_PRICING restores previousStage and clears it', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'PRICING', previousStage: 'QUALIFIER' };
    const next = hudReducer(s, { type: 'RETURN_FROM_PRICING', callSid: 'test-1' }, PLAYBOOK);
    assert.equal(next.stage, 'QUALIFIER');
    assert.equal(next.previousStage, null);
  });

  it('RETURN_FROM_PRICING falls back to QUALIFIER if no previousStage', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'PRICING', previousStage: null };
    const next = hudReducer(s, { type: 'RETURN_FROM_PRICING', callSid: 'test-1' }, PLAYBOOK);
    assert.equal(next.stage, 'QUALIFIER');
  });

  it('MANUAL_SET_STAGE clears previousStage', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'PRICING', previousStage: 'BRIDGE' };
    const next = hudReducer(s, { type: 'MANUAL_SET_STAGE', callSid: 'test-1', stage: 'CLOSE', atMs: 1000 }, PLAYBOOK);
    assert.equal(next.stage, 'CLOSE');
    assert.equal(next.previousStage, null);
  });

  it('SET_COMPOUND updates compound fields', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1' };
    const next = hudReducer(s, {
      type: 'SET_COMPOUND', callSid: 'test-1',
      compound: true, signalCount: 2,
      recommendedActionBias: 'compress',
      activeObjection: 'timing',
    }, PLAYBOOK);
    assert.equal(next.compound, true);
    assert.equal(next.signalCount, 2);
    assert.equal(next.recommendedActionBias, 'compress');
    assert.equal(next.activeObjection, 'timing');
  });

  it('SET_COMPOUND with no compound resets fields', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', compound: true, signalCount: 2 };
    const next = hudReducer(s, {
      type: 'SET_COMPOUND', callSid: 'test-1',
      compound: false, signalCount: 0,
    }, PLAYBOOK);
    assert.equal(next.compound, false);
    assert.equal(next.signalCount, 0);
  });

  it('activeObjection is set when objection detected via TRANSCRIPT_FINAL', () => {
    let s = connect(init());
    s = hudReducer(s, {
      type: 'MANUAL_SET_STAGE',
      callSid: SID,
      stage: 'CLOSE',
      atMs: T + 100,
    }, PLAYBOOK);

    s = transcriptFinal(s, 'not right now', {
      band: 'high',
      objectionBucket: 'timing',
      utterance: 'not right now',
      why: 'timing objection',
    }, T + 5000);

    assert.equal(s.stage, 'OBJECTION');
    assert.equal(s.activeObjection, 'timing');
  });

  it('createInitialState has v2 fields', () => {
    const s = createInitialState(PLAYBOOK);
    assert.equal(s.tone, 'neutral');
    assert.equal(s.risk, 'low');
    assert.equal(s.compound, false);
    assert.equal(s.previousStage, null);
    assert.equal(s.moveType, 'pause');
    assert.ok(s.trajectory);
    assert.equal(s.trajectory.salvageAttemptCount, 0);
  });
});

// ── Stress test fix regressions ─────────────────────────────
describe('stress test fixes', () => {
  it('MINI_PITCH + TRANSCRIPT_FINAL advances to BRIDGE', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'MINI_PITCH' };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: 'Ok tell me more', atMs: Date.now() },
      rule: { band: 'medium', confidence: 0.65, why: 'engaged' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'BRIDGE');
  });

  it('PRICING + TRANSCRIPT_FINAL returns to previousStage', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'PRICING', previousStage: 'QUALIFIER' };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: 'Yeah we do miss some calls', atMs: Date.now() },
      rule: { band: 'medium', confidence: 0.65, why: 'engaged' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'QUALIFIER');
    assert.equal(next.previousStage, null);
  });

  it('OPENER + "not interested" routes to OBJECTION not BRIDGE', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'OPENER' };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: 'Not interested', atMs: Date.now() },
      rule: { band: 'high', confidence: 0.8, why: 'objection', objectionBucket: 'interest' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'OBJECTION');
    assert.equal(next.lastObjectionBucket, 'interest');
  });
});

// ── QA simulation fixes: LLM fallthrough side-stage exits ──────

describe('LLM_RESULT side-stage exits (QA fix 2026-04-03)', () => {
  it('MINI_PITCH + LLM_RESULT → advances to BRIDGE', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'MINI_PITCH', latestTranscriptSeq: 0, lastProcessedUtteranceSeq: 0 };
    const next = hudReducer(s, {
      type: 'LLM_RESULT', callSid: 'test-1', seq: 1,
      result: { band: 'medium', confidence: 0.55, why: 'rules fallthrough', utterance: 'yeah we miss calls' },
      atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'BRIDGE');
  });

  it('WRONG_PERSON + LLM_RESULT → advances to OPENER', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'WRONG_PERSON', latestTranscriptSeq: 0, lastProcessedUtteranceSeq: 0 };
    const next = hudReducer(s, {
      type: 'LLM_RESULT', callSid: 'test-1', seq: 1,
      result: { band: 'medium', confidence: 0.55, why: 'rules fallthrough', utterance: 'this is Jim' },
      atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'OPENER');
  });

  it('PRICING + LLM_RESULT → returns to previousStage (QUALIFIER)', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'PRICING', previousStage: 'QUALIFIER', latestTranscriptSeq: 0, lastProcessedUtteranceSeq: 0 };
    const next = hudReducer(s, {
      type: 'LLM_RESULT', callSid: 'test-1', seq: 1,
      result: { band: 'medium', confidence: 0.55, why: 'rules fallthrough', utterance: 'we miss calls on weekends' },
      atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'QUALIFIER');
    assert.equal(next.previousStage, null);
  });

  it('CONFUSION + LLM_RESULT → advances to BRIDGE', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'CONFUSION', latestTranscriptSeq: 0, lastProcessedUtteranceSeq: 0 };
    const next = hudReducer(s, {
      type: 'LLM_RESULT', callSid: 'test-1', seq: 1,
      result: { band: 'medium', confidence: 0.55, why: 'rules fallthrough', utterance: 'oh ok that makes sense' },
      atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'BRIDGE');
  });
});

describe('WRONG_PERSON rules exit via TRANSCRIPT_FINAL', () => {
  it('WRONG_PERSON + any usable TRANSCRIPT_FINAL → OPENER', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'WRONG_PERSON' };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: 'Oh this is Jim, what do you need?', atMs: Date.now() },
      rule: { band: 'medium', confidence: 0.55, why: 'rules fallthrough' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'OPENER');
  });
});

// ── Gap fixes: OBJECTION exit, CLOSE→BOOKED, LLM_RESULT OBJECTION ──

describe('Gap 1: OBJECTION engaged exit via TRANSCRIPT_FINAL', () => {
  it('OBJECTION + bridge angle (no objectionBucket) → BRIDGE', () => {
    const s = {
      ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'OBJECTION',
      lastObjectionBucket: 'interest', objectionHistory: [{ bucket: 'interest', atMs: 1000 }],
      metrics: { ...createInitialState(PLAYBOOK).metrics, objectionCount: 1 },
    };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: 'Well yeah after hours goes to voicemail', atMs: Date.now() },
      rule: { band: 'high', confidence: 0.78, why: 'bridge angle', bridgeAngle: 'missed_calls' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'BRIDGE');
  });
});

describe('Gap 1b: OBJECTION engaged exit via LLM_RESULT', () => {
  it('OBJECTION + LLM_RESULT without objectionBucket → BRIDGE', () => {
    const s = {
      ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'OBJECTION',
      lastObjectionBucket: 'interest', latestTranscriptSeq: 0, lastProcessedUtteranceSeq: 0,
      objectionHistory: [{ bucket: 'interest', atMs: 1000 }],
    };
    const next = hudReducer(s, {
      type: 'LLM_RESULT', callSid: 'test-1', seq: 1,
      result: { band: 'medium', confidence: 0.55, why: 'rules fallthrough', bridgeAngle: 'missed_calls', utterance: 'yeah voicemail' },
      atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'BRIDGE');
  });
});

describe('Round 2: Cross-stage booking', () => {
  it('CLOSE + yes intent → BOOKED', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'CLOSE', qualifierRead: 'pain' };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: 'Thursday works for me', atMs: Date.now() },
      rule: { band: 'high', confidence: 0.75, why: 'yes intent detected', detectedIntent: 'yes' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'BOOKED');
    assert.equal(next.outcome, 'booked');
  });

  it('QUALIFIER + yes intent → BOOKED (cross-stage)', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'QUALIFIER' };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: 'Friday at 2 would work', atMs: Date.now() },
      rule: { band: 'high', confidence: 0.75, why: 'yes intent detected', detectedIntent: 'yes' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'BOOKED');
    assert.equal(next.outcome, 'booked');
  });

  it('BRIDGE + yes intent → BOOKED (cross-stage)', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'BRIDGE', bridgeAngle: 'missed_calls' };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: 'Thursday morning works', atMs: Date.now() },
      rule: { band: 'high', confidence: 0.75, why: 'yes intent detected', detectedIntent: 'yes' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'BOOKED');
    assert.equal(next.outcome, 'booked');
  });

  it('OPENER + yes intent does NOT → BOOKED (too early)', () => {
    const s = { ...connect(init()) };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: SID,
      turn: { speaker: 'prospect', text: 'Sure yeah', atMs: Date.now() },
      rule: { band: 'medium', confidence: 0.65, why: 'yes', detectedIntent: 'yes' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.notEqual(next.stage, 'BOOKED');
  });
});

describe('Round 2: Same-bucket objection x2 → EXIT', () => {
  it('interest objection x2 → EXIT (not QUALIFIER)', () => {
    const s = {
      ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'OBJECTION',
      objectionHistory: [{ bucket: 'interest', atMs: 1000, utterance: 'not interested' }],
      lastObjectionBucket: 'interest', activeObjection: 'interest',
      metrics: { ...createInitialState(PLAYBOOK).metrics, objectionCount: 1 },
    };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: 'Still not interested', atMs: Date.now() },
      rule: { band: 'high', confidence: 0.8, why: 'interest objection', objectionBucket: 'interest' },
      seq: 2, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'EXIT');
  });

  it('3 different buckets → stays OBJECTION (not EXIT)', () => {
    const s = {
      ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'OBJECTION',
      objectionHistory: [
        { bucket: 'interest', atMs: 1000, utterance: 'not interested' },
        { bucket: 'timing', atMs: 2000, utterance: 'too busy' },
      ],
      lastObjectionBucket: 'timing', activeObjection: 'timing',
      metrics: { ...createInitialState(PLAYBOOK).metrics, objectionCount: 2 },
    };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: 'Just email me', atMs: Date.now() },
      rule: { band: 'high', confidence: 0.8, why: 'info objection', objectionBucket: 'info' },
      seq: 3, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'OBJECTION');
  });
});

describe('Round 2: WRONG_PERSON → EXIT on brush_off', () => {
  it('gatekeeper "goodbye" → EXIT from WRONG_PERSON', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'WRONG_PERSON' };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: 'Not taking a message, goodbye', atMs: Date.now() },
      rule: { band: 'high', confidence: 0.8, why: 'brush off detected', detectedIntent: 'brush_off' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'EXIT');
  });
});

describe('Round 2: MINI_PITCH preserves bridge angle on pain', () => {
  it('MINI_PITCH + pain with bridgeAngle → BRIDGE with angle', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'MINI_PITCH' };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: 'We miss calls all the time', atMs: Date.now() },
      rule: { band: 'high', confidence: 0.8, why: 'missed calls', bridgeAngle: 'missed_calls' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'BRIDGE');
    assert.equal(next.bridgeAngle, 'missed_calls');
  });
});

// ── Cross-model review fixes ───────────────────────────────────────

describe('Cross-model: BRIDGE → OBJECTION on objection signal', () => {
  it('BRIDGE + objection bucket → OBJECTION (not QUALIFIER)', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'BRIDGE', bridgeAngle: 'missed_calls' };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: "Actually I don't think we need it", atMs: Date.now() },
      rule: { band: 'medium', confidence: 0.7, why: 'interest objection in bridge', objectionBucket: 'interest' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'OBJECTION');
    assert.equal(next.lastObjectionBucket, 'interest');
  });

  it('BRIDGE + no objection bucket → QUALIFIER (normal advance)', () => {
    const s = { ...createInitialState(PLAYBOOK), callId: 'test-1', stage: 'BRIDGE', bridgeAngle: 'missed_calls' };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: 'test-1',
      turn: { speaker: 'prospect', text: 'Yeah we miss calls on weekends', atMs: Date.now() },
      rule: { band: 'medium', confidence: 0.7, why: 'engaged', bridgeAngle: 'missed_calls' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'QUALIFIER');
  });
});

describe('Cross-model: OPENER → EXIT on brush_off', () => {
  it('OPENER + brush_off → EXIT directly (no transient BRIDGE)', () => {
    const s = { ...connect(init()) };
    const next = hudReducer(s, {
      type: 'TRANSCRIPT_FINAL', callSid: SID,
      turn: { speaker: 'prospect', text: 'Take me off your calling list', atMs: Date.now() },
      rule: { band: 'high', confidence: 0.8, why: 'DNC detected', detectedIntent: 'brush_off' },
      seq: 1, atMs: Date.now(),
    }, PLAYBOOK);
    assert.equal(next.stage, 'EXIT');
    assert.equal(next.outcome, 'not_booked');
  });
});
