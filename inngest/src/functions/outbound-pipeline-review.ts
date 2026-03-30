import { inngest } from "../inngest.js";
import { postToOutboundFeed } from "./outbound-projector.js";

type PipelineReviewResponse = {
  date?: string;
  calling_day?: boolean;
  zero_dials_alert?: boolean;
  scoreboard?: { daily_dials?: number };
  warm_leads_missing_next_step?: Array<{ business_name?: string; stage?: string; metro?: string }>;
  sections?: {
    engaged_with_ai_followup?: string[];
    recommended_actions?: string[];
  };
};

export async function runOutboundPipelineReview(step: any): Promise<PipelineReviewResponse> {
  const baseUrl = process.env.HARNESS_BASE_URL;
  if (!baseUrl) {
    return { date: new Date().toISOString().slice(0, 10), zero_dials_alert: false };
  }

  const payload = await step.run("fetch-pipeline-review", async () => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const secret = process.env.HARNESS_EVENT_SECRET;
    if (secret) headers.Authorization = `Bearer ${secret}`;

    const response = await fetch(`${baseUrl}/outbound/pipeline-review`, {
      headers,
      signal: AbortSignal.timeout(30000),
    });
    if (!response.ok) {
      throw new Error(`Pipeline review fetch failed: ${response.status}`);
    }
    return response.json() as Promise<PipelineReviewResponse>;
  });

  await step.run("post-pipeline-review", async () => {
    const warmLeads = payload.warm_leads_missing_next_step || [];
    const recommended = payload.sections?.recommended_actions || [];

    const lines: string[] = [];
    lines.push(`Date: ${payload.date || new Date().toISOString().slice(0, 10)}`);

    if (warmLeads.length > 0) {
      lines.push("");
      lines.push(`Warm leads without next step (${warmLeads.length}):`);
      // Truncate to 15 leads to stay within Discord embed limits
      const shown = warmLeads.slice(0, 15);
      for (const lead of shown) {
        lines.push(`- ${lead.business_name || "Unknown"} (${lead.stage || "unknown"}, ${lead.metro || "n/a"})`);
      }
      if (warmLeads.length > 15) {
        lines.push(`... and ${warmLeads.length - 15} more`);
      }
    } else {
      lines.push("");
      lines.push("Warm leads all have next steps assigned.");
    }

    if (recommended.length > 0) {
      lines.push("");
      lines.push("Recommended actions:");
      for (const action of recommended) {
        lines.push(`- ${action}`);
      }
    }

    await postToOutboundFeed({
      title: "Pipeline Review",
      description: lines.join("\n"),
      color: 0x3b82f6,
      timestamp: new Date().toISOString(),
      fields: [
        {
          name: "Today Dials",
          value: String(payload.scoreboard?.daily_dials || 0),
          inline: true,
        },
        {
          name: "Warm Missing Next Step",
          value: String(warmLeads.length),
          inline: true,
        },
      ],
    });

    if (payload.calling_day && payload.zero_dials_alert) {
      await postToOutboundFeed({
        title: "Zero Dials Alert",
        description: "Calling day is active and no dials are logged yet. Start Sprint 1 now.",
        color: 0xef4444,
        timestamp: new Date().toISOString(),
      });
    }
  });

  return payload;
}

export const outboundPipelineReview = inngest.createFunction(
  {
    id: "outbound-pipeline-review",
    name: "Outbound: Pipeline Review",
  },
  { cron: "30 11 * * *", timezone: "America/New_York" },
  async ({ step }: any) => runOutboundPipelineReview(step),
);
