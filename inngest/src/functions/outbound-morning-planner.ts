import { inngest } from "../inngest.js";
import { postToOutboundFeed } from "./outbound-projector.js";

function progressBar(current: number, target: number, width = 16): string {
  if (target <= 0) return `[${"-".repeat(width)}] 0%`;
  const ratio = Math.max(0, Math.min(1, current / target));
  const filled = Math.round(ratio * width);
  return `[${"#".repeat(filled)}${"-".repeat(width - filled)}] ${Math.round(ratio * 100)}%`;
}

function heatMapSummary(heatMap: Record<string, Record<string, { dials?: number; connects?: number; rate?: number }>> | undefined): string[] {
  if (!heatMap) return ["No heat map data yet."];
  const points: Array<{ metro: string; slot: string; dials: number; rate: number }> = [];
  for (const [metro, slots] of Object.entries(heatMap)) {
    for (const [slot, data] of Object.entries(slots || {})) {
      points.push({
        metro,
        slot,
        dials: Number(data?.dials || 0),
        rate: Number(data?.rate || 0),
      });
    }
  }
  points.sort((a, b) => b.rate - a.rate || b.dials - a.dials);
  const top = points.slice(0, 3);
  if (top.length === 0) return ["No heat map data yet."];
  return top.map((row) => `${row.metro} ${row.slot}: ${(row.rate * 100).toFixed(1)}% connect (${row.dials} dials)`);
}

function objectionSummary(objections: Array<{ objection?: string; count?: number; example?: string }> | undefined): string[] {
  if (!objections || objections.length === 0) return ["No objection patterns yet."];
  return objections.slice(0, 3).map((item) => {
    const objection = item.objection || "unknown";
    const count = Number(item.count || 0);
    const example = item.example ? ` — "${item.example}"` : "";
    return `${objection}: ${count}${example}`;
  });
}

/**
 * Morning Planner: fires at 7 AM ET daily.
 * Posts two messages:
 *  1) Sprint Plan (schedule + progress + lead sections)
 *  2) Intelligence Briefing (heat map + objections + coaching + streak)
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

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const secret = process.env.HARNESS_EVENT_SECRET;
    if (secret) headers.Authorization = `Bearer ${secret}`;

    const plan = await step.run("fetch-daily-plan", async () => {
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
      await step.run("post-rest-day", async () => {
        await postToOutboundFeed({
          title: `Sprint Plan — ${plan.date}`,
          description: plan.message,
          color: 0x6b7280,
          timestamp: new Date().toISOString(),
        });
      });
      return { date: plan.date, week: plan.week, message: plan.message };
    }

    const scoreboard = await step.run("fetch-scoreboard", async () => {
      const response = await fetch(`${baseUrl}/outbound/scoreboard`, {
        headers,
        signal: AbortSignal.timeout(30000),
      });
      if (!response.ok) {
        return {};
      }
      return response.json();
    });

    await step.run("post-sprint-plan", async () => {
      const blocks = plan.blocks || [];
      const totalSprints = Number(plan.total_sprints || 0);
      const dialsPerSprint = Number(plan.dials_per_sprint || 0);
      const targetDials = totalSprints * dialsPerSprint;

      const weeklyDials = Number(scoreboard.weekly_dials || 0);
      const weeklyTarget = Number(scoreboard.weekly_target || 0);
      const weeklyProgress = progressBar(weeklyDials, weeklyTarget);

      const hotCount = Math.min(Number(plan.total_callbacks || 0), 3);
      const warmCount = Math.max(Number(plan.total_callbacks || 0) - hotCount, 0);
      const volumeCount = Number(plan.total_fresh || 0);

      const lines: string[] = [];
      lines.push(`Weekly progress: ${weeklyProgress} (${weeklyDials}/${weeklyTarget})`);
      lines.push("");
      lines.push("Lead sections:");
      lines.push(`- Hot: ${hotCount}`);
      lines.push(`- Warm: ${warmCount}`);
      lines.push(`- Volume: ${volumeCount}`);

      if (Number(plan.total_callbacks || 0) > 0) {
        lines.push("");
        lines.push(`Callbacks due: ${plan.total_callbacks}`);
      }

      for (const block of blocks) {
        lines.push("");
        lines.push(`${block.block} Block (${block.start_et} ET)`);
        for (const sprint of block.sprints || []) {
          const metro = String(sprint.metro || "").toUpperCase();
          const count = Number(sprint.lead_count || 0);
          const note = sprint.note ? ` — ${sprint.note}` : "";
          lines.push(`  Sprint ${sprint.sprint_number}: ${metro} (${count} leads)${note}`);
        }
      }

      await postToOutboundFeed({
        title: `Sprint Plan — Week ${plan.week}, ${plan.day_of_week} ${plan.date}`,
        description: lines.join("\n"),
        color: 0x3b82f6,
        timestamp: new Date().toISOString(),
        fields: [
          { name: "Sprints", value: String(totalSprints), inline: true },
          { name: "Dials / Sprint", value: String(dialsPerSprint), inline: true },
          { name: "Target Dials", value: String(targetDials), inline: true },
          { name: "Callbacks", value: String(plan.total_callbacks || 0), inline: true },
        ],
      });
    });

    await step.run("post-intelligence-briefing", async () => {
      const streak = Number(scoreboard?.streak?.current_streak || 0);
      const heatMapLines = heatMapSummary(scoreboard?.heat_map);
      const objectionLines = objectionSummary(scoreboard?.objection_summary);

      const lines: string[] = [];
      lines.push(`Coaching note: ${plan.coaching_note || "Stay consistent and protect quality."}`);
      lines.push(`Weekly goal: ${plan.weekly_goal || "Hit the dial target with clean follow-through."}`);
      lines.push(`Streak: ${streak} calling day(s)`);
      lines.push("");
      lines.push("Heat map highlights:");
      for (const row of heatMapLines) lines.push(`- ${row}`);
      lines.push("");
      lines.push("Objection patterns:");
      for (const row of objectionLines) lines.push(`- ${row}`);

      await postToOutboundFeed({
        title: `Intelligence Briefing — ${plan.date}`,
        description: lines.join("\n"),
        color: 0x22c55e,
        timestamp: new Date().toISOString(),
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
