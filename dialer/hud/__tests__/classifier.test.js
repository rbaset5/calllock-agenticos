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

  it('"Did someone give you my info?" should NOT match info objection bucket', () => {
    // "info" as a standalone word in a non-objection context should not trigger info bucket
    const r = classifyUtterance("Did someone give you my info?", { stage: "OPENER" });
    assert.notEqual(r.objectionBucket, "info");
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

// ── QA simulation fixes (50-scenario E2E audit 2026-04-03) ──────

describe('short utterance heuristics', () => {
  test('"No" → brush_off intent', () => {
    const r = detectNewIntents('No', 'OPENER');
    assert.equal(r.intent, 'brush_off');
  });

  test('"Huh?" → confusion intent', () => {
    const r = detectNewIntents('Huh?', 'OPENER');
    assert.equal(r.intent, 'confusion');
  });

  test('"Yeah" → engaged_answer intent', () => {
    const r = detectNewIntents('Yeah', 'BRIDGE');
    assert.equal(r.intent, 'engaged_answer');
  });

  test('"Bye" → brush_off intent', () => {
    const r = detectNewIntents('Bye', 'OPENER');
    assert.equal(r.intent, 'brush_off');
  });

  test('"What" → confusion intent', () => {
    const r = detectNewIntents('What', 'OPENER');
    assert.equal(r.intent, 'confusion');
  });

  test('longer utterances do not trigger short map', () => {
    const r = detectNewIntents('yeah we get some calls after hours', 'BRIDGE');
    // Should NOT match short utterance map "yeah" — too many words
    assert.ok(r === null || r.intent !== 'engaged_answer');
  });
});

describe('exit-intent detection', () => {
  test('"Take me off your calling list" → brush_off (high confidence)', () => {
    const r = detectNewIntents('Take me off your calling list', 'OPENER');
    assert.equal(r.intent, 'brush_off');
    assert.ok(r.confidence >= 0.80);
  });

  test('"Wrong number" → brush_off', () => {
    const r = detectNewIntents('This is a wrong number buddy', 'OPENER');
    assert.equal(r.intent, 'brush_off');
  });

  test('"We closed down" → brush_off', () => {
    const r = detectNewIntents('We actually closed down last month', 'OPENER');
    assert.equal(r.intent, 'brush_off');
  });

  test('"Stop calling me" → brush_off', () => {
    const r = detectNewIntents('Stop calling me this is harassment', 'OPENER');
    assert.equal(r.intent, 'brush_off');
    assert.ok(r.confidence >= 0.80);
  });

  test('"I retired" → brush_off', () => {
    const r = detectNewIntents('Yeah I retired last year', 'OPENER');
    assert.equal(r.intent, 'brush_off');
  });
});

describe('conference call detection (not authority_mismatch)', () => {
  test('"On speaker with my partner" → engaged_answer, NOT authority_mismatch', () => {
    const r = detectNewIntents("Hey you're on speaker with me and my partner", 'OPENER');
    assert.equal(r.intent, 'engaged_answer');
  });

  test('"Both here" → engaged_answer', () => {
    const r = detectNewIntents("We're both here listening", 'OPENER');
    assert.equal(r.intent, 'engaged_answer');
  });
});

describe('yes-intent for scheduling language', () => {
  test('"Thursday works" → yes intent', () => {
    const r = detectNewIntents('Thursday works', 'CLOSE');
    assert.equal(r.intent, 'yes');
  });

  test('"Let\'s do it" → yes intent', () => {
    const r = detectNewIntents("Let's do it", 'CLOSE');
    assert.equal(r.intent, 'yes');
  });

  test('"Set something up" → yes intent', () => {
    const r = detectNewIntents('Yeah set something up', 'CLOSE');
    assert.equal(r.intent, 'yes');
  });

  test('"Morning works" → yes intent', () => {
    const r = detectNewIntents('Morning works for me', 'CLOSE');
    assert.equal(r.intent, 'yes');
  });
});

describe('BRIDGE numeric responses route to qualifier', () => {
  test('"Maybe 5 or 6 a week" at BRIDGE → qualifierRead', () => {
    const r = classifyUtterance('Maybe 5 or 6 a week', { stage: 'BRIDGE' });
    assert.ok(r.qualifierRead, `Expected qualifierRead, got: ${JSON.stringify(r)}`);
  });

  test('"Probably 10-12" at BRIDGE → qualifierRead', () => {
    const r = classifyUtterance('Probably 10-12 a week', { stage: 'BRIDGE' });
    assert.ok(r.qualifierRead, `Expected qualifierRead, got: ${JSON.stringify(r)}`);
  });

  test('"At least 4 or 5" at BRIDGE → qualifierRead', () => {
    const r = classifyUtterance('At least 4 or 5 that I know of', { stage: 'BRIDGE' });
    assert.ok(r.qualifierRead, `Expected qualifierRead, got: ${JSON.stringify(r)}`);
  });

  test('Pain words WITHOUT numbers at BRIDGE → still bridge angle', () => {
    const r = classifyUtterance('We miss some calls sometimes', { stage: 'BRIDGE' });
    assert.ok(r.bridgeAngle, `Expected bridgeAngle, got: ${JSON.stringify(r)}`);
  });
});

describe('Gap 3: missing phrase patterns', () => {
  test('"He\'s in a meeting, can I take a message?" → authority_mismatch', () => {
    const r = detectNewIntents("He's in a meeting, can I take a message?", 'OPENER');
    assert.equal(r.intent, 'authority_mismatch');
  });

  test('"You\'ve reached Peak HVAC, leave a message" → brush_off (voicemail)', () => {
    const r = detectNewIntents("You've reached Peak HVAC, leave a message after the tone", 'OPENER');
    assert.equal(r.intent, 'brush_off');
  });
});

describe('Gap 6: time pressure detection at OPENER', () => {
  test('"Make it quick I got a truck to load" → time_pressure', () => {
    const r = detectNewIntents('Make it quick I got a truck to load', 'OPENER');
    assert.equal(r.intent, 'time_pressure');
  });

  test('"I\'m busy" at OPENER → time_pressure', () => {
    const r = detectNewIntents("I'm busy right now", 'OPENER');
    assert.equal(r.intent, 'time_pressure');
  });

  test('"I\'m busy" at CLOSE → NOT time_pressure (let objection classifier handle)', () => {
    const r = detectNewIntents("I'm busy right now", 'CLOSE');
    assert.equal(r, null);
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

// ── Round 2: New pattern regression tests ──────────────────────────

describe('Round 2: engagement patterns for BRIDGE advancement', () => {
  test('"sounds like what we need" → curiosity', () => {
    const r = detectNewIntents('sounds like what we need', 'BRIDGE');
    assert.equal(r.intent, 'curiosity');
  });

  test('"returning your call" → curiosity', () => {
    const r = detectNewIntents('returning your call, what was this about?', 'OPENER');
    assert.equal(r.intent, 'curiosity');
  });

  test('"can you do that" → curiosity', () => {
    const r = detectNewIntents('can you do that?', 'BRIDGE');
    assert.equal(r.intent, 'curiosity');
  });

  test('"that would help" → curiosity', () => {
    const r = detectNewIntents('that would help', 'BRIDGE');
    assert.equal(r.intent, 'curiosity');
  });
});

describe('Round 2: yes-intent expansions', () => {
  test('"fine thursday" → yes', () => {
    const r = detectNewIntents('fine thursday at 2', 'CLOSE');
    assert.equal(r.intent, 'yes');
  });

  test('"put me down for Thursday" → yes', () => {
    const r = detectNewIntents('put me down for Thursday at 10', 'QUALIFIER');
    assert.equal(r.intent, 'yes');
  });

  test('"set up a call" → yes', () => {
    const r = detectNewIntents('set up a call for Friday', 'CLOSE');
    assert.equal(r.intent, 'yes');
  });

  test('"esta bien" (bilingual) → yes', () => {
    const r = detectNewIntents('ok thursday esta bien', 'CLOSE');
    assert.equal(r.intent, 'yes');
  });

  test('"thursday i guess" → yes', () => {
    const r = detectNewIntents('thursday i guess', 'QUALIFIER');
    assert.equal(r.intent, 'yes');
  });
});

describe('Round 2: WRONG_PERSON phrase expansions', () => {
  test('"I\'m just the tech" → authority_mismatch', () => {
    const r = detectNewIntents("boss isn't here, I'm just the tech", 'OPENER');
    assert.equal(r.intent, 'authority_mismatch');
  });

  test('"just the technician" → authority_mismatch', () => {
    const r = detectNewIntents("i'm just the technician", 'OPENER');
    assert.equal(r.intent, 'authority_mismatch');
  });
});

describe('Round 2: weekend/after-hours bridge angle', () => {
  test('"weekends are tough" detected in bridge classifier', () => {
    const r = classifyUtterance('weekends are tough, we close at noon Saturday', { stage: 'OPENER' });
    assert.ok(r.confidence >= 0.5, 'Should have non-trivial confidence');
  });
});

describe('Round 2: exit-intent expansions', () => {
  test('"not going to take a message" → brush_off', () => {
    const r = detectNewIntents("I'm not going to take a message, goodbye", 'WRONG_PERSON');
    assert.equal(r.intent, 'brush_off');
  });
});

// ── Codex adversarial review fixes ─────────────────────────────────

describe('Codex fix: "i\'m in" false positive', () => {
  test('"I\'m in the middle of an install" should NOT match yes-intent', () => {
    const r = detectNewIntents("Bad time, I'm in the middle of an install", 'OPENER');
    assert.notEqual(r?.intent, 'yes', '"i\'m in" substring should not trigger yes');
  });
});

describe('Codex fix: confusion phrases expanded', () => {
  test('"I don\'t understand" → confusion', () => {
    const r = detectNewIntents("Wait what? I don't understand what you're saying", 'OPENER');
    assert.equal(r.intent, 'confusion');
  });

  test('"what are you talking about" → confusion', () => {
    const r = detectNewIntents("what are you talking about", 'OPENER');
    assert.equal(r.intent, 'confusion');
  });
});

describe('Codex fix: transfer phrases → WRONG_PERSON', () => {
  test('"let me transfer you" → authority_mismatch', () => {
    const r = detectNewIntents("let me transfer you to the owner", 'OPENER');
    assert.equal(r.intent, 'authority_mismatch');
  });

  test('"i\'ll get the owner" → authority_mismatch', () => {
    const r = detectNewIntents("hold on, i'll get the owner", 'OPENER');
    assert.equal(r.intent, 'authority_mismatch');
  });
});

describe('Codex fix: expanded YES_PHRASES', () => {
  test('"Friday at 2 would work" → yes', () => {
    const r = detectNewIntents("Friday at 2 would work", 'CLOSE');
    assert.equal(r.intent, 'yes');
  });

  test('"Wednesday at 4" → yes', () => {
    const r = detectNewIntents("OK let me look, Wednesday at 4", 'QUALIFIER');
    assert.equal(r.intent, 'yes');
  });

  test('"works for both of us" → yes', () => {
    const r = detectNewIntents("Thursday works for both of us", 'CLOSE');
    assert.equal(r.intent, 'yes');
  });

  test('"that works" → yes', () => {
    const r = detectNewIntents("yeah that works for me", 'QUALIFIER');
    assert.equal(r.intent, 'yes');
  });
});

describe('Codex fix: ballpark pricing', () => {
  test('"give me a ballpark" → pricing_question', () => {
    const r = detectNewIntents("just give me a ballpark", 'BRIDGE');
    assert.equal(r.intent, 'pricing_question');
  });
});

// ── Cross-model review fixes ───────────────────────────────────────

describe('MINI_PITCH/WRONG_PERSON deterministic classifier', () => {
  test('MINI_PITCH: "we miss calls all the time" → bridge result', () => {
    const r = classifyUtterance('we miss calls all the time, 5 or 6 a week', { stage: 'MINI_PITCH' });
    assert.ok(r.confidence >= 0.5, 'Should classify with non-trivial confidence from MINI_PITCH');
  });

  test('MINI_PITCH: "voicemail" utterance → bridge result', () => {
    const r = classifyUtterance('yeah everything goes to voicemail', { stage: 'MINI_PITCH' });
    assert.ok(r.confidence >= 0.5);
  });

  test('WRONG_PERSON: "yeah we miss calls" → bridge result', () => {
    const r = classifyUtterance('yeah we miss a lot of calls when he is out', { stage: 'WRONG_PERSON' });
    assert.ok(r.confidence >= 0.5);
  });

  test('MINI_PITCH: vague response → low confidence (LLM fallback)', () => {
    const r = classifyUtterance('oh ok', { stage: 'MINI_PITCH' });
    assert.ok(r.confidence < 0.5, 'Vague response should be low confidence');
  });
});

describe('OBJECTION → bridge signal detection', () => {
  test('OBJECTION: "calls go to voicemail all the time" → bridge signal', () => {
    const r = classifyUtterance('yeah calls go to voicemail all the time', { stage: 'OBJECTION' });
    assert.ok(r.confidence >= 0.5, 'Bridge signal from OBJECTION should classify');
    assert.ok(r.bridgeAngle, 'Should have bridgeAngle for missed_calls');
  });
});

describe('Expanded timing objection phrases', () => {
  test('"don\'t have time right now" → timing objection', () => {
    const r = classifyUtterance("I don't have time for this right now", { stage: 'OBJECTION' });
    assert.ok(r.objectionBucket === 'timing' || r.confidence >= 0.5);
  });
});

describe('Expanded pricing phrases', () => {
  test('"tell me the price" → pricing_question', () => {
    const r = detectNewIntents("just tell me the price", 'BRIDGE');
    assert.equal(r.intent, 'pricing_question');
  });

  test('"what does something like this cost" → pricing_question', () => {
    const r = detectNewIntents("what does something like this cost?", 'QUALIFIER');
    assert.equal(r.intent, 'pricing_question');
  });
});

describe('Expanded curiosity phrases', () => {
  test('"how does it work" → curiosity', () => {
    const r = detectNewIntents("so how does it work exactly?", 'BRIDGE');
    assert.equal(r.intent, 'curiosity');
  });

  test('"sounds interesting" → curiosity', () => {
    const r = detectNewIntents("sounds interesting, tell me more", 'OPENER');
    assert.equal(r.intent, 'curiosity');
  });
});

describe('Final review: "interested" polarity fix', () => {
  test('"Yeah I\'m interested" → curiosity, NOT interest objection', () => {
    const r = detectNewIntents("Yeah I'm interested", 'OPENER');
    assert.equal(r.intent, 'curiosity', '"i\'m interested" should match curiosity before objection word scoring');
    assert.notEqual(r.intent, 'authority_mismatch');
  });

  test('"Not interested" still routes through objection classifier (not detectNewIntents)', () => {
    const r = detectNewIntents("Not interested, we're good", 'OPENER');
    // "not interested" is NOT in curiosity phrases, so detectNewIntents returns null
    // The stage-specific classifier (classifyBridge) handles it via OBJECTION_BUCKETS
    assert.equal(r, null, '"not interested" should not match curiosity');
  });

  test('"That\'s interesting" → curiosity', () => {
    const r = detectNewIntents("that's interesting, tell me more", 'OPENER');
    assert.equal(r.intent, 'curiosity');
  });
});

describe('Anti-AI and competitor phrases', () => {
  test('"some robot" → tried_ai', () => {
    const r = detectNewIntents("I'm not putting some robot between me and my customers", 'BRIDGE');
    assert.equal(r.intent, 'tried_ai');
    assert.ok(r.confidence >= 0.65);
  });

  test('"AI voice things" → tried_ai', () => {
    const r = detectNewIntents("is this a real person answering, or is this one of those AI voice things?", 'MINI_PITCH');
    assert.equal(r.intent, 'tried_ai');
    assert.ok(r.confidence >= 0.65);
  });

  test('tried_ai wins over "take a message" wrong_person collision', () => {
    const r = detectNewIntents("What usually happens is they take a message, screw up the details. Is this one of those AI voice things?", 'MINI_PITCH');
    assert.equal(r.intent, 'tried_ai');
    assert.notEqual(r.intent, 'authority_mismatch');
  });

  test('"what makes this any different" → competitor_comparison', () => {
    const r = detectNewIntents("what makes this any different from the last guy who called", 'MINI_PITCH');
    assert.equal(r.intent, 'competitor_comparison');
    assert.ok(r.confidence >= 0.65);
  });
});
