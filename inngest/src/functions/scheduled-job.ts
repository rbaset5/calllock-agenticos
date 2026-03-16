import { inngest } from "../inngest.js";

export const scheduledJob = inngest.createFunction(
  { id: "scheduled-job" },
  { cron: "*/15 * * * *" },
  async ({ step }: any) => {
    return step.run("scheduled-job-tick", async () => ({ ok: true }));
  },
);
