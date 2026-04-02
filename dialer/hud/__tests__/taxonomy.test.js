// dialer/hud/__tests__/taxonomy.test.js
// Uses Node.js built-in test runner: node --test

import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  INTENTS,
  TONES,
  RISK_LEVELS,
  MOVE_TYPES,
  DELIVERY_MODIFIERS,
  NOW_TEMPLATES,
  ROUTING_PRECEDENCE,
  INTENT_STAGE_MAP,
  OBJECTION_INTENTS,
  OVERLAY_INTENTS,
} from "../taxonomy.js";

// -------------------------
// INTENTS
// -------------------------

describe("INTENTS", () => {
  it("has exactly 17 canonical labels", () => {
    assert.equal(INTENTS.length, 17);
  });

  it("contains all expected labels", () => {
    const expected = [
      "engaged_answer",
      "existing_coverage",
      "answering_service",
      "pricing_question",
      "pricing_resistance",
      "timing",
      "interest",
      "info",
      "authority",
      "authority_mismatch",
      "confusion",
      "curiosity",
      "pain_reveal",
      "brush_off",
      "time_pressure",
      "hedge",
      "yes",
    ];
    assert.deepEqual(INTENTS, expected);
  });

  it("contains no duplicates", () => {
    assert.equal(new Set(INTENTS).size, INTENTS.length);
  });
});

// -------------------------
// TONES
// -------------------------

describe("TONES", () => {
  it("has exactly 7 labels", () => {
    assert.equal(TONES.length, 7);
  });

  it("contains all expected labels", () => {
    const expected = [
      "rushed",
      "skeptical",
      "annoyed",
      "curious",
      "guarded",
      "neutral",
      "unknown",
    ];
    assert.deepEqual(TONES, expected);
  });
});

// -------------------------
// RISK_LEVELS
// -------------------------

describe("RISK_LEVELS", () => {
  it("has exactly 4 levels in order", () => {
    assert.deepEqual(RISK_LEVELS, ["low", "medium", "high", "call_ending"]);
  });
});

// -------------------------
// MOVE_TYPES
// -------------------------

describe("MOVE_TYPES", () => {
  it("has exactly 9 core move types", () => {
    assert.equal(MOVE_TYPES.length, 9);
  });

  it("contains all expected types", () => {
    const expected = [
      "ask",
      "clarify",
      "probe",
      "reframe",
      "bridge",
      "quantify",
      "close",
      "exit",
      "pause",
    ];
    assert.deepEqual(MOVE_TYPES, expected);
  });
});

// -------------------------
// DELIVERY_MODIFIERS
// -------------------------

describe("DELIVERY_MODIFIERS", () => {
  it("has exactly 5 modifiers", () => {
    assert.equal(DELIVERY_MODIFIERS.length, 5);
  });

  it("contains all expected modifiers", () => {
    const expected = ["compress", "soften", "hold", "escalate", "redirect"];
    assert.deepEqual(DELIVERY_MODIFIERS, expected);
  });
});

// -------------------------
// NOW_TEMPLATES
// -------------------------

describe("NOW_TEMPLATES", () => {
  it("has an entry for every intent", () => {
    for (const intent of INTENTS) {
      assert.ok(
        intent in NOW_TEMPLATES,
        `Missing NOW_TEMPLATE for intent: ${intent}`
      );
    }
  });

  it("every template is under 80 characters", () => {
    for (const [intent, template] of Object.entries(NOW_TEMPLATES)) {
      assert.ok(
        template.length < 80,
        `NOW_TEMPLATE for '${intent}' is ${template.length} chars (must be < 80)`
      );
    }
  });

  it("every template is a non-empty string", () => {
    for (const [intent, template] of Object.entries(NOW_TEMPLATES)) {
      assert.equal(typeof template, "string");
      assert.ok(template.length > 0, `NOW_TEMPLATE for '${intent}' is empty`);
    }
  });
});

// -------------------------
// ROUTING_PRECEDENCE
// -------------------------

describe("ROUTING_PRECEDENCE", () => {
  it("contains every intent exactly once", () => {
    assert.equal(ROUTING_PRECEDENCE.length, INTENTS.length);
    assert.equal(new Set(ROUTING_PRECEDENCE).size, ROUTING_PRECEDENCE.length);
    for (const intent of INTENTS) {
      assert.ok(
        ROUTING_PRECEDENCE.includes(intent),
        `Missing from ROUTING_PRECEDENCE: ${intent}`
      );
    }
  });
});

// -------------------------
// INTENT_STAGE_MAP
// -------------------------

describe("INTENT_STAGE_MAP", () => {
  it("maps expected intents to stages", () => {
    assert.equal(INTENT_STAGE_MAP.pricing_question, "PRICING");
    assert.equal(INTENT_STAGE_MAP.pricing_resistance, "PRICING");
    assert.equal(INTENT_STAGE_MAP.authority_mismatch, "WRONG_PERSON");
    assert.equal(INTENT_STAGE_MAP.confusion, "MINI_PITCH");
  });
});

// -------------------------
// OBJECTION_INTENTS
// -------------------------

describe("OBJECTION_INTENTS", () => {
  it("contains exactly the 4 objection intents", () => {
    assert.deepEqual(OBJECTION_INTENTS, [
      "timing",
      "interest",
      "info",
      "authority",
    ]);
  });

  it("every entry is a valid intent", () => {
    for (const intent of OBJECTION_INTENTS) {
      assert.ok(INTENTS.includes(intent), `Invalid intent: ${intent}`);
    }
  });
});

// -------------------------
// OVERLAY_INTENTS
// -------------------------

describe("OVERLAY_INTENTS", () => {
  it("contains exactly the 2 overlay intents", () => {
    assert.deepEqual(OVERLAY_INTENTS, [
      "existing_coverage",
      "answering_service",
    ]);
  });

  it("every entry is a valid intent", () => {
    for (const intent of OVERLAY_INTENTS) {
      assert.ok(INTENTS.includes(intent), `Invalid intent: ${intent}`);
    }
  });
});
