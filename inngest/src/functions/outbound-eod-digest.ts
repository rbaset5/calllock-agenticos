import { inngest } from "../inngest.js";
import { postToOutboundFeed } from "./outbound-projector.js";

/**
 * EOD Digest: fires at 7 PM ET daily.
 * Calls harness GET /outbound/digest to get today's call stats,
 * then posts a summary to Discord #outbound-calls.
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

    const digest = await step.run("fetch-digest", async () => {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      const secret = process.env.HARNESS_EVENT_SECRET;
      if (secret) headers.Authorization = `Bearer ${secret}`;

      const response = await fetch(`${baseUrl}/outbound/digest`, {
        headers,
        signal: AbortSignal.timeout(30000),
      });
      if (!response.ok) {
        throw new Error(`Digest fetch failed: ${response.status}`);
      }
      return response.json();
    });

    const stats = digest.stats || {};
    const totalCalls = Number(stats.total_calls || 0);

    await step.run("post-eod-digest", async () => {
      if (totalCalls === 0) {
        await postToOutboundFeed({
          title: "EOD Digest",
          description: "No outbound calls logged today.",
          color: 0x6b7280, // gray
          timestamp: new Date().toISOString(),
        });
        return { posted: true, total_calls: 0 };
      }

      const answered = Number(stats.answered || 0);
      const interested = Number(stats.interested || 0);
      const callbacks = Number(stats.callbacks || 0);
      const voicemails = Number(stats.voicemails || 0);
      const noAnswers = Number(stats.no_answers || 0);
      const demos = Number(stats.demos_scheduled || 0);
      const connectRate = totalCalls > 0 ? Math.round((answered / totalCalls) * 100) : 0;
      const interestRate = answered > 0 ? Math.round((interested / answered) * 100) : 0;

      const lines = [
        `**${totalCalls} calls** today`,
        `Connect rate: **${connectRate}%** (${answered}/${totalCalls})`,
        interested > 0 ? `Interest rate: **${interestRate}%** (${interested}/${answered})` : "",
        "",
        `Interested: ${interested} | Callbacks: ${callbacks} | Demos: ${demos}`,
        `Voicemails: ${voicemails} | No Answer: ${noAnswers}`,
      ].filter(Boolean);

      await postToOutboundFeed({
        title: "EOD Digest",
        description: lines.join("\n"),
        color: interested > 0 ? 0x22c55e : 0x3b82f6, // green if any interest, blue otherwise
        timestamp: new Date().toISOString(),
        fields: [
          { name: "Calls", value: String(totalCalls), inline: true },
          { name: "Connects", value: `${connectRate}%`, inline: true },
          { name: "Interest", value: `${interestRate}%`, inline: true },
          { name: "Demos", value: String(demos), inline: true },
        ],
      });

      return { posted: true, total_calls: totalCalls };
    });

    return { date: digest.date, total_calls: totalCalls };
  },
);
