import { inngest } from "./inngest.js";
import { processCall } from "./functions/process-call.js";

export const client = inngest;
export const functions = [processCall];
