import { inngest } from "../inngest.js";

export const evaluateAlerts = inngest.createFunction(
  { id: "evaluate-alerts" },
  { cron: "*/15 * * * *" },
  async ({ step }: any) => {
    const baseUrl = process.env.HARNESS_BASE_URL;
    if (!baseUrl) {
      throw new Error("HARNESS_BASE_URL is required");
    }
    const evaluated = await step.run("evaluate-alerts", async () => {
      const response = await fetch(`${baseUrl}/alerts/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ window_minutes: 15 }),
      });
      if (!response.ok) {
        throw new Error(`Alert evaluation failed with status ${response.status}`);
      }
      return response.json();
    });
    const escalated = await step.run("escalate-stale-alerts", async () => {
      const response = await fetch(`${baseUrl}/alerts/escalate-stale`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        throw new Error(`Alert escalation failed with status ${response.status}`);
      }
      return response.json();
    });
    const resolved = await step.run("resolve-recovered-alerts", async () => {
      const response = await fetch(`${baseUrl}/alerts/resolve-recovered`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        throw new Error(`Alert recovery failed with status ${response.status}`);
      }
      return response.json();
    });
    return { evaluated, escalated, resolved };
  },
);
