import { dispatchHarnessRequest } from "../../client.js";
import { validateGrowthTouchpointPayload, type GrowthTouchpointPayload } from "../../events/schemas.js";
import { inngest } from "../../inngest.js";

export async function handleTouchpointTask(payload: GrowthTouchpointPayload) {
  const errors = validateGrowthTouchpointPayload(payload);
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
      path: "/growth/handle-touchpoint",
      method: "POST",
    },
    payload as unknown as Record<string, unknown>,
  );
}

export const handleTouchpoint = inngest.createFunction(
  { id: "growth-handle-touchpoint" },
  { event: "growth/touchpoint.logged" },
  async ({ event, step }: any) => {
    return step.run("dispatch-growth-touchpoint", async () => handleTouchpointTask(event.data as GrowthTouchpointPayload));
  },
);
