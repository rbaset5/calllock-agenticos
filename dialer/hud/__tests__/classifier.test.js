// dialer/hud/__tests__/classifier.test.js
// Uses Node.js built-in test runner: node --test

import { describe, it, test } from "node:test";
import assert from "node:assert/strict";

import {
  classifyUtterance,
  detectNewIntents,
  shouldCallLlmFallback,
  isUsableDeterministicResult,
} from "../classifier.js";

// -------------------------
// Bridge classification
// -------------------------

describe("classifyBridge", () => {
  it('"goes to voicemail" -> missed_calls, high confidence', () => {
    const r = classifyUtterance("It usually just goes to voicemail", { stage: "OPENER" });
    assert.equal(r.bridgeAngle, "missed_calls");
    assert.equal(r.band, "high");
    assert.ok(isUsableDeterministicResult(r));
    assert.ok(!shouldCallLlmFallback(r));
  });

  it('"it\'s just me, I do everything" -> overwhelmed', () => {
    const r = classifyUtterance("it's just me, I do everything", { stage: "OPENER" });
    assert.equal(r.bridgeAngle, "overwhelmed");
    assert.ok(r.band === "high" || r.band === "medium");
    assert.ok(isUsableDeterministicResult(r));
  });

  it('"we\'re trying to grow" -> competition', () => {
    const r = classifyUtterance("we're trying to grow the business", { stage: "OPENER" });
    assert.equal(r.bridgeAngle, "competition");
    assert.ok(r.band === "high" || r.band === "medium");
    assert.ok(isUsableDeterministicResult(r));
  });

  it('"it is rushed during bids" -> fallback (mixed signals, margin < 1.25)', () => {
    // overwhelmed: token "rushed" = 1.25 (no phrase match, no nudge)
    // competition: token "bids" = 1.25 (no phrase match, no nudge)
    // margin = 0, well under 1.25 -> fallback
    const r = classifyUtterance("it is rushed during bids", { stage: "OPENER" });
    assert.equal(r.bridgeAngle, "fallback");
    assert.ok(shouldCallLlmFallback(r));
  });

  it("empty/short answer -> fallback, low confidence", () => {
    const r = classifyUtterance("", { stage: "OPENER" });
    assert.equal(r.band, "low");
    assert.ok(shouldCallLlmFallback(r));
  });
});

// -------------------------
// Qualifier classification
// -------------------------

describe("classifyQualifier", () => {
  it('"more than I\'d like" -> pain', () => {
    const r = classifyUtterance("more than I'd like honestly", { stage: "QUALIFIER" });
    assert.equal(r.qualifierRead, "pain");
    assert.ok(isUsableDeterministicResult(r));
  });

  it('"a few" -> no_pain', () => {
    const r = classifyUtterance("a few maybe", { stage: "QUALIFIER" });
    assert.equal(r.qualifierRead, "no_pain");
    assert.ok(isUsableDeterministicResult(r));
  });

  it('"depends" or "don\'t know" -> unknown_pain', () => {
    const r1 = classifyUtterance("depends on the week really", { stage: "QUALIFIER" });
    assert.equal(r1.qualifierRead, "unknown_pain");

    const r2 = classifyUtterance("don't know, haven't tracked it", { stage: "QUALIFIER" });
    assert.equal(r2.qualifierRead, "unknown_pain");
  });

  it('"probably 5 or 6" -> pain (number detection)', () => {
    const r = classifyUtterance("probably 5 or 6 a week", { stage: "QUALIFIER" });
    assert.equal(r.qualifierRead, "pain");
    assert.ok(isUsableDeterministicResult(r));
  });
});

// -------------------------
// Objection classification
// -------------------------

describe("classifyObjectionOrClose", () => {
  it('"not interested" -> interest bucket', () => {
    const r = classifyUtterance("not interested", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "interest");
    assert.ok(isUsableDeterministicResult(r));
  });

  it('"email me" -> info bucket', () => {
    const r = classifyUtterance("just email me something", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "info");
    assert.ok(isUsableDeterministicResult(r));
  });

  it('"I\'m busy, just send me something" -> info (priority: info > timing)', () => {
    const r = classifyUtterance("I'm busy, just send me something", { stage: "OBJECTION" });
    assert.equal(r.objectionBucket, "info");
  });
});

// -------------------------
// Gatekeeper classification
// -------------------------

describe("classifyGatekeeper", () => {
  it('"what\'s this about" -> gatekeeper stage suggestion', () => {
    const r = classifyUtterance("what's this about?", { stage: "GATEKEEPER" });
    assert.equal(r.stageSuggestion, "GATEKEEPER");
    assert.equal(r.band, "high");
    assert.ok(r.why.includes("what the call is about"));
  });
});

// -------------------------
// Edge cases
// -------------------------

describe("edge cases", () => {
  it("empty utterance -> low confidence", () => {
    const r = classifyUtterance("", { stage: "BRIDGE" });
    assert.equal(r.band, "low");
    assert.ok(shouldCallLlmFallback(r));
    assert.ok(!isUsableDeterministicResult(r));
  });
});

// -------------------------
// detectNewIntents
// -------------------------

describe('detectNewIntents', () => {
  test('detects confusion for "what is this about" in OPENER', () => {
    const result = detectNewIntents('what is this about', 'OPENER');
    assert.equal(result.intent, 'confusion');
    assert.ok(result.confidence >= 0.65);
  });

  test('detects pricing_question for "how much is it" in QUALIFIER', () => {
    const result = detectNewIntents('how much is it', 'QUALIFIER');
    assert.equal(result.intent, 'pricing_question');
  });

  test('detects authority_mismatch for "talk to my wife"', () => {
    const result = detectNewIntents('you need to talk to my wife she handles that', 'OPENER');
    assert.equal(result.intent, 'authority_mismatch');
  });

  test('detects pricing_resistance for "too expensive"', () => {
    const result = detectNewIntents('that sounds too expensive', 'CLOSE');
    assert.equal(result.intent, 'pricing_resistance');
  });

  test('returns null when no new intents match', () => {
    const result = detectNewIntents('yeah we get some calls', 'BRIDGE');
    assert.equal(result, null);
  });

  test('stage-aware: confusion higher confidence in OPENER than QUALIFIER', () => {
    const openerResult = detectNewIntents('what is this about', 'OPENER');
    const qualResult = detectNewIntents('what is this about', 'QUALIFIER');
    assert.ok(openerResult.confidence > qualResult.confidence);
  });
});

describe('classifyUtterance integration with new intents', () => {
  test('"what is this about" in OPENER routes through classifyUtterance', () => {
    const result = classifyUtterance('what is this about', { stage: 'OPENER' });
    assert.ok(result.confidence >= 0.6);
  });
});

describe('stress test fixes', () => {
  test('detects "talk to my husband" as authority_mismatch', () => {
    const result = detectNewIntents('you need to talk to my husband he handles that', 'OPENER');
    assert.equal(result.intent, 'authority_mismatch');
  });

  test('detects "he handles that" as authority_mismatch', () => {
    const result = detectNewIntents('he handles that not me', 'OPENER');
    assert.equal(result.intent, 'authority_mismatch');
  });

  test('detects curiosity in OPENER', () => {
    const result = detectNewIntents('how does that work exactly', 'OPENER');
    assert.equal(result.intent, 'curiosity');
    assert.ok(result.confidence >= 0.65);
  });

  test('curiosity higher confidence in OPENER than BRIDGE', () => {
    const openerResult = detectNewIntents('tell me more about that', 'OPENER');
    const bridgeResult = detectNewIntents('tell me more about that', 'BRIDGE');
    assert.ok(openerResult.confidence > bridgeResult.confidence);
  });
});
