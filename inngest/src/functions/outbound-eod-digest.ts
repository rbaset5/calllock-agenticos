import { inngest } from "../inngest.js";
import { postToOutboundFeed } from "./outbound-projector.js";

function blockAnalysis(heatMap: Record<string, Record<string, { dials?: number; connects?: number; rate?: number }>> | undefined): string {
  if (!heatMap) return "No block-level data yet.";
  let best = { label: "", rate: -1, dials: 0 };
  for (const [metro, slots] of Object.entries(heatMap)) {
    for (const [slot, data] of Object.entries(slots || {})) {
      const dials = Number(data?.dials || 0);
      const rate = Number(data?.rate || 0);
      if (rate > best.rate || (rate === best.rate && dials > best.dials)) {
        best = { label: `${metro} ${slot}`, rate, dials };
      }
    }
  }
  if (best.rate < 0) return "No block-level data yet.";
  return `Best slot: ${best.label} at ${(best.rate * 100).toFixed(1)}% connect (${best.dials} dials)`;
}

/**
 * EOD Digest: fires at 7 PM ET daily.
 * Includes stats, shutdown log prompts, streak, block analysis, tactical recommendations.
 */
export const outboundEodDigest = inngest.createFunction(
  {
    id: "outbound-eod-digest",
    name: "Outbound: End-of-Day Digest",
  },
  { cron: "0 19 * * *", timezone: "America/New_York" },
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

    // Sequential step.run calls for Inngest replay safety (no Promise.all)
    const digest = await step.run("fetch-digest", async () => {
      const response = await fetch(`${baseUrl}/outbound/digest`, {
        headers,
        signal: AbortSignal.timeout(30000),
      });
      if (!response.ok) {
        throw new Error(`Digest fetch failed: ${response.status}`);
      }
      return response.json();
    });
    const plan = await step.run("fetch-daily-plan", async () => {
      const response = await fetch(`${baseUrl}/outbound/daily-plan`, {
        headers,
        signal: AbortSignal.timeout(30000),
      });
      if (!response.ok) return {};
      return response.json();
    });
    const scoreboard = await step.run("fetch-scoreboard", async () => {
      const response = await fetch(`${baseUrl}/outbound/scoreboard?include_tactical=true`, {
        headers,
        signal: AbortSignal.timeout(30000),
      });
      if (!response.ok) return {};
      return response.json();
    });

    const stats = digest.stats || {};
    const totalCalls = Number(stats.total_calls || 0);

    await step.run("post-eod-digest", async () => {
      const answered = Number(stats.answered || 0);
      const interested = Number(stats.interested || 0);
      const callbacks = Number(stats.callbacks || 0);
      const voicemails = Number(stats.voicemails || 0);
      const noAnswers = Number(stats.no_answers || 0);
      const demos = Number(stats.demos_scheduled || 0);
      const connectRate = totalCalls > 0 ? Math.round((answered / totalCalls) * 100) : 0;
      const interestRate = answered > 0 ? Math.round((interested / answered) * 100) : 0;

      const lines: string[] = [];
      lines.push(`Calls: ${totalCalls}`);
      lines.push(`Connect rate: ${connectRate}% (${answered}/${totalCalls})`);
      lines.push(`Interest rate: ${interestRate}% (${interested}/${Math.max(answered, 1)})`);
      lines.push(`Interested: ${interested} | Callbacks: ${callbacks} | Demos: ${demos}`);
      lines.push(`Voicemails: ${voicemails} | No Answer: ${noAnswers}`);

      const streak = Number(scoreboard?.streak?.current_streak || 0);
      lines.push("");
      lines.push(`Streak: ${streak} calling day(s)`);
      lines.push(blockAnalysis(scoreboard?.heat_map));

      const shutdownFields: string[] = Array.isArray(plan?.shutdown_fields) ? plan.shutdown_fields : [];
      if (shutdownFields.length > 0) {
        lines.push("");
        lines.push("Shutdown log prompts:");
        for (const field of shutdownFields) {
          lines.push(`- ${field}`);
        }
      }

      const tactical: Array<{ recommendation?: string; data_point?: string }> = Array.isArray(scoreboard?.tactical_recommendations)
        ? scoreboard.tactical_recommendations
        : [];
      if (tactical.length > 0) {
        lines.push("");
        lines.push("Tactical recommendations:");
        for (const rec of tactical.slice(0, 3)) {
          lines.push(`- ${rec.recommendation || "Recommendation"} (${rec.data_point || ""})`);
        }
      }

      const week = Number(plan?.week || 0);
      const phase = Number(plan?.phase || 0);
      // Phase transitions: phase 1 ends after week 2, phase 2 ends after week 4
      // Alert on Friday (weekday 5) of the last week in the current phase
      const isFriday = new Date().getDay() === 5;
      const isPhaseEnd = (phase === 1 && week === 2) || (phase === 2 && week === 4);
      if (isFriday && isPhaseEnd && phase < 3) {
        lines.push("");
        lines.push(`Phase transition: Phase ${phase + 1} starts next week. Every live conversation ends with the next step.`);
      }

      await postToOutboundFeed({
        title: "EOD Digest",
        description: lines.join("\n"),
        color: interested > 0 ? 0x22c55e : 0x3b82f6,
        timestamp: new Date().toISOString(),
        fields: [
          { name: "Calls", value: String(totalCalls), inline: true },
          { name: "Connects", value: `${connectRate}%`, inline: true },
          { name: "Interest", value: `${interestRate}%`, inline: true },
          { name: "Demos", value: String(demos), inline: true },
        ],
      });
    });

    return { date: digest.date, total_calls: totalCalls };
  },
);
