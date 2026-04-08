// dialer/hud/__tests__/replay-timeline.test.js
// Tests for generateReplayTimeline in session.js
// Uses Node.js built-in test runner: node --test

import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import {
  resetAuditTrail,
  logDecision,
  generateReplayTimeline,
} from "../session.js";

describe("generateReplayTimeline", () => {
  beforeEach(() => {
    resetAuditTrail();
  });

  it("returns empty array when no events logged", () => {
    const timeline = generateReplayTimeline();
    assert.deepStrictEqual(timeline, []);
  });

  it("captures keypress events with relative timing", () => {
    const t0 = Date.now();
    // Simulate a KEYPRESS_LOG entry
    logDecision(
      { type: "KEYPRESS_LOG", stage: "BRIDGE", key: "1", action: "MANUAL_SET_BRIDGE_ANGLE", value: "missed_calls", isOverride: false, source: "manual" },
      { stage: "BRIDGE", now: null },
      { stage: "BRIDGE", now: null }
    );

    const timeline = generateReplayTimeline();
    assert.strictEqual(timeline.length, 1);
    assert.strictEqual(timeline[0].type, "keypress");
    assert.strictEqual(timeline[0].key, "1");
    assert.strictEqual(timeline[0].action, "MANUAL_SET_BRIDGE_ANGLE");
    assert.strictEqual(timeline[0].value, "missed_calls");
    assert.strictEqual(timeline[0].isOverride, false);
    assert.ok(timeline[0].offsetMs >= 0);
  });

  it("captures stage changes from audit trail", () => {
    logDecision(
      { type: "MANUAL_SET_STAGE" },
      { stage: "OPENER", now: null },
      { stage: "BRIDGE", now: null }
    );

    const timeline = generateReplayTimeline();
    assert.strictEqual(timeline.length, 1);
    assert.strictEqual(timeline[0].type, "stage_change");
    assert.strictEqual(timeline[0].from, "OPENER");
    assert.strictEqual(timeline[0].to, "BRIDGE");
    assert.strictEqual(timeline[0].source, "manual");
  });

  it("marks AI-driven stage changes as source ai", () => {
    logDecision(
      { type: "CLASSIFY_RESULT" },
      { stage: "BRIDGE", now: null },
      { stage: "QUALIFIER", now: null }
    );

    const timeline = generateReplayTimeline();
    assert.strictEqual(timeline.length, 1);
    assert.strictEqual(timeline[0].source, "ai");
  });

  it("sorts mixed events by offsetMs", () => {
    // Log two events in sequence
    logDecision(
      { type: "KEYPRESS_LOG", stage: "OPENER", key: "1", action: "MANUAL_SET_OBJECTION", value: "timing", isOverride: false },
      { stage: "OPENER", now: null },
      { stage: "OPENER", now: null }
    );
    logDecision(
      { type: "MANUAL_SET_STAGE" },
      { stage: "OPENER", now: null },
      { stage: "BRIDGE", now: null }
    );

    const timeline = generateReplayTimeline();
    assert.strictEqual(timeline.length, 2);
    assert.ok(timeline[0].offsetMs <= timeline[1].offsetMs);
  });

  it("filters out same-stage transitions (no actual change)", () => {
    logDecision(
      { type: "TRANSCRIPT_FINAL" },
      { stage: "BRIDGE", now: null },
      { stage: "BRIDGE", now: null }
    );

    const timeline = generateReplayTimeline();
    assert.strictEqual(timeline.length, 0);
  });

  it("marks override keypresses correctly", () => {
    logDecision(
      { type: "KEYPRESS_LOG", stage: "CLOSE", key: "Alt+1", action: "MANUAL_SET_BRIDGE_ANGLE", value: "missed_calls", isOverride: true, source: "manual" },
      { stage: "CLOSE", now: null },
      { stage: "CLOSE", now: null }
    );

    const timeline = generateReplayTimeline();
    assert.strictEqual(timeline.length, 1);
    assert.strictEqual(timeline[0].isOverride, true);
    assert.strictEqual(timeline[0].key, "Alt+1");
  });
});
