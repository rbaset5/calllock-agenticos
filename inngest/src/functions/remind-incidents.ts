import { inngest } from "../inngest.js";

export const remindIncidents = inngest.createFunction(
  { id: "remind-incidents" },
  { cron: "*/15 * * * *" },
  async ({ step }: any) => {
    const baseUrl = process.env.HARNESS_BASE_URL;
    if (!baseUrl) {
      throw new Error("HARNESS_BASE_URL is required");
    }
    return step.run("remind-incidents", async () => {
      const response = await fetch(`${baseUrl}/incidents/remind-stale`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        throw new Error(`Incident reminders failed with status ${response.status}`);
      }
      return response.json();
    });
  },
);
