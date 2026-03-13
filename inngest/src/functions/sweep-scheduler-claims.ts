import { inngest } from "../inngest.js";

export const sweepSchedulerClaims = inngest.createFunction(
  { id: "sweep-scheduler-claims" },
  { cron: "*/5 * * * *" },
  async ({ step }: any) => {
    const baseUrl = process.env.HARNESS_BASE_URL;
    if (!baseUrl) {
      throw new Error("HARNESS_BASE_URL is required");
    }
    return step.run("sweep-scheduler-claims", async () => {
      const response = await fetch(`${baseUrl}/schedules/sweep`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dry_run: false }),
      });
      if (!response.ok) {
        throw new Error(`Scheduler sweep failed with status ${response.status}`);
      }
      return response.json();
    });
  },
);
