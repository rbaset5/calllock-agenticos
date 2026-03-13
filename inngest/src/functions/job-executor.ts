import { buildJobCompleteEvent, dispatchHarnessEvent } from "../client.js";
import { type JobDispatchPayload, validateJobDispatchPayload } from "../events/schemas.js";
import { inngest } from "../inngest.js";

export const jobExecutor = inngest.createFunction(
  { id: "job-executor" },
  { event: "harness/job-dispatch" },
  async ({ event, step }: any) => {
    return step.run("execute-job", async () => {
      const payload = event.data as JobDispatchPayload;
      const errors = validateJobDispatchPayload(payload);
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
        {
          ...buildJobCompleteEvent({
            job_id: payload.job_id,
            tenant_id: payload.tenant_id,
            status: "completed",
            result: {
              executed: true,
              job_type: payload.job_type,
              payload: payload.payload ?? {},
            },
          }),
        },
      );
    });
  },
);
