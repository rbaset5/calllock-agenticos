import { buildHarnessEvent, dispatchHarnessEvent } from "../client.js";
import { validateProcessCallPayload, type ProcessCallPayload } from "../events/schemas.js";
import { inngest } from "../inngest.js";

export async function processCallTask(payload: ProcessCallPayload) {
  const errors = validateProcessCallPayload(payload);
  if (errors.length > 0) {
    throw new Error(errors.join(", "));
  }
  const baseUrl = process.env.HARNESS_BASE_URL;
  if (!baseUrl) {
    throw new Error("HARNESS_BASE_URL is required");
  }
  return dispatchHarnessEvent(
    {
      baseUrl,
      eventSecret: process.env.HARNESS_EVENT_SECRET,
    },
    buildHarnessEvent(payload),
  );
}

export const processCall = inngest.createFunction(
  { id: "process-call" },
  { event: "harness/process-call" },
  async ({ event, step }) => {
    return step.run("dispatch-harness-event", async () => processCallTask(event.data as ProcessCallPayload));
  },
);
