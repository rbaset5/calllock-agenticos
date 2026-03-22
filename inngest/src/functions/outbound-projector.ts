import {
  OUTBOUND_BATCH_COMPLETE,
  OUTBOUND_PIPELINE_ERROR,
  OUTBOUND_TEST_COMPLETE,
  type OutboundBatchCompletePayload,
  type OutboundPipelineErrorPayload,
  type OutboundTestBatchCompletePayload,
  validateOutboundBatchCompletePayload,
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
const RED = 0xef4444;

function outboundWebhookUrl(): string {
  return process.env.DISCORD_OUTBOUND_FEED_WEBHOOK_URL || "";
}

export async function postToOutboundFeed(embed: DiscordEmbed): Promise<void> {
  const webhookUrl = outboundWebhookUrl();
  if (!webhookUrl) return;

  await fetch(webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ embeds: [embed] }),
  });
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
