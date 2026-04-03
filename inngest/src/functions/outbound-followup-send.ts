import { inngest } from "../inngest.js";
import {
  OUTBOUND_EXTRACTION_COMPLETE,
  type OutboundExtractionCompletePayload,
  validateOutboundExtractionCompletePayload,
} from "../events/outbound-schemas.js";
import { postToOutboundFeed } from "./outbound-projector.js";

/**
 * Outbound Follow-Up Send: triggered by extraction-complete event.
 * Calls harness POST /outbound/followup-send to generate and send
 * a personalized iMessage follow-up via the imsg CLI.
 *
 * Concurrency limited to 1 to prevent race conditions on the imsg
 * subprocess (Messages.app can only handle one send at a time).
 */
export const outboundFollowupSend = inngest.createFunction(
  {
    id: "outbound-followup-send",
    name: "Outbound: Follow-Up iMessage Send",
    concurrency: { limit: 1 },
    retries: 2,
  },
  { event: OUTBOUND_EXTRACTION_COMPLETE },
  async ({ event, step }: any) => {
    const payload = event.data as OutboundExtractionCompletePayload;
    const errors = validateOutboundExtractionCompletePayload(payload);
    if (errors.length > 0) {
      return { skipped: true, reason: `invalid payload: ${errors.join(", ")}` };
    }

    const baseUrl = process.env.HARNESS_BASE_URL;
    if (!baseUrl) {
      return { skipped: true, reason: "HARNESS_BASE_URL not configured" };
    }

    const result = await step.run("send-followup-text", async () => {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      const secret = process.env.HARNESS_EVENT_SECRET;
      if (secret) headers.Authorization = `Bearer ${secret}`;

      const response = await fetch(`${baseUrl}/outbound/followup-send`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          prospect_id: payload.prospect_id,
          outcome: event.data.outcome || "unknown",
          extraction_data: payload.extraction,
          twilio_call_sid: payload.twilio_call_sid,
        }),
        signal: AbortSignal.timeout(60000),
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`Follow-up send failed: ${response.status} ${body}`);
      }
      return response.json();
    });

    // Post Discord alert on failure
    if (result && !result.sent && !result.skipped) {
      await step.run("alert-followup-failure", async () => {
        await postToOutboundFeed({
          title: "Follow-Up Send Failed",
          description: `**${payload.business_name}** — ${result.reason || "unknown error"}`,
          color: 0xef4444,
          timestamp: new Date().toISOString(),
          fields: [
            { name: "Prospect", value: payload.prospect_id, inline: true },
            { name: "Outcome", value: event.data.outcome || "unknown", inline: true },
          ],
        });
      });
    }

    return result;
  },
);
