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
    assert.ok(next.now.line.includes('voicemail on a Monday morning'));
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
    assert.deepEqual(stale, s);
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
    assert.deepEqual(stale, s);
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
    assert.deepEqual(stale, s);
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
