import type { GuardianDispatchPayload } from "../events/guardian-schemas.js";
import { inngest } from "../inngest.js";

function getHarnessConfig() {
  const baseUrl = process.env.HARNESS_BASE_URL;
  if (!baseUrl) {
    throw new Error("HARNESS_BASE_URL is required");
  }

  return {
    baseUrl: baseUrl.replace(/\/$/, ""),
    eventSecret: process.env.HARNESS_EVENT_SECRET,
  };
}

function normalizeChangedFiles(taskContext: Record<string, unknown>): string[] | undefined {
  const changedFiles = taskContext.changed_files;
  if (Array.isArray(changedFiles)) {
    return changedFiles.filter((entry): entry is string => typeof entry === "string" && entry.length > 0);
  }
  if (typeof changedFiles === "string" && changedFiles.length > 0) {
    return changedFiles.split(",").map((entry) => entry.trim()).filter(Boolean);
  }

  const legacyChangedFiles = taskContext.changed_file_paths;
  if (Array.isArray(legacyChangedFiles)) {
    return legacyChangedFiles.filter((entry): entry is string => typeof entry === "string" && entry.length > 0);
  }
  if (typeof legacyChangedFiles === "string" && legacyChangedFiles.length > 0) {
    return legacyChangedFiles.split(",").map((entry) => entry.trim()).filter(Boolean);
  }

  return undefined;
}

function buildGuardianRequest(payload: GuardianDispatchPayload) {
  const { target, task_type, pr_id, pr_url, task_context, origin, tenant_id } = payload;
  const normalizedChangedFiles = normalizeChangedFiles(task_context);
  const callId =
    typeof task_context.call_id === "string" && task_context.call_id.length > 0
      ? task_context.call_id
      : `guardian-${target}-${pr_id ?? "adhoc"}-${Date.now()}`;
  const transcript =
    typeof task_context.transcript === "string" && task_context.transcript.length > 0
      ? task_context.transcript
      : `Guardian dispatch for ${target}: ${task_type}`;
  const problemDescription =
    typeof task_context.problem_description === "string" && task_context.problem_description.length > 0
      ? task_context.problem_description
      : `Guardian dispatch task ${task_type}`;

  return {
    call_id: callId,
    tenant_id,
    worker_id: target,
    call_source: "test",
    transcript,
    problem_description: problemDescription,
    task_context: {
      ...task_context,
      ...(normalizedChangedFiles ? { changed_files: normalizedChangedFiles } : {}),
      task_type,
      pr_id,
      pr_url,
      origin,
    },
  };
}

/**
 * Receives calllock/guardian.dispatch events from eng-product-qa
 * and triggers the harness supervisor for the target agent.
 */
export const guardianDispatch = inngest.createFunction(
  {
    id: "guardian-dispatch",
    name: "Guardian Agent Dispatch",
  },
  { event: "calllock/guardian.dispatch" },
  async ({ event, step }: any) => {
    const payload = event.data as GuardianDispatchPayload;
    const { baseUrl, eventSecret } = getHarnessConfig();
    const timeoutMs = payload.timeout_ms || 300000;

    const result = await step.run(`dispatch-${payload.target}`, async () => {
      const response = await fetch(`${baseUrl}/process-call`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(eventSecret ? { Authorization: `Bearer ${eventSecret}` } : {}),
        },
        body: JSON.stringify(buildGuardianRequest(payload)),
        signal: AbortSignal.timeout(timeoutMs),
      });

      if (!response.ok) {
        throw new Error(`Harness dispatch failed: ${response.status} ${await response.text()}`);
      }

      return response.json();
    });

    await step.run("log-dispatch-result", async () => ({
      target: payload.target,
      task_type: payload.task_type,
      pr_id: payload.pr_id,
      status: result.verification_verdict ?? "unknown",
      run_id: result.run_id,
    }));

    return result;
  },
);
