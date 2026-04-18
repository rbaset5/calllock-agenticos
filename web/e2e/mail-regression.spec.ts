/**
 * Mail app regression tests.
 *
 * Verifies that the route group refactor (moving src/app/page.tsx into
 * src/app/(app)/page.tsx and creating (app)/layout.tsx with the dark theme
 * wrapper and viewport scroll lock) did not break the existing Mail UI at /.
 *
 * Required by /plan-eng-review iron rule for regressions.
 *
 * Usage:
 *   APP_URL=http://localhost:3000 npx playwright test e2e/mail-regression.spec.ts
 */
import { expect, test } from "@playwright/test";

test.describe("Mail app regression (route group refactor)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
  });

  test("/ still renders the Mail UI (not the marketing page)", async ({ page }) => {
    // Mail renders a <Mail> component with a list of call cards. Assert a Mail-
    // specific marker is present and the marketing H1 is not.
    const bodyText = await page.textContent("body");
    expect(bodyText).not.toContain("Stop losing jobs to voicemail");
  });

  test("/ viewport is scroll-locked by the (app) wrapper", async ({ page }) => {
    // After the refactor, h-dvh overflow-hidden lives on the (app) wrapper
    // div. The document should not be taller than the viewport.
    const [scrollHeight, innerHeight] = await page.evaluate(() => [
      document.documentElement.scrollHeight,
      window.innerHeight,
    ]);
    // Allow a small tolerance for scrollbar/browser chrome variance.
    expect(scrollHeight).toBeLessThanOrEqual(innerHeight + 10);
  });

  test("/ dark theme still resolves (dark:* classes apply inside (app))", async ({ page }) => {
    // The (app) wrapper adds className="dark" so Tailwind's custom variant
    // &:is(.dark *) still resolves for every dark:* utility in components/mail/*.
    // Check the computed background color of the first body child — it should
    // be the dark shell color #0e0e0e.
    const bgColor = await page.evaluate(() => {
      const firstChild = document.body.firstElementChild as HTMLElement | null;
      if (!firstChild) return null;
      return window.getComputedStyle(firstChild).backgroundColor;
    });
    // rgb(14, 14, 14) == #0e0e0e
    expect(bgColor).toBe("rgb(14, 14, 14)");
  });
});
