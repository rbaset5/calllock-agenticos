import { dispatchHarnessRequest } from "../../client.js";
import { validateGrowthAdvisorWeeklyPayload, type GrowthAdvisorWeeklyPayload } from "../../events/schemas.js";
import { inngest } from "../../inngest.js";

export async function growthAdvisorWeeklyTask(payload: GrowthAdvisorWeeklyPayload) {
  const errors = validateGrowthAdvisorWeeklyPayload(payload);
  if (errors.length > 0) {
    throw new Error(errors.join(", "));
  }
  const baseUrl = process.env.HARNESS_BASE_URL;
  if (!baseUrl) {
    throw new Error("HARNESS_BASE_URL is required");
  }
  return dispatchHarnessRequest(
    {
      baseUrl,
      eventSecret: process.env.HARNESS_EVENT_SECRET,
      path: "/growth/growth-advisor/weekly",
      method: "POST",
    },
    payload as unknown as Record<string, unknown>,
  );
}

export const growthAdvisorWeekly = inngest.createFunction(
  { id: "growth-advisor-weekly" },
  { cron: "0 9 * * 1" },
  async ({ step }: any) => {
    const tenantId = process.env.GROWTH_DEFAULT_TENANT_ID;
    if (!tenantId) {
      return step.run("skip-growth-advisor-weekly", async () => ({ skipped: true, reason: "GROWTH_DEFAULT_TENANT_ID not configured" }));
    }
    return step.run("dispatch-growth-advisor-weekly", async () =>
      growthAdvisorWeeklyTask({
        tenant_id: tenantId,
        source_version: process.env.GROWTH_SOURCE_VERSION ?? "growth-advisor-weekly",
      }),
    );
  },
);
