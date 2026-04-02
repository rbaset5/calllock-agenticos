// dialer/hud/__tests__/cards.test.js
// Uses Node.js built-in test runner: node --test

import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  CARD_FIELDS,
  makeEmptyCard,
  normalizeCard,
  NATIVE_STAGE_CARDS,
  NATIVE_OBJECTION_CARDS,
} from "../cards.js";
import { PLAYBOOK } from "../playbook.js";

// -------------------------
// CARD_FIELDS constant
// -------------------------

describe("CARD_FIELDS", () => {
  const expected = [
    "id",
    "stage",
    "moveType",
    "deliveryModifier",
    "goal",
    "primaryLine",
    "backupLine",
    "why",
    "listenFor",
    "branchPreview",
    "clarifyingQuestion",
    "valueProp",
    "proofPoint",
    "toneVariants",
  ];

  it("lists all 14 required fields", () => {
    assert.equal(CARD_FIELDS.length, 14);
    assert.deepStrictEqual(CARD_FIELDS, expected);
  });
});

// -------------------------
// makeEmptyCard
// -------------------------

describe("makeEmptyCard", () => {
  it("returns a card with all 14 fields", () => {
    const card = makeEmptyCard("OPENER");
    for (const field of CARD_FIELDS) {
      assert.ok(
        field in card,
        `missing field: ${field}`
      );
    }
    assert.equal(Object.keys(card).length, CARD_FIELDS.length);
  });

  it("sets stage and id from stageId", () => {
    const card = makeEmptyCard("CLOSE");
    assert.equal(card.stage, "CLOSE");
    assert.equal(card.id, "CLOSE");
  });

  it("infers moveType from STAGE_MOVE_MAP", () => {
    assert.equal(makeEmptyCard("OPENER").moveType, "ask");
    assert.equal(makeEmptyCard("CLOSE").moveType, "close");
    assert.equal(makeEmptyCard("EXIT").moveType, "exit");
    assert.equal(makeEmptyCard("BRIDGE").moveType, "bridge");
  });

  it("falls back to 'pause' for unknown stages", () => {
    assert.equal(makeEmptyCard("UNKNOWN_STAGE").moveType, "pause");
  });
});

// -------------------------
// normalizeCard
// -------------------------

describe("normalizeCard", () => {
  it("fills primaryLine from playbook for OPENER", () => {
    const card = normalizeCard("OPENER", PLAYBOOK);
    assert.equal(card.primaryLine, PLAYBOOK.opener);
    assert.equal(card.moveType, "ask");
    assert.equal(card.stage, "OPENER");
  });

  it("fills primaryLine from playbook for CLOSE", () => {
    const card = normalizeCard("CLOSE", PLAYBOOK);
    assert.equal(card.primaryLine, PLAYBOOK.close);
    assert.equal(card.moveType, "close");
  });

  it("fills primaryLine from playbook for EXIT", () => {
    const card = normalizeCard("EXIT", PLAYBOOK);
    assert.equal(card.primaryLine, PLAYBOOK.exit);
    assert.equal(card.moveType, "exit");
  });

  it("fills primaryLine from playbook for BRIDGE", () => {
    const card = normalizeCard("BRIDGE", PLAYBOOK);
    assert.equal(card.primaryLine, PLAYBOOK.bridge.fallback);
    assert.equal(card.moveType, "bridge");
  });

  it("returns empty primaryLine for unknown stages", () => {
    const card = normalizeCard("UNKNOWN_STAGE", PLAYBOOK);
    assert.equal(card.primaryLine, "");
    assert.equal(card.moveType, "pause");
  });

  it("produces a card with all 14 fields", () => {
    const card = normalizeCard("QUALIFIER", PLAYBOOK);
    for (const field of CARD_FIELDS) {
      assert.ok(field in card, `missing field: ${field}`);
    }
  });
});

// -------------------------
// NATIVE_STAGE_CARDS
// -------------------------

const ALL_NATIVE_STAGES = [
  'OPENER', 'BRIDGE', 'QUALIFIER', 'CLOSE', 'OBJECTION',
  'EXIT', 'SEED_EXIT', 'BOOKED', 'NON_CONNECT', 'GATEKEEPER', 'IDLE',
  'PERMISSION_MOMENT', 'MINI_PITCH', 'WRONG_PERSON', 'PRICING',
  'CALLBACK_CLOSE', 'TRANSFER_CLOSE', 'DIAGNOSTIC_CLOSE', 'REFERRAL_CLOSE',
];

describe("NATIVE_STAGE_CARDS", () => {
  it("exports all 19 stages", () => {
    for (const stage of ALL_NATIVE_STAGES) {
      assert.ok(stage in NATIVE_STAGE_CARDS, `missing stage: ${stage}`);
    }
    assert.equal(Object.keys(NATIVE_STAGE_CARDS).length, 19);
  });

  it("every card has id matching its key", () => {
    for (const [key, card] of Object.entries(NATIVE_STAGE_CARDS)) {
      assert.equal(card.id, key, `id mismatch for ${key}`);
    }
  });

  it("every card has all 14 v2 fields", () => {
    for (const [key, card] of Object.entries(NATIVE_STAGE_CARDS)) {
      for (const field of CARD_FIELDS) {
        assert.ok(field in card, `${key} missing field: ${field}`);
      }
    }
  });

  it("every card has ≤4 listenFor items", () => {
    for (const [key, card] of Object.entries(NATIVE_STAGE_CARDS)) {
      assert.ok(
        Array.isArray(card.listenFor) && card.listenFor.length <= 4,
        `${key} listenFor must be array with ≤4 items, got ${card.listenFor}`
      );
    }
  });

  it("every card has ≤3 branchPreview routes", () => {
    for (const [key, card] of Object.entries(NATIVE_STAGE_CARDS)) {
      assert.ok(
        typeof card.branchPreview === 'object' && card.branchPreview !== null,
        `${key} branchPreview must be an object`
      );
      assert.ok(
        Object.keys(card.branchPreview).length <= 3,
        `${key} branchPreview must have ≤3 routes, got ${Object.keys(card.branchPreview).length}`
      );
    }
  });

  // OPENER-specific tests
  describe("OPENER", () => {
    it("has all v2 fields including backupLine, listenFor, branchPreview", () => {
      const c = NATIVE_STAGE_CARDS.OPENER;
      assert.equal(c.stage, 'OPENER');
      assert.equal(c.moveType, 'ask');
      assert.ok(c.primaryLine.length > 0, 'primaryLine must be non-empty');
      assert.ok(c.backupLine.length > 0, 'backupLine must be non-empty');
      assert.ok(Array.isArray(c.listenFor) && c.listenFor.length >= 1);
      assert.ok(Object.keys(c.branchPreview).length >= 1);
      assert.ok(typeof c.toneVariants === 'object' && c.toneVariants !== null);
    });
  });

  // BRIDGE-specific tests
  describe("BRIDGE", () => {
    it("has toneVariants with rushed, annoyed, curious", () => {
      const c = NATIVE_STAGE_CARDS.BRIDGE;
      assert.ok('rushed' in c.toneVariants, 'missing rushed variant');
      assert.ok('annoyed' in c.toneVariants, 'missing annoyed variant');
      assert.ok('curious' in c.toneVariants, 'missing curious variant');
    });
  });

  // CLOSE-specific tests
  describe("CLOSE", () => {
    it("has clarifyingQuestion", () => {
      const c = NATIVE_STAGE_CARDS.CLOSE;
      assert.ok(
        typeof c.clarifyingQuestion === 'string' && c.clarifyingQuestion.length > 0,
        'CLOSE must have a non-empty clarifyingQuestion'
      );
    });
  });

  // PERMISSION_MOMENT-specific tests
  describe("PERMISSION_MOMENT", () => {
    it("has moveType 'ask' and toneVariants.rushed", () => {
      const c = NATIVE_STAGE_CARDS.PERMISSION_MOMENT;
      assert.equal(c.moveType, 'ask');
      assert.equal(c.id, 'PERMISSION_MOMENT');
      assert.ok(c.primaryLine.length > 0, 'primaryLine must be non-empty');
      assert.ok(c.backupLine.length > 0, 'backupLine must be non-empty');
      assert.ok(c.why.length > 0, 'why must be non-empty');
      assert.ok('rushed' in c.toneVariants, 'missing rushed variant');
      assert.ok(Object.keys(c.branchPreview).length === 3, 'branchPreview must have 3 routes');
    });
  });

  // MINI_PITCH-specific tests
  describe("MINI_PITCH", () => {
    it("has moveType 'clarify', deliveryModifier 'compress', and clarifyingQuestion", () => {
      const c = NATIVE_STAGE_CARDS.MINI_PITCH;
      assert.equal(c.moveType, 'clarify');
      assert.equal(c.deliveryModifier, 'compress');
      assert.equal(c.id, 'MINI_PITCH');
      assert.ok(c.primaryLine.length > 0, 'primaryLine must be non-empty');
      assert.ok(c.backupLine.length > 0, 'backupLine must be non-empty');
      assert.ok(c.clarifyingQuestion.length > 0, 'clarifyingQuestion must be non-empty');
      assert.ok(Object.keys(c.branchPreview).length === 2, 'branchPreview must have 2 routes');
    });
  });

  // WRONG_PERSON-specific tests
  describe("WRONG_PERSON", () => {
    it("has moveType 'clarify' and clarifyingQuestion", () => {
      const c = NATIVE_STAGE_CARDS.WRONG_PERSON;
      assert.equal(c.moveType, 'clarify');
      assert.equal(c.id, 'WRONG_PERSON');
      assert.ok(c.primaryLine.length > 0, 'primaryLine must be non-empty');
      assert.ok(c.backupLine.length > 0, 'backupLine must be non-empty');
      assert.ok(c.clarifyingQuestion.length > 0, 'clarifyingQuestion must be non-empty');
      assert.ok(Object.keys(c.branchPreview).length === 2, 'branchPreview must have 2 routes');
    });
  });

  // PRICING-specific tests
  describe("PRICING", () => {
    it("has moveType 'reframe', valueProp, proofPoint, toneVariants.annoyed", () => {
      const c = NATIVE_STAGE_CARDS.PRICING;
      assert.equal(c.moveType, 'reframe');
      assert.equal(c.id, 'PRICING');
      assert.ok(c.primaryLine.length > 0, 'primaryLine must be non-empty');
      assert.ok(c.backupLine.length > 0, 'backupLine must be non-empty');
      assert.ok(c.valueProp.length > 0, 'valueProp must be non-empty');
      assert.ok(c.proofPoint.length > 0, 'proofPoint must be non-empty');
      assert.ok(c.clarifyingQuestion.length > 0, 'clarifyingQuestion must be non-empty');
      assert.ok('annoyed' in c.toneVariants, 'missing annoyed variant');
      assert.ok(Object.keys(c.branchPreview).length === 2, 'branchPreview must have 2 routes');
    });
  });

  // ── Close variant cards ─────────────────────────────────────
  const CLOSE_VARIANT_KEYS = ['CALLBACK_CLOSE', 'TRANSFER_CLOSE', 'DIAGNOSTIC_CLOSE', 'REFERRAL_CLOSE'];

  describe("close variant cards", () => {
    it("all 4 close variants exist", () => {
      for (const key of CLOSE_VARIANT_KEYS) {
        assert.ok(key in NATIVE_STAGE_CARDS, `missing close variant: ${key}`);
      }
    });

    it("all close variants have moveType 'close'", () => {
      for (const key of CLOSE_VARIANT_KEYS) {
        assert.equal(NATIVE_STAGE_CARDS[key].moveType, 'close', `${key} moveType must be 'close'`);
      }
    });

    it("all close variants have required fields", () => {
      for (const key of CLOSE_VARIANT_KEYS) {
        const c = NATIVE_STAGE_CARDS[key];
        assert.equal(c.id, key, `${key} id must match key`);
        assert.equal(c.stage, key, `${key} stage must match key`);
        assert.ok(typeof c.goal === 'string' && c.goal.length > 0, `${key} must have non-empty goal`);
        assert.ok(typeof c.primaryLine === 'string' && c.primaryLine.length > 0, `${key} must have non-empty primaryLine`);
        assert.ok(typeof c.backupLine === 'string' && c.backupLine.length > 0, `${key} must have non-empty backupLine`);
        assert.ok(typeof c.why === 'string' && c.why.length > 0, `${key} must have non-empty why`);
        assert.ok(Array.isArray(c.listenFor) && c.listenFor.length >= 1, `${key} must have listenFor array`);
        assert.ok(typeof c.branchPreview === 'object' && c.branchPreview !== null, `${key} must have branchPreview`);
        assert.ok(typeof c.clarifyingQuestion === 'string' && c.clarifyingQuestion.length > 0, `${key} must have non-empty clarifyingQuestion`);
        for (const field of CARD_FIELDS) {
          assert.ok(field in c, `${key} missing field: ${field}`);
        }
      }
    });

    it("DIAGNOSTIC_CLOSE has deliveryModifier 'soften'", () => {
      assert.equal(NATIVE_STAGE_CARDS.DIAGNOSTIC_CLOSE.deliveryModifier, 'soften');
    });

    it("REFERRAL_CLOSE branchPreview has only engaged route", () => {
      assert.equal(Object.keys(NATIVE_STAGE_CARDS.REFERRAL_CLOSE.branchPreview).length, 1);
      assert.ok('engaged' in NATIVE_STAGE_CARDS.REFERRAL_CLOSE.branchPreview);
    });
  });
});

// -------------------------
// NATIVE_OBJECTION_CARDS
// -------------------------

const ALL_OBJECTION_KEYS = [
  'timing', 'interest', 'info', 'authority', 'existing_coverage', 'answering_service',
];

describe("NATIVE_OBJECTION_CARDS", () => {
  it("exports all 6 objection cards", () => {
    for (const key of ALL_OBJECTION_KEYS) {
      assert.ok(key in NATIVE_OBJECTION_CARDS, `missing objection card: ${key}`);
    }
    assert.equal(Object.keys(NATIVE_OBJECTION_CARDS).length, 6);
  });

  it("every card has id matching its key", () => {
    for (const [key, card] of Object.entries(NATIVE_OBJECTION_CARDS)) {
      assert.equal(card.id, key, `id mismatch for ${key}`);
    }
  });

  it("every card has all 14 CARD_FIELDS", () => {
    for (const [key, card] of Object.entries(NATIVE_OBJECTION_CARDS)) {
      for (const field of CARD_FIELDS) {
        assert.ok(field in card, `${key} missing field: ${field}`);
      }
    }
  });

  it("every card has primaryLine, backupLine, and clarifyingQuestion", () => {
    for (const [key, card] of Object.entries(NATIVE_OBJECTION_CARDS)) {
      assert.ok(
        typeof card.primaryLine === 'string' && card.primaryLine.length > 0,
        `${key} must have non-empty primaryLine`
      );
      assert.ok(
        typeof card.backupLine === 'string' && card.backupLine.length > 0,
        `${key} must have non-empty backupLine`
      );
      assert.ok(
        typeof card.clarifyingQuestion === 'string' && card.clarifyingQuestion.length > 0,
        `${key} must have non-empty clarifyingQuestion`
      );
    }
  });

  it("every card has stage 'OBJECTION'", () => {
    for (const [key, card] of Object.entries(NATIVE_OBJECTION_CARDS)) {
      assert.equal(card.stage, 'OBJECTION', `${key} stage must be OBJECTION`);
    }
  });

  it("every card has ≤4 listenFor items", () => {
    for (const [key, card] of Object.entries(NATIVE_OBJECTION_CARDS)) {
      assert.ok(
        Array.isArray(card.listenFor) && card.listenFor.length <= 4,
        `${key} listenFor must be array with ≤4 items`
      );
    }
  });

  it("every card has ≤3 branchPreview routes", () => {
    for (const [key, card] of Object.entries(NATIVE_OBJECTION_CARDS)) {
      assert.ok(
        typeof card.branchPreview === 'object' && card.branchPreview !== null,
        `${key} branchPreview must be an object`
      );
      assert.ok(
        Object.keys(card.branchPreview).length <= 3,
        `${key} branchPreview must have ≤3 routes`
      );
    }
  });

  // timing-specific
  describe("timing", () => {
    it("has moveType 'reframe', deliveryModifier 'compress', toneVariants.annoyed", () => {
      const c = NATIVE_OBJECTION_CARDS.timing;
      assert.equal(c.moveType, 'reframe');
      assert.equal(c.deliveryModifier, 'compress');
      assert.ok('annoyed' in c.toneVariants, 'missing annoyed variant');
    });
  });

  // interest-specific
  describe("interest", () => {
    it("has moveType 'probe', valueProp, and proofPoint", () => {
      const c = NATIVE_OBJECTION_CARDS.interest;
      assert.equal(c.moveType, 'probe');
      assert.ok(c.valueProp.length > 0, 'valueProp must be non-empty');
      assert.ok(c.proofPoint.length > 0, 'proofPoint must be non-empty');
    });
  });

  // existing_coverage-specific
  describe("existing_coverage", () => {
    it("has moveType 'probe', valueProp, proofPoint, toneVariants.curious", () => {
      const c = NATIVE_OBJECTION_CARDS.existing_coverage;
      assert.equal(c.moveType, 'probe');
      assert.ok(c.valueProp.length > 0, 'valueProp must be non-empty');
      assert.ok(c.proofPoint.length > 0, 'proofPoint must be non-empty');
      assert.ok('curious' in c.toneVariants, 'missing curious variant');
    });
  });

  // answering_service-specific
  describe("answering_service", () => {
    it("has moveType 'probe', valueProp, and proofPoint", () => {
      const c = NATIVE_OBJECTION_CARDS.answering_service;
      assert.equal(c.moveType, 'probe');
      assert.ok(c.valueProp.length > 0, 'valueProp must be non-empty');
      assert.ok(c.proofPoint.length > 0, 'proofPoint must be non-empty');
    });
  });

  // authority-specific
  describe("authority", () => {
    it("has moveType 'clarify'", () => {
      const c = NATIVE_OBJECTION_CARDS.authority;
      assert.equal(c.moveType, 'clarify');
    });
  });

  // info-specific
  describe("info", () => {
    it("has moveType 'probe'", () => {
      const c = NATIVE_OBJECTION_CARDS.info;
      assert.equal(c.moveType, 'probe');
    });
  });
});
