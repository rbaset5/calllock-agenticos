import { dispatchHarnessRequest } from "../../client.js";
import { validateInboundPollRequestedPayload, type InboundPollRequestedPayload } from "../../events/schemas.js";
import { inngest } from "../../inngest.js";

export async function pollInboundTask(payload: InboundPollRequestedPayload) {
  const errors = validateInboundPollRequestedPayload(payload);
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
      path: "/inbound/poll",
      method: "POST",
    },
    payload as unknown as Record<string, unknown>,
  );
}

export const pollInbound = inngest.createFunction(
  { id: "poll-inbound" },
  { cron: "0 * * * *" },
  async ({ step }: any) => {
    const tenantId = process.env.INBOUND_DEFAULT_TENANT_ID;
    if (!tenantId) {
      return step.run("skip-poll-inbound", async () => ({
        skipped: true,
        reason: "INBOUND_DEFAULT_TENANT_ID not configured",
      }));
    }
    return step.run("dispatch-poll-inbound", async () =>
      pollInboundTask({ tenant_id: tenantId }),
    );
  },
);
