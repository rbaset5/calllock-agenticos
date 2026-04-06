// dialer/hud/__tests__/hotkey-config.test.js
// Tests for HOTKEY_CONFIG, GLOBAL_HOTKEYS, and keypress event schema.
// Uses Node.js built-in test runner: node --test

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  HOTKEY_CONFIG,
  GLOBAL_HOTKEYS,
  BRIDGE_STAGES,
  KEYPRESS_EVENT_FIELDS,
} from "../taxonomy.js";
import { STAGES } from "../reducer.js";

describe("HOTKEY_CONFIG", () => {
  it("has an entry for every stage in the reducer", () => {
    for (const stage of STAGES) {
      assert.ok(
        stage in HOTKEY_CONFIG,
        `HOTKEY_CONFIG missing entry for stage: ${stage}`
      );
    }
  });

  it("every entry is an array", () => {
    for (const [stage, keys] of Object.entries(HOTKEY_CONFIG)) {
      assert.ok(Array.isArray(keys), `HOTKEY_CONFIG[${stage}] should be an array`);
    }
  });

  it("each hotkey entry has key, label, action, value, type fields", () => {
    for (const [stage, keys] of Object.entries(HOTKEY_CONFIG)) {
      for (const entry of keys) {
        assert.ok(entry.key, `Missing key in ${stage} entry`);
        assert.ok(entry.label, `Missing label in ${stage} entry`);
        assert.ok(entry.action, `Missing action in ${stage} entry`);
        assert.ok(entry.value, `Missing value in ${stage} entry`);
        assert.ok(entry.type, `Missing type in ${stage} entry`);
      }
    }
  });

  it("blocked stages have empty arrays", () => {
    const blockedStages = ["PRICING", "MINI_PITCH", "WRONG_PERSON", "PERMISSION_MOMENT"];
    for (const stage of blockedStages) {
      assert.deepStrictEqual(
        HOTKEY_CONFIG[stage],
        [],
        `${stage} should have empty hotkey config (blocked)`
      );
    }
  });

  it("bridge stages have bridge-type entries", () => {
    for (const stage of BRIDGE_STAGES) {
      const entries = HOTKEY_CONFIG[stage];
      assert.ok(entries.length > 0, `${stage} should have hotkey entries`);
      for (const entry of entries) {
        assert.strictEqual(entry.type, "bridge", `${stage} entries should be type bridge`);
        assert.strictEqual(entry.action, "MANUAL_SET_BRIDGE_ANGLE");
      }
    }
  });

  it("CLOSE and OBJECTION stages have objection-type entries with 4 keys", () => {
    for (const stage of ["CLOSE", "OBJECTION"]) {
      const entries = HOTKEY_CONFIG[stage];
      assert.strictEqual(entries.length, 4, `${stage} should have 4 objection entries`);
      for (const entry of entries) {
        assert.strictEqual(entry.type, "objection");
        assert.strictEqual(entry.action, "MANUAL_SET_OBJECTION");
      }
    }
  });

  it("terminal stages have empty arrays", () => {
    for (const stage of ["IDLE", "EXIT", "ENDED", "BOOKED", "NON_CONNECT"]) {
      assert.deepStrictEqual(
        HOTKEY_CONFIG[stage],
        [],
        `${stage} should have empty hotkey config (terminal/idle)`
      );
    }
  });

  it("bridge angle values match existing BRIDGE_ANGLES", () => {
    const bridgeEntries = HOTKEY_CONFIG["BRIDGE"];
    const values = bridgeEntries.map((e) => e.value);
    assert.ok(values.includes("missed_calls"));
    assert.ok(values.includes("competition"));
    assert.ok(values.includes("overwhelmed"));
  });

  it("objection bucket values match existing OBJECTION_BUCKETS", () => {
    const objEntries = HOTKEY_CONFIG["CLOSE"];
    const values = objEntries.map((e) => e.value);
    assert.ok(values.includes("timing"));
    assert.ok(values.includes("interest"));
    assert.ok(values.includes("info"));
    assert.ok(values.includes("authority"));
  });
});

describe("GLOBAL_HOTKEYS", () => {
  it("has entries for all navigation keys", () => {
    const keys = GLOBAL_HOTKEYS.map((g) => g.key);
    assert.ok(keys.includes("→"));
    assert.ok(keys.includes("←"));
    assert.ok(keys.includes("F9"));
    assert.ok(keys.includes("F10"));
    assert.ok(keys.includes("Space"));
    assert.ok(keys.includes("Shift+F1"));
    assert.ok(keys.includes("?"));
  });

  it("each entry has key, label, and description", () => {
    for (const entry of GLOBAL_HOTKEYS) {
      assert.ok(entry.key, "Missing key");
      assert.ok(entry.label, "Missing label");
      assert.ok(entry.description, "Missing description");
    }
  });
});

describe("KEYPRESS_EVENT_FIELDS", () => {
  it("includes all required telemetry fields", () => {
    assert.ok(KEYPRESS_EVENT_FIELDS.includes("ts"));
    assert.ok(KEYPRESS_EVENT_FIELDS.includes("stage"));
    assert.ok(KEYPRESS_EVENT_FIELDS.includes("key"));
    assert.ok(KEYPRESS_EVENT_FIELDS.includes("action"));
    assert.ok(KEYPRESS_EVENT_FIELDS.includes("value"));
    assert.ok(KEYPRESS_EVENT_FIELDS.includes("isOverride"));
    assert.ok(KEYPRESS_EVENT_FIELDS.includes("source"));
  });
});

describe("blocked stages in HOTKEY_CONFIG", () => {
  it("PRICING, MINI_PITCH, WRONG_PERSON, PERMISSION_MOMENT have empty arrays", () => {
    for (const stage of ["PRICING", "MINI_PITCH", "WRONG_PERSON", "PERMISSION_MOMENT"]) {
      assert.deepStrictEqual(HOTKEY_CONFIG[stage], []);
    }
  });
});

describe("BRIDGE_STAGES", () => {
  it("contains BRIDGE and OPENER", () => {
    assert.strictEqual(BRIDGE_STAGES.length, 2);
    assert.ok(BRIDGE_STAGES.includes("BRIDGE"));
    assert.ok(BRIDGE_STAGES.includes("OPENER"));
  });
});
