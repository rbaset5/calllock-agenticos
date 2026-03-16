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

export interface GrowthTouchpointPayload {
  touchpoint_id: string;
  tenant_id: string;
  prospect_id: string;
  touchpoint_type: string;
  source_component: string;
  source_version: string;
  channel?: string;
  experiment_id?: string;
  arm_id?: string;
  attribution_token?: string;
  signal_quality_score?: number;
  cost?: number;
  metadata?: Record<string, unknown>;
  seasonal_context?: Record<string, unknown>;
  created_at?: string;
}

export interface GrowthLifecyclePayload {
  touchpoint_id: string;
  tenant_id: string;
  prospect_id: string;
  trigger_id: string;
  to_state: string;
  source_version: string;
  source_component?: string;
  channel?: string;
  experiment_id?: string;
  arm_id?: string;
  signal_quality_score?: number;
  cost?: number;
  metadata?: Record<string, unknown>;
  seasonal_context?: Record<string, unknown>;
  created_at?: string;
}

export interface GrowthAdvisorWeeklyPayload {
  tenant_id: string;
  source_version: string;
  wedges?: string[];
  context?: Record<string, unknown>;
  now_iso?: string;
}

export interface InboundPollRequestedPayload {
  tenant_id: string;
  account_ids?: string[];
}

export interface InboundMessageReceivedPayload {
  tenant_id: string;
  account_id: string;
  message_id: string;
  from_addr: string;
  from_domain: string;
  subject: string;
  source: "organic" | "reply";
}

export interface InboundMessageProcessedPayload {
  tenant_id: string;
  message_id: string;
  action: string;
  total_score: number;
  stage: string;
  draft_generated: boolean;
  escalated: boolean;
}

export interface InboundEscalationTriggeredPayload {
  tenant_id: string;
  message_id: string;
  from_addr: string;
  subject: string;
  total_score: number;
  reasoning: string;
  action: string;
  priority: "high" | "normal";
  channel: string;
  escalated_at: string;
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

export function validateGrowthTouchpointPayload(payload: GrowthTouchpointPayload): string[] {
  const errors: string[] = [];
  if (!payload.touchpoint_id) errors.push("touchpoint_id is required");
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (!payload.prospect_id) errors.push("prospect_id is required");
  if (!payload.touchpoint_type) errors.push("touchpoint_type is required");
  if (!payload.source_component) errors.push("source_component is required");
  if (!payload.source_version) errors.push("source_version is required");
  return errors;
}

export function validateGrowthLifecyclePayload(payload: GrowthLifecyclePayload): string[] {
  const errors: string[] = [];
  if (!payload.touchpoint_id) errors.push("touchpoint_id is required");
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (!payload.prospect_id) errors.push("prospect_id is required");
  if (!payload.trigger_id) errors.push("trigger_id is required");
  if (!payload.to_state) errors.push("to_state is required");
  if (!payload.source_version) errors.push("source_version is required");
  return errors;
}

export function validateGrowthAdvisorWeeklyPayload(payload: GrowthAdvisorWeeklyPayload): string[] {
  const errors: string[] = [];
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (!payload.source_version) errors.push("source_version is required");
  return errors;
}

export function validateInboundPollRequestedPayload(payload: InboundPollRequestedPayload): string[] {
  const errors: string[] = [];
  if (!payload.tenant_id) errors.push("tenant_id is required");
  return errors;
}

export function validateInboundMessageReceivedPayload(payload: InboundMessageReceivedPayload): string[] {
  const errors: string[] = [];
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (!payload.account_id) errors.push("account_id is required");
  if (!payload.message_id) errors.push("message_id is required");
  if (!payload.from_addr) errors.push("from_addr is required");
  if (!payload.source) errors.push("source is required");
  if (payload.source && !["organic", "reply"].includes(payload.source)) {
    errors.push("source must be 'organic' or 'reply'");
  }
  return errors;
}
