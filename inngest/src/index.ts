import { inngest } from "./inngest.js";
import { evaluateAlerts } from "./functions/evaluate-alerts.js";
import { growthAdvisorWeekly } from "./functions/growth/growth-advisor-weekly.js";
import { handleLifecycle } from "./functions/growth/handle-lifecycle.js";
import { handleTouchpoint } from "./functions/growth/handle-touchpoint.js";
import { jobExecutor } from "./functions/job-executor.js";
import { processCall } from "./functions/process-call.js";
import { remindIncidents } from "./functions/remind-incidents.js";
import { runEvals } from "./functions/run-evals.js";
import { runRetention } from "./functions/run-retention.js";
import { scheduledJob } from "./functions/scheduled-job.js";
import { sweepSchedulerClaims } from "./functions/sweep-scheduler-claims.js";

export const client = inngest;
export const functions = [
  processCall,
  jobExecutor,
  scheduledJob,
  evaluateAlerts,
  remindIncidents,
  runRetention,
  runEvals,
  sweepSchedulerClaims,
  handleTouchpoint,
  handleLifecycle,
  growthAdvisorWeekly,
];
