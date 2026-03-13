export interface ProcessCallPayload {
  call_id: string;
  tenant_id: string;
  transcript?: string;
  problem_description?: string;
  worker_id?: string;
  call_source?: "retell" | "manual" | "test";
  received_at?: string;
  call_metadata?: Record<string, unknown>;
}

export interface JobDispatchPayload {
  job_id: string;
  tenant_id: string;
  origin_run_id: string;
  job_type: string;
  payload?: Record<string, unknown>;
}

export interface JobCompletePayload {
  job_id: string;
  tenant_id: string;
  status: "completed" | "failed" | "cancelled" | "superseded";
  result?: Record<string, unknown>;
}

export function validateProcessCallPayload(payload: ProcessCallPayload): string[] {
  const errors: string[] = [];
  if (!payload.call_id) errors.push("call_id is required");
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (!payload.transcript && !payload.problem_description) {
    errors.push("transcript or problem_description is required");
  }
  if (payload.call_source && !["retell", "manual", "test"].includes(payload.call_source)) {
    errors.push("call_source is invalid");
  }
  return errors;
}

export function validateJobDispatchPayload(payload: JobDispatchPayload): string[] {
  const errors: string[] = [];
  if (!payload.job_id) errors.push("job_id is required");
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (!payload.job_type) errors.push("job_type is required");
  return errors;
}

export function validateJobCompletePayload(payload: JobCompletePayload): string[] {
  const errors: string[] = [];
  if (!payload.job_id) errors.push("job_id is required");
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (!payload.status) errors.push("status is required");
  if (payload.status && !["completed", "failed", "cancelled", "superseded"].includes(payload.status)) {
    errors.push("status is invalid");
  }
  return errors;
}
