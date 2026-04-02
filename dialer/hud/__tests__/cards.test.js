// dialer/hud/__tests__/cards.test.js
// Uses Node.js built-in test runner: node --test

import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  CARD_FIELDS,
  STAGE_MOVE_MAP,
  makeEmptyCard,
  normalizeCard,
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
