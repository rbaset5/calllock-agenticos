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

export const CALL_ENDED = "calllock/call.ended";
export const CALL_EMERGENCY_SMS = "calllock/call.emergency.sms";
export const AGENT_STATE_CHANGED = "calllock/agent.state.changed";
export const AGENT_HANDOFF = "calllock/agent.handoff";
export const AGENT_DISPATCH = "calllock/agent.dispatch";

export interface AgentStateChangedPayload {
  agent_id: string;
  tenant_id: string;
  department: string;
  role: string;
  from_state: string;
  to_state: string;
  description?: string | null;
}

export interface AgentHandoffPayload {
  from_agent: string;
  to_agent: string;
  from_department: string;
  to_department: string;
  tenant_id?: string;
  call_id?: string;
  lead_id?: string;
  context_summary?: string;
  timestamp?: string;
}

export interface AgentDispatchPayload {
  worker_id: string;
  tenant_id: string;
  origin_worker_id: string;
  department: string;
  role: string;
  task_type: string;
  task_context: Record<string, unknown>;
  idempotency_key: string;
  priority?: "low" | "medium" | "high";
  requires_approval?: boolean;
  description?: string | null;
}

export interface CallEndedPayload {
  tenant_id: string;
  call_id: string;
  call_source?: "retell";
  phone_number: string;
  transcript: string;
  customer_name?: string | null;
  service_address?: string | null;
  problem_description?: string | null;
  urgency_tier: "emergency" | "urgent" | "routine" | "estimate";
  caller_type:
    | "residential"
    | "commercial"
    | "property_management"
    | "vendor"
    | "recruiter"
    | "spam"
    | "unknown";
  primary_intent:
    | "service"
    | "maintenance"
    | "estimate"
    | "installation"
    | "callback"
    | "billing"
    | "other"
    | "unknown";
  revenue_tier:
    | "low_value"
    | "standard_repair"
    | "high_value"
    | "membership"
    | "replacement"
    | "maintenance_plan"
    | "unknown";
  tags: string[];
  quality_score: number;
  scorecard_warnings: string[];
  route: "legitimate" | "spam" | "vendor" | "recruiter";
  booking_id?: string | null;
  callback_scheduled?: boolean;
  extraction_status: "complete" | "partial";
  retell_call_id: string;
  call_duration_seconds: number;
  end_call_reason:
    | "customer_hangup"
    | "agent_hangup"
    | "booking_confirmed"
    | "callback_scheduled"
    | "sales_lead"
    | "out_of_area"
    | "safety_exit"
    | "wrong_number"
    | "voicemail"
    | "transfer"
    | "error";
  call_recording_url?: string | null;
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

export function validateCallEndedPayload(payload: CallEndedPayload): string[] {
  const errors: string[] = [];
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (!payload.call_id) errors.push("call_id is required");
  if (!payload.phone_number) errors.push("phone_number is required");
  if (payload.transcript === undefined) errors.push("transcript is required");
  if (!payload.urgency_tier) errors.push("urgency_tier is required");
  if (!payload.caller_type) errors.push("caller_type is required");
  if (!payload.primary_intent) errors.push("primary_intent is required");
  if (!payload.revenue_tier) errors.push("revenue_tier is required");
  if (!Array.isArray(payload.tags)) errors.push("tags must be an array");
  if (typeof payload.quality_score !== "number" || Number.isNaN(payload.quality_score)) {
    errors.push("quality_score must be a number");
  }
  if (!Array.isArray(payload.scorecard_warnings)) {
    errors.push("scorecard_warnings must be an array");
  }
  if (!payload.route) errors.push("route is required");
  if (!payload.extraction_status) errors.push("extraction_status is required");
  if (!payload.retell_call_id) errors.push("retell_call_id is required");
  if (
    typeof payload.call_duration_seconds !== "number" ||
    Number.isNaN(payload.call_duration_seconds) ||
    payload.call_duration_seconds < 0
  ) {
    errors.push("call_duration_seconds must be a non-negative number");
  }
  if (!payload.end_call_reason) errors.push("end_call_reason is required");
  if (payload.call_source && payload.call_source !== "retell") {
    errors.push("call_source must be 'retell'");
  }
  if (payload.urgency_tier && !["emergency", "urgent", "routine", "estimate"].includes(payload.urgency_tier)) {
    errors.push("urgency_tier is invalid");
  }
  if (
    payload.caller_type &&
    !["residential", "commercial", "property_management", "vendor", "recruiter", "spam", "unknown"].includes(
      payload.caller_type,
    )
  ) {
    errors.push("caller_type is invalid");
  }
  if (
    payload.primary_intent &&
    !["service", "maintenance", "estimate", "installation", "callback", "billing", "other", "unknown"].includes(
      payload.primary_intent,
    )
  ) {
    errors.push("primary_intent is invalid");
  }
  if (
    payload.revenue_tier &&
    !["low_value", "standard_repair", "high_value", "membership", "replacement", "maintenance_plan", "unknown"].includes(
      payload.revenue_tier,
    )
  ) {
    errors.push("revenue_tier is invalid");
  }
  if (payload.route && !["legitimate", "spam", "vendor", "recruiter"].includes(payload.route)) {
    errors.push("route is invalid");
  }
  if (payload.extraction_status && !["complete", "partial"].includes(payload.extraction_status)) {
    errors.push("extraction_status is invalid");
  }
  if (
    payload.end_call_reason &&
    ![
      "customer_hangup",
      "agent_hangup",
      "booking_confirmed",
      "callback_scheduled",
      "sales_lead",
      "out_of_area",
      "safety_exit",
      "wrong_number",
      "voicemail",
      "transfer",
      "error",
    ].includes(payload.end_call_reason)
  ) {
    errors.push("end_call_reason is invalid");
  }
  return errors;
}

<<<<<<< HEAD
export function validateAgentHandoffPayload(payload: AgentHandoffPayload): string[] {
  const errors: string[] = [];
  if (!payload.from_agent) errors.push("from_agent is required");
  if (!payload.to_agent) errors.push("to_agent is required");
  if (!payload.from_department) errors.push("from_department is required");
  if (!payload.to_department) errors.push("to_department is required");
  return errors;
}
=======
export { type GuardianDispatchPayload, type GuardianWatchdogPayload } from "./guardian-schemas.js";
>>>>>>> f542157 (feat: add guardian dispatch Inngest event and function)

export function validateAgentStateChangedPayload(
  payload: AgentStateChangedPayload,
): string[] {
  const errors: string[] = [];
  if (!payload.agent_id) errors.push("agent_id is required");
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (!payload.department) errors.push("department is required");
  if (!payload.role) errors.push("role is required");
  if (payload.from_state === undefined) errors.push("from_state is required");
  if (!payload.to_state) errors.push("to_state is required");
  return errors;
}

export function validateAgentDispatchPayload(payload: AgentDispatchPayload): string[] {
  const errors: string[] = [];
  if (!payload.worker_id) errors.push("worker_id is required");
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (!payload.origin_worker_id) errors.push("origin_worker_id is required");
  if (!payload.department) errors.push("department is required");
  if (!payload.role) errors.push("role is required");
  if (!payload.task_type) errors.push("task_type is required");
  if (!payload.idempotency_key) errors.push("idempotency_key is required");
  if (!payload.task_context || typeof payload.task_context !== "object" || Array.isArray(payload.task_context)) {
    errors.push("task_context must be an object");
  }
  if (payload.priority && !["low", "medium", "high"].includes(payload.priority)) {
    errors.push("priority is invalid");
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

export { type GuardianDispatchPayload, type GuardianWatchdogPayload } from "./guardian-schemas.js";
