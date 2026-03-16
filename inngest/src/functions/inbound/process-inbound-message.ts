import { dispatchHarnessRequest } from "../../client.js";
import { validateInboundMessageReceivedPayload, type InboundMessageReceivedPayload } from "../../events/schemas.js";
import { inngest } from "../../inngest.js";

export async function processInboundMessageTask(payload: InboundMessageReceivedPayload) {
  const errors = validateInboundMessageReceivedPayload(payload);
  if (errors.length > 0) {
    throw new Error(errors.join(", "));
  }
  const baseUrl = process.env.HARNESS_BASE_URL;
  if (!baseUrl) {
    throw new Error("HARNESS_BASE_URL is required");
  }
  return dispatchHarnessRequest(
    {
      baseUrl,
      eventSecret: process.env.HARNESS_EVENT_SECRET,
      path: "/inbound/process",
      method: "POST",
    },
    payload as unknown as Record<string, unknown>,
  );
}

export const processInboundMessage = inngest.createFunction(
  { id: "process-inbound-message" },
  { event: "calllock/inbound.message.received" },
  async ({ event, step }: any) => {
    return step.run("dispatch-process-inbound-message", async () =>
      processInboundMessageTask(event.data as InboundMessageReceivedPayload),
    );
  },
);
