import {
  OUTBOUND_BATCH_COMPLETE,
  OUTBOUND_EXTRACTION_COMPLETE,
  OUTBOUND_PIPELINE_ERROR,
  OUTBOUND_TEST_COMPLETE,
  type OutboundBatchCompletePayload,
  type OutboundExtractionCompletePayload,
  type OutboundPipelineErrorPayload,
  type OutboundTestBatchCompletePayload,
  validateOutboundBatchCompletePayload,
  validateOutboundExtractionCompletePayload,
  validateOutboundPipelineErrorPayload,
  validateOutboundTestBatchCompletePayload,
} from "../events/outbound-schemas.js";
import { inngest } from "../inngest.js";

interface DiscordEmbed {
  title: string;
  description: string;
  color: number;
  timestamp?: string;
  fields?: Array<{ name: string; value: string; inline?: boolean }>;
}

const BLUE = 0x3b82f6;
const GREEN = 0x22c55e;
const RED = 0xef4444;

function outboundWebhookUrl(): string {
  return process.env.DISCORD_OUTBOUND_FEED_WEBHOOK_URL || "";
}

export async function postToOutboundFeed(embed: DiscordEmbed): Promise<void> {
  const webhookUrl = outboundWebhookUrl();
  if (!webhookUrl) {
    console.warn("[outbound-projector] DISCORD_OUTBOUND_FEED_WEBHOOK_URL not set, skipping post");
    return;
  }

  const response = await fetch(webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ embeds: [embed] }),
  });

  if (!response.ok) {
    console.error(`[outbound-projector] Discord webhook failed: ${response.status} ${response.statusText}`);
  }
}

export function buildDiscoveryEmbed(payload: OutboundBatchCompletePayload): DiscordEmbed {
  return {
    title: "Outbound Scout Batch Complete",
    description: "Discovery and scoring batch finished for the internal outbound tenant.",
    color: BLUE,
    timestamp: new Date().toISOString(),
    fields: [
      { name: "Tenant", value: payload.tenant_id, inline: true },
      { name: "Ingested", value: String(payload.ingested), inline: true },
      { name: "Scored", value: String(payload.scored), inline: true },
      { name: "A Leads", value: String(payload.a_leads), inline: true },
      { name: "B Leads", value: String(payload.b_leads), inline: true },
      { name: "Source", value: payload.source_version, inline: true },
    ],
  };
}

export function buildTestResultsEmbed(payload: OutboundTestBatchCompletePayload): DiscordEmbed {
  return {
    title: "Outbound Probe Batch Complete",
    description: "After-hours probe batch finished.",
    color: BLUE,
    timestamp: new Date().toISOString(),
    fields: [
      { name: "Tenant", value: payload.tenant_id, inline: true },
      { name: "Tested", value: String(payload.tested), inline: true },
      { name: "Confirmed Weak", value: String(payload.confirmed_weak), inline: true },
      { name: "Answered", value: String(payload.answered), inline: true },
      { name: "Source", value: payload.source_version, inline: true },
    ],
  };
}

export function buildErrorEmbed(payload: OutboundPipelineErrorPayload): DiscordEmbed {
  return {
    title: "Outbound Pipeline Error",
    description: payload.error_message,
    color: RED,
    timestamp: new Date().toISOString(),
    fields: [
      { name: "Tenant", value: payload.tenant_id, inline: true },
      { name: "Type", value: payload.error_type, inline: true },
      { name: "Source", value: payload.source_version, inline: true },
    ],
  };
}

export const discordOutboundDiscovery = inngest.createFunction(
  { id: "discord-outbound-discovery", name: "Discord: Outbound Discovery" },
  { event: OUTBOUND_BATCH_COMPLETE },
  async ({ event }: { event: { data: OutboundBatchCompletePayload } }) => {
    const errors = validateOutboundBatchCompletePayload(event.data);
    if (errors.length > 0) {
      throw new Error(errors.join(", "));
    }
    await postToOutboundFeed(buildDiscoveryEmbed(event.data));
  },
);

export const discordOutboundTestResults = inngest.createFunction(
  { id: "discord-outbound-test-results", name: "Discord: Outbound Test Results" },
  { event: OUTBOUND_TEST_COMPLETE },
  async ({ event }: { event: { data: OutboundTestBatchCompletePayload } }) => {
    const errors = validateOutboundTestBatchCompletePayload(event.data);
    if (errors.length > 0) {
      throw new Error(errors.join(", "));
    }
    await postToOutboundFeed(buildTestResultsEmbed(event.data));
  },
);

export const discordOutboundError = inngest.createFunction(
  { id: "discord-outbound-error", name: "Discord: Outbound Error" },
  { event: OUTBOUND_PIPELINE_ERROR },
  async ({ event }: { event: { data: OutboundPipelineErrorPayload } }) => {
    const errors = validateOutboundPipelineErrorPayload(event.data);
    if (errors.length > 0) {
      throw new Error(errors.join(", "));
    }
    await postToOutboundFeed(buildErrorEmbed(event.data));
  },
);

export function buildExtractionEmbed(payload: OutboundExtractionCompletePayload): DiscordEmbed {
  const ext = payload.extraction;
  const fields: Array<{ name: string; value: string; inline?: boolean }> = [];
  if (payload.business_name) fields.push({ name: "Business", value: payload.business_name, inline: true });
  if (ext.buying_temperature) fields.push({ name: "Temperature", value: ext.buying_temperature, inline: true });
  if (ext.missed_call_pain) fields.push({ name: "Pain", value: ext.missed_call_pain, inline: true });
  if (ext.objection_type && ext.objection_type !== "none") {
    fields.push({ name: "Objection", value: ext.objection_type, inline: true });
  }
  if (ext.objection_verbatim) {
    fields.push({ name: "Verbatim", value: `"${ext.objection_verbatim}"` });
  }
  if (ext.current_call_handling) fields.push({ name: "Current Handling", value: ext.current_call_handling });
  if (ext.status_quo_details) fields.push({ name: "Status Quo", value: ext.status_quo_details });
  if (ext.follow_up_action && ext.follow_up_action !== "none") {
    fields.push({ name: "Next Step", value: ext.follow_up_action, inline: true });
  }
  if (ext.follow_up_date) fields.push({ name: "Follow-up Date", value: ext.follow_up_date, inline: true });

  return {
    title: "Call Extraction Complete",
    description: `AI analysis finished for ${payload.business_name || payload.twilio_call_sid}`,
    color: GREEN,
    timestamp: new Date().toISOString(),
    fields,
  };
}

export const discordOutboundExtraction = inngest.createFunction(
  { id: "discord-outbound-extraction", name: "Discord: Outbound Extraction" },
  { event: OUTBOUND_EXTRACTION_COMPLETE },
  async ({ event }: { event: { data: OutboundExtractionCompletePayload } }) => {
    const errors = validateOutboundExtractionCompletePayload(event.data);
    if (errors.length > 0) {
      throw new Error(errors.join(", "));
    }
    await postToOutboundFeed(buildExtractionEmbed(event.data));
  },
);
