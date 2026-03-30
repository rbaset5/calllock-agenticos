import { inngest } from "../inngest.js";
import { postToOutboundFeed } from "./outbound-projector.js";

/**
 * Morning Planner: fires at 7 AM ET daily.
 * Calls harness GET /outbound/daily-plan to build a timezone-aware sprint plan,
 * then posts it to Discord #outbound-calls.
 */
export const outboundMorningPlanner = inngest.createFunction(
  {
    id: "outbound-morning-planner",
    name: "Outbound: Morning Sprint Planner",
  },
  { cron: "0 7 * * *", timezone: "America/New_York" },
  async ({ step }: any) => {
    const baseUrl = process.env.HARNESS_BASE_URL;
    if (!baseUrl) {
      return { skipped: true, reason: "HARNESS_BASE_URL not configured" };
    }

    const plan = await step.run("fetch-daily-plan", async () => {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      const secret = process.env.HARNESS_EVENT_SECRET;
      if (secret) headers.Authorization = `Bearer ${secret}`;

      const response = await fetch(`${baseUrl}/outbound/daily-plan`, {
        headers,
        signal: AbortSignal.timeout(30000),
      });
      if (!response.ok) {
        throw new Error(`Daily plan fetch failed: ${response.status}`);
      }
      return response.json();
    });

    if (plan.message) {
      // Rest day or pre-sprint
      await step.run("post-rest-day", async () => {
        await postToOutboundFeed({
          title: `Sprint Plan — ${plan.date}`,
          description: plan.message,
          color: 0x6b7280, // gray
          timestamp: new Date().toISOString(),
        });
      });
      return { date: plan.date, week: plan.week, message: plan.message };
    }

    await step.run("post-sprint-plan", async () => {
      const blocks = plan.blocks || [];
      const lines: string[] = [];

      if (plan.total_callbacks > 0) {
        lines.push(`**${plan.total_callbacks} callbacks due** (priority)`);
      }

      for (const block of blocks) {
        lines.push("");
        lines.push(`**${block.block} Block** (${block.start_et} ET)`);
        for (const sprint of block.sprints || []) {
          const metro = sprint.metro.toUpperCase();
          const count = sprint.lead_count || 0;
          const note = sprint.note ? ` — ${sprint.note}` : "";
          lines.push(`  Sprint ${sprint.sprint_number}: ${metro} (${count} leads)${note}`);
        }
      }

      const totalSprints = plan.total_sprints || 0;
      const dials = totalSprints * (plan.dials_per_sprint || 10);

      await postToOutboundFeed({
        title: `Sprint Plan — Week ${plan.week}, ${plan.day_of_week} ${plan.date}`,
        description: lines.join("\n"),
        color: 0x3b82f6, // blue
        timestamp: new Date().toISOString(),
        fields: [
          { name: "Sprints", value: String(totalSprints), inline: true },
          { name: "Target Dials", value: String(dials), inline: true },
          { name: "Callbacks", value: String(plan.total_callbacks), inline: true },
          { name: "Fresh Leads", value: String(plan.total_fresh), inline: true },
        ],
      });
    });

    return {
      date: plan.date,
      week: plan.week,
      total_sprints: plan.total_sprints,
      total_callbacks: plan.total_callbacks,
      total_fresh: plan.total_fresh,
    };
  },
);
