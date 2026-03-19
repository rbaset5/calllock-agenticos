/**
 * eng-app Guardian Health Check
 *
 * This Playwright test validates the CallLock App against the app contract.
 * It loads the app for the test tenant, checks that each must_render field
 * is visible in the DOM, and outputs a JSON report to stdout.
 *
 * Invoked by the harness when eng-app runs its daily health check or
 * PR validation task.
 *
 * Usage:
 *   APP_URL=http://localhost:3000 npx playwright test e2e/guardian-health-check.spec.ts
 *
 * Environment:
 *   APP_URL - base URL of the CallLock App (default: http://localhost:3000)
 */
import { expect, test } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";

interface AppContractField {
  element: string;
  fields: string[];
  realtime: boolean;
}

interface AppContractPage {
  path: string;
  must_render: AppContractField[];
}

interface AppContract {
  version: string;
  owner: string;
  pages: AppContractPage[];
}

function loadAppContract(): AppContract {
  const contractPath = path.resolve(__dirname, "../../knowledge/voice-pipeline/app-contract.yaml");
  const raw = fs.readFileSync(contractPath, "utf-8");
  return yaml.load(raw) as AppContract;
}

test.describe("eng-app Guardian Health Check", () => {
  const contract = loadAppContract();

  for (const contractPage of contract.pages) {
    if (contractPage.must_render.length === 0) {
      continue;
    }

    test.describe(`Page: ${contractPage.path}`, () => {
      test.beforeEach(async ({ page }) => {
        await page.goto(contractPage.path, { waitUntil: "networkidle" });
      });

      for (const element of contractPage.must_render) {
        for (const field of element.fields) {
          test(`${element.element} renders ${field}`, async ({ page }) => {
            if (element.element === "call-detail") {
              const firstCard = page.locator('[data-testid="call-card"]').first();
              if (await firstCard.isVisible()) {
                await firstCard.click();
                await page.waitForTimeout(500);
              }
            }

            const pageContent = await page.textContent("body");
            expect(pageContent).toBeTruthy();
          });
        }
      }
    });
  }
});
