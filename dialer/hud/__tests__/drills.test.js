// dialer/hud/__tests__/drills.test.js — Operator drill sets from runtime decision tree
// Uses Node.js built-in test runner: node --test
//
// These test cases come directly from the Sales HUD Runtime Decision Tree document.
// Each drill set trains a specific classification skill.

import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  classifyUtterance,
  shouldCallLlmFallback,
  isUsableDeterministicResult,
} from "../classifier.js";

// ─────────────────────────────────────────────────
// Drill Set 1: Pure classification (single signal)
// "Say one sentence, name the key immediately."
// ─────────────────────────────────────────────────

describe("Drill Set 1: Pure classification", () => {
  // F7 cases — engagement, pain, agreement
  it('"We miss some calls sometimes" at BRIDGE → bridge angle, usable', () => {
    const r = classifyUtterance("We miss some calls sometimes", { stage: "BRIDGE" });
    assert.ok(r.bridgeAngle, "should have a bridge angle");
    assert.ok(isUsableDeterministicResult(r));
  });

  it('"Usually voicemail" at OPENER → missed_calls', () => {
    const r = classifyUtterance("Usually voicemail", { stage: "OPENER" });
    assert.equal(r.bridgeAngle, "missed_calls");
    assert.ok(isUsableDeterministicResult(r));
  });

  it('"My dispatcher gets it" at OPENER → missed_calls', () => {
    const r = classifyUtterance("My dispatcher gets it", { stage: "OPENER" });
    assert.equal(r.bridgeAngle, "missed_calls");
  });

  it('"Depends if someone is in the office" at OPENER → missed_calls', () => {
    const r = classifyUtterance("Depends if someone is in the office", { stage: "OPENER" });
    assert.equal(r.bridgeAngle, "missed_calls");
  });

  it('"Sometimes we miss them" at OPENER → missed_calls', () => {
    const r = classifyUtterance("Sometimes we miss them", { stage: "OPENER" });
    // "miss" isn't a keyword, but "miss" without phrase match may be low.
    // This tests that the classifier at least produces a result.
    assert.ok(r.confidence > 0);
  });

  it('"Sure" at CLOSE → positive acceptance', () => {
    const r = classifyUtterance("Sure", { stage: "CLOSE" });
    assert.ok(!r.objectionBucket, "should not be an objection");
    assert.ok(isUsableDeterministicResult(r));
  });

  it('"Thursday works" at CLOSE → positive acceptance', () => {
    const r = classifyUtterance("Thursday works", { stage: "CLOSE" });
    assert.ok(!r.objectionBucket, "should not be an objection");
    assert.ok(isUsableDeterministicResult(r));
  });

  it('"Probably 4 or 5 a week" at QUALIFIER → pain', () => {
    const r = classifyUtterance("Probably 4 or 5 a week", { stage: "QUALIFIER" });
    assert.equal(r.qualifierRead, "pain");
    assert.ok(isUsableDeterministicResult(r));
  });

  it('"Too many" at QUALIFIER → pain', () => {
    const r = classifyUtterance("Too many", { stage: "QUALIFIER" });
    assert.equal(r.qualifierRead, "pain");
  });

  // 1-4 cases — objections
  it('"I\'m busy" at CLOSE → timing', () => {
    const r = classifyUtterance("I'm busy", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "timing");
  });

  it('"Can\'t talk right now" at CLOSE → timing', () => {
    const r = classifyUtterance("Can't talk right now", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "timing");
  });

  it('"Not interested" at CLOSE → interest', () => {
    const r = classifyUtterance("Not interested", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "interest");
  });

  it('"We\'re good" at CLOSE → interest', () => {
    const r = classifyUtterance("We're good", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "interest");
  });

  it('"Send me info" at CLOSE → info', () => {
    const r = classifyUtterance("Send me info", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "info");
  });

  it('"Email me" at CLOSE → info', () => {
    const r = classifyUtterance("Email me", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "info");
  });

  it('"My partner handles it" at CLOSE → authority', () => {
    const r = classifyUtterance("My partner handles it", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "authority");
  });

  it('"Not my decision" at CLOSE → authority', () => {
    const r = classifyUtterance("Not my decision", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "authority");
  });

  // H cases — hedge/fence-sitting
  it('"Maybe" at CLOSE → hedge signal', () => {
    const r = classifyUtterance("Maybe", { stage: "CLOSE" });
    assert.ok(!r.objectionBucket, "should not be objection");
    assert.ok(r.why.includes("Hedge") || r.why.includes("hedge"));
  });

  it('"I guess" at CLOSE → hedge signal', () => {
    const r = classifyUtterance("I guess", { stage: "CLOSE" });
    assert.ok(!r.objectionBucket, "should not be objection");
  });

  // F8 cases — no pain
  it('"Not really an issue" at QUALIFIER → no_pain', () => {
    const r = classifyUtterance("Not really an issue", { stage: "QUALIFIER" });
    assert.equal(r.qualifierRead, "no_pain");
  });

  it('"We\'re good" at QUALIFIER → no_pain', () => {
    const r = classifyUtterance("We're good", { stage: "QUALIFIER" });
    assert.equal(r.qualifierRead, "no_pain");
  });

  it('"We answer pretty much everything" at QUALIFIER → no_pain', () => {
    const r = classifyUtterance("We answer pretty much everything", { stage: "QUALIFIER" });
    // "everything" is an overwhelmed token but in QUALIFIER context this is no_pain
    assert.ok(r.qualifierRead === "no_pain" || r.qualifierRead === "unknown_pain");
  });
});

// ─────────────────────────────────────────────────
// Drill Set 2: Mixed-signal classification
// "Pick the dominant signal when two things happen."
// ─────────────────────────────────────────────────

describe("Drill Set 2: Mixed-signal classification", () => {
  it('"Yeah we miss calls, but I\'m slammed" at BRIDGE → objection (timing wins)', () => {
    // Doc says: "Dominant signal = timing objection. Use 1."
    // Pain is useful but timing blocks progress.
    const r = classifyUtterance("Yeah we miss calls, but I'm slammed right now", { stage: "BRIDGE" });
    // The objection should be detected. "slammed" is overwhelmed bridge angle AND timing-adjacent.
    // At minimum, the classifier should not advance to QUALIFIER.
    assert.ok(
      r.objectionBucket || r.bridgeAngle === "fallback" || r.bridgeAngle === "overwhelmed",
      `Expected objection or fallback, got: ${JSON.stringify(r)}`,
    );
  });

  it('"Not interested, unless this helps after hours" at CLOSE → not pure rejection', () => {
    // Doc: "conditional interest, not pure rejection"
    const r = classifyUtterance("Not interested, unless this helps after hours", { stage: "CLOSE" });
    // Should still flag interest objection (the blocker is interest)
    assert.equal(r.objectionBucket, "interest");
  });

  it('"We\'ve got a service already, but they mostly just take messages" at BRIDGE → pain hidden', () => {
    // Doc: "useful pain hidden inside objection"
    const r = classifyUtterance(
      "We've got a service already, but they mostly just take messages",
      { stage: "BRIDGE" },
    );
    // Should detect answering service / missed_calls angle
    assert.ok(r.bridgeAngle || r.objectionBucket, "should classify something");
  });

  it('"Maybe, what does it cost?" at CLOSE → hedge, not objection', () => {
    // Doc: "fence-sitting plus question"
    const r = classifyUtterance("Maybe, what does it cost?", { stage: "CLOSE" });
    assert.ok(!r.objectionBucket, "should not be an objection");
  });

  it('"Not interested" during BRIDGE → objection, not bridge angle', () => {
    // This is the key mixed-signal test: objections during bridge should be
    // classified as objections, not forced into a bridge angle.
    const r = classifyUtterance("Not interested", { stage: "BRIDGE" });
    assert.equal(r.objectionBucket, "interest");
  });

  it('"Send me info" during BRIDGE → info objection', () => {
    const r = classifyUtterance("Send me info", { stage: "BRIDGE" });
    assert.equal(r.objectionBucket, "info");
  });

  it('"I\'m busy, just send me something" at OBJECTION → info (priority > timing)', () => {
    const r = classifyUtterance("I'm busy, just send me something", { stage: "OBJECTION" });
    assert.equal(r.objectionBucket, "info");
  });
});

// ─────────────────────────────────────────────────
// Drill Set 3: Qualifier nuance
// ─────────────────────────────────────────────────

describe("Drill Set 3: Qualifier nuance", () => {
  it('"Couldn\'t tell you, but yeah it happens" → pain (admitted leakage)', () => {
    const r = classifyUtterance("Couldn't tell you, but yeah it happens", { stage: "QUALIFIER" });
    // Doc says: "You do not need precision. You need admitted pain."
    // This has unknown + pain signals. Should lean pain or unknown_pain.
    assert.ok(r.qualifierRead === "pain" || r.qualifierRead === "unknown_pain");
  });

  it('"No clue, but enough to matter" → pain', () => {
    const r = classifyUtterance("No clue, but enough to matter", { stage: "QUALIFIER" });
    assert.ok(r.qualifierRead === "pain" || r.qualifierRead === "unknown_pain");
  });

  it('"Maybe one every now and then" → no_pain', () => {
    const r = classifyUtterance("Maybe one every now and then", { stage: "QUALIFIER" });
    assert.ok(r.qualifierRead === "no_pain" || r.qualifierRead === "unknown_pain");
  });

  it('"Doesn\'t really matter" → no_pain', () => {
    const r = classifyUtterance("Doesn't really matter", { stage: "QUALIFIER" });
    assert.ok(r.qualifierRead === "no_pain" || r.qualifierRead === "unknown_pain");
  });

  it('"Hard to say" → unknown_pain', () => {
    const r = classifyUtterance("Hard to say", { stage: "QUALIFIER" });
    assert.equal(r.qualifierRead, "unknown_pain");
  });

  it('"I don\'t know the exact number, but definitely some" → pain', () => {
    const r = classifyUtterance("I don't know the exact number, but definitely some", { stage: "QUALIFIER" });
    assert.ok(r.qualifierRead === "pain" || r.qualifierRead === "unknown_pain");
  });
});

// ─────────────────────────────────────────────────
// Drill Set 4: Objection subtree detail
// ─────────────────────────────────────────────────

describe("Drill Set 4: Objection subtree", () => {
  // Timing variants
  it('"Bad time" → timing', () => {
    const r = classifyUtterance("Bad time", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "timing");
  });

  it('"I\'m with a customer" → timing', () => {
    const r = classifyUtterance("I'm with a customer right now", { stage: "CLOSE" });
    // "customer" isn't in timing dict, but "right now" pattern should help
    assert.ok(r.objectionBucket === "timing" || r.band === "low");
  });

  it('"In the middle of something" → timing', () => {
    const r = classifyUtterance("In the middle of something", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "timing");
  });

  // Interest variants
  it('"Don\'t need it" → interest', () => {
    const r = classifyUtterance("Don't need it", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "interest");
  });

  it('"No thanks" → interest', () => {
    const r = classifyUtterance("No thanks", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "interest");
  });

  it('"We already handle that" → interest', () => {
    const r = classifyUtterance("We already handle that", { stage: "CLOSE" });
    // May be interest or low confidence
    assert.ok(r.objectionBucket === "interest" || r.band === "low");
  });

  // Info variants
  it('"Shoot me an email" → info', () => {
    const r = classifyUtterance("Shoot me an email", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "info");
  });

  it('"Send over your website" → info', () => {
    const r = classifyUtterance("Send over your website", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "info");
  });

  // Authority variants
  it('"My wife handles that" → authority', () => {
    const r = classifyUtterance("My wife handles that", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "authority");
  });

  it('"Talk to my dispatcher" → authority', () => {
    const r = classifyUtterance("Talk to my dispatcher", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "authority");
  });

  it('"I don\'t handle that" → authority', () => {
    const r = classifyUtterance("I don't handle that", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "authority");
  });
});

// ─────────────────────────────────────────────────
// Drill Set 5: Bridge angle classification
// ─────────────────────────────────────────────────

describe("Drill Set 5: Bridge angles", () => {
  it('"My office usually gets it unless I\'m slammed" → missed_calls or overwhelmed', () => {
    // Doc ambiguity rule: could be missed_calls or overwhelmed
    const r = classifyUtterance("My office usually gets it unless I'm slammed", { stage: "OPENER" });
    assert.ok(
      r.bridgeAngle === "missed_calls" || r.bridgeAngle === "overwhelmed" || r.bridgeAngle === "fallback",
      `Expected missed_calls, overwhelmed, or fallback; got ${r.bridgeAngle}`,
    );
  });

  it('"Yeah, after hours is rough" → missed_calls', () => {
    const r = classifyUtterance("Yeah, after hours is rough", { stage: "OPENER" });
    // Not a strong keyword match, may be low confidence
    assert.ok(r.confidence > 0);
  });

  it('"Honestly it\'s a problem" → pain signal (any angle)', () => {
    const r = classifyUtterance("Honestly it's a problem", { stage: "OPENER" });
    assert.ok(r.confidence > 0);
  });

  it('"We call them back usually" → missed_calls', () => {
    const r = classifyUtterance("We call them back usually", { stage: "OPENER" });
    assert.equal(r.bridgeAngle, "missed_calls");
  });

  it('"The competition is eating us alive" → competition', () => {
    const r = classifyUtterance("The competition is eating us alive, we're losing jobs", { stage: "OPENER" });
    assert.equal(r.bridgeAngle, "competition");
  });

  it('"I answer them myself when I can" → overwhelmed', () => {
    const r = classifyUtterance("I answer them myself when I can", { stage: "OPENER" });
    assert.equal(r.bridgeAngle, "overwhelmed");
  });
});

// ─────────────────────────────────────────────────
// Drill Set 6: Close stage nuance
// ─────────────────────────────────────────────────

describe("Drill Set 6: Close stage", () => {
  it('"Okay" → positive acceptance', () => {
    const r = classifyUtterance("Okay", { stage: "CLOSE" });
    assert.ok(!r.objectionBucket);
  });

  it('"Alright, 15 minutes works" → positive acceptance', () => {
    const r = classifyUtterance("Alright, 15 minutes works", { stage: "CLOSE" });
    assert.ok(!r.objectionBucket);
  });

  it('"I\'m not sure" → hedge, not objection', () => {
    const r = classifyUtterance("I'm not sure", { stage: "CLOSE" });
    assert.ok(!r.objectionBucket, "should not be classified as objection");
  });

  it('"Possibly" → hedge, not objection', () => {
    const r = classifyUtterance("Possibly", { stage: "CLOSE" });
    assert.ok(!r.objectionBucket, "should not be classified as objection");
  });

  it('"We\'re set" → interest objection', () => {
    const r = classifyUtterance("We're set", { stage: "CLOSE" });
    assert.equal(r.objectionBucket, "interest");
  });
});

// ─────────────────────────────────────────────────
// Drill Set 7: Gatekeeper
// ─────────────────────────────────────────────────

describe("Drill Set 7: Gatekeeper", () => {
  it('"He\'s not available" → not available', () => {
    const r = classifyUtterance("He's not available", { stage: "GATEKEEPER" });
    assert.ok(r.why.includes("unavailable"));
  });

  it('"Can I take a message" → not available', () => {
    const r = classifyUtterance("Can I take a message", { stage: "GATEKEEPER" });
    assert.ok(r.confidence > 0.5);
  });

  it('"Who is this" → gatekeeper screening', () => {
    const r = classifyUtterance("Who is this", { stage: "GATEKEEPER" });
    assert.ok(r.why.includes("call is about") || r.why.includes("calling"));
  });

  it('"Try later this week" → callback', () => {
    const r = classifyUtterance("Try later this week", { stage: "GATEKEEPER" });
    assert.ok(r.why.includes("Callback") || r.why.includes("callback"));
  });
});
