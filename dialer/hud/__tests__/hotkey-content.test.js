// dialer/hud/__tests__/hotkey-content.test.js
// Positioning invariants for the pure hotkey HUD.
// Grep-based regression lock — reads hotkey.html as a string and asserts
// the post-reframe positioning invariants are present and the old ones absent.
// No dynamic code evaluation. Uses Node built-in test runner: node --test

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const html = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "..", "hotkey.html"),
  "utf8"
);

describe("hotkey.html positioning invariants", () => {
  it("contains no deprecated after-hours-wedge language", () => {
    assert.doesNotMatch(html, /weekend leak/i);
    assert.doesNotMatch(html, /after-hours wedge/i);
    assert.doesNotMatch(html, /Sat calls/);
  });

  it("contains the new patience-filter insight", () => {
    assert.match(html, /patience filter/i);
  });

  it("contains the new $3K–$12K monthly-leak anchor in the $ overlay", () => {
    assert.ok(
      html.includes("$3K") || html.includes("$3,000"),
      "expected $3K or $3,000 anchor"
    );
    assert.ok(
      html.includes("$12K") || html.includes("$12,000"),
      "expected $12K or $12,000 anchor"
    );
  });

  it("math strip uses VMs/day labeling", () => {
    assert.match(html, /VMs\/day/);
  });

  it("computeMonthlyLeak helper defines monthly multiplier constants", () => {
    // Shallow sanity check — verifies the helper exists and references the
    // 20-workday and 0.2 close-rate constants. Numerical correctness
    // (e.g. computeMonthlyLeak(3, 400) === 4800) is verified manually in the
    // browser smoke-test, intentionally NOT by eval'ing the function body.
    assert.match(html, /function\s+computeMonthlyLeak/);
    assert.match(html, /computeMonthlyLeak[\s\S]{0,300}?\b20\b[\s\S]{0,80}?0\.2/);
  });
});
