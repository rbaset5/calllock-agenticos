import { inngest } from "../inngest.js";
import { postToOutboundFeed } from "./outbound-projector.js";

/**
 * Follow-Up Guardian: fires at 6 AM ET daily (before calling starts).
 * Calls harness POST /outbound/lifecycle-run to execute lifecycle rules:
 * - Requeue overdue callbacks (3+ days)
 * - Auto-disqualify 3-strike no-answers (warm-lead protected)
 * - Requeue voicemail follow-ups (3+ calendar days)
 * - Alert on cooling interested leads (5+ days, no demo)
 * - Disqualify wrong numbers
 *
 * Concurrency limited to 1 to prevent overlapping runs.
 */
export const outboundFollowupGuardian = inngest.createFunction(
  {
    id: "outbound-followup-guardian",
    name: "Outbound: Follow-Up Guardian",
    concurrency: { limit: 1 },
  },
  { cron: "0 6 * * *", timezone: "America/New_York" },
  async ({ step }: any) => {
    const baseUrl = process.env.HARNESS_BASE_URL;
    if (!baseUrl) {
      return { skipped: true, reason: "HARNESS_BASE_URL not configured" };
    }

    const result = await step.run("run-lifecycle-sweep", async () => {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      const secret = process.env.HARNESS_EVENT_SECRET;
      if (secret) headers.Authorization = `Bearer ${secret}`;

      const response = await fetch(`${baseUrl}/outbound/lifecycle-run`, {
        method: "POST",
        headers,
        signal: AbortSignal.timeout(30000),
      });
      if (!response.ok) {
        throw new Error(`Lifecycle sweep failed: ${response.status}`);
      }
      return response.json();
    });

    // Post summary to Discord if any actions were taken
    if (result.total_actions > 0 || (result.errors && result.errors.length > 0)) {
      await step.run("post-guardian-summary", async () => {
        const lines: string[] = [];

        if (result.overdue_requeued > 0) {
          lines.push(`Requeued **${result.overdue_requeued}** overdue callback(s)`);
        }
        if (result.voicemail_requeued > 0) {
          lines.push(`Requeued **${result.voicemail_requeued}** voicemail follow-up(s)`);
        }
        if (result.strikes_disqualified > 0) {
          lines.push(`Auto-disqualified **${result.strikes_disqualified}** unreachable prospect(s)`);
        }
        if (result.wrong_number_disqualified > 0) {
          lines.push(`Disqualified **${result.wrong_number_disqualified}** wrong number(s)`);
        }

        const cooling = result.cooling_alerts || [];
        if (cooling.length > 0) {
          lines.push("");
          lines.push("**Cooling Leads (interested but stalling):**");
          for (const lead of cooling) {
            lines.push(`  ${lead.business_name} (${lead.metro}) — ${lead.days_since_interested}d since interested`);
          }
        }

        if (result.errors && result.errors.length > 0) {
          lines.push("");
          lines.push(`**${result.errors.length} error(s):** ${result.errors[0]}`);
        }

        const color = result.errors && result.errors.length > 0 ? 0xeab308 : 0x22c55e; // yellow if errors, green if clean

        await postToOutboundFeed({
          title: "Follow-Up Guardian Sweep",
          description: lines.join("\n") || "No actions needed. Pipeline is clean.",
          color,
          timestamp: new Date().toISOString(),
          fields: [
            { name: "Total Actions", value: String(result.total_actions || 0), inline: true },
            { name: "Errors", value: String(result.errors?.length || 0), inline: true },
          ],
        });
      });
    }

    return result;
  },
);
