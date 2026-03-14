import { dispatchHarnessRequest } from "../../client.js";
import { validateGrowthLifecyclePayload, type GrowthLifecyclePayload } from "../../events/schemas.js";
import { inngest } from "../../inngest.js";

export async function handleLifecycleTask(payload: GrowthLifecyclePayload) {
  const errors = validateGrowthLifecyclePayload(payload);
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
      path: "/growth/handle-lifecycle",
      method: "POST",
    },
    payload as unknown as Record<string, unknown>,
  );
}

export const handleLifecycle = inngest.createFunction(
  { id: "growth-handle-lifecycle" },
  { event: "growth/lifecycle.transitioned" },
  async ({ event, step }: any) => {
    return step.run("dispatch-growth-lifecycle", async () => handleLifecycleTask(event.data as GrowthLifecyclePayload));
  },
);
