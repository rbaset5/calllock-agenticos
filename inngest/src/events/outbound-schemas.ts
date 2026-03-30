export interface OutboundBatchCompletePayload {
  tenant_id: string;
  ingested: number;
  scored: number;
  a_leads: number;
  b_leads: number;
  source_version: string;
}

export interface OutboundTestBatchCompletePayload {
  tenant_id: string;
  tested: number;
  confirmed_weak: number;
  answered: number;
  source_version: string;
}

export interface OutboundCallOutcomePayload {
  tenant_id: string;
  prospect_id: string;
  twilio_call_sid: string;
  outcome: string;
  source_version: string;
}

export interface OutboundPipelineErrorPayload {
  tenant_id: string;
  error_type: string;
  error_message: string;
  source_version: string;
}

export const OUTBOUND_BATCH_COMPLETE = "outbound/scout.batch-complete";
export const OUTBOUND_TEST_COMPLETE = "outbound/scout.test-batch-complete";
export const OUTBOUND_CALL_OUTCOME = "outbound/call.outcome-logged";
export const OUTBOUND_EXTRACTION_COMPLETE = "outbound/call.extraction-complete";
export const OUTBOUND_PIPELINE_ERROR = "outbound/pipeline.error";

export interface OutboundExtractionCompletePayload {
  tenant_id: string;
  prospect_id: string;
  twilio_call_sid: string;
  business_name: string;
  extraction: {
    reached_decision_maker?: boolean;
    current_call_handling?: string;
    missed_call_pain?: string;
    after_hours_workflow?: string;
    objection_type?: string;
    objection_verbatim?: string;
    buying_temperature?: string;
    follow_up_action?: string;
    follow_up_date?: string | null;
    status_quo_details?: string;
  };
  source_version: string;
}

export function validateOutboundExtractionCompletePayload(payload: OutboundExtractionCompletePayload): string[] {
  const errors: string[] = [];
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (!payload.twilio_call_sid) errors.push("twilio_call_sid is required");
  if (!payload.extraction) errors.push("extraction is required");
  if (!payload.source_version) errors.push("source_version is required");
  return errors;
}

export function validateOutboundBatchCompletePayload(payload: OutboundBatchCompletePayload): string[] {
  const errors: string[] = [];
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (typeof payload.ingested !== "number") errors.push("ingested must be a number");
  if (typeof payload.scored !== "number") errors.push("scored must be a number");
  if (typeof payload.a_leads !== "number") errors.push("a_leads must be a number");
  if (typeof payload.b_leads !== "number") errors.push("b_leads must be a number");
  if (!payload.source_version) errors.push("source_version is required");
  return errors;
}

export function validateOutboundTestBatchCompletePayload(payload: OutboundTestBatchCompletePayload): string[] {
  const errors: string[] = [];
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (typeof payload.tested !== "number") errors.push("tested must be a number");
  if (typeof payload.confirmed_weak !== "number") errors.push("confirmed_weak must be a number");
  if (typeof payload.answered !== "number") errors.push("answered must be a number");
  if (!payload.source_version) errors.push("source_version is required");
  return errors;
}

export function validateOutboundCallOutcomePayload(payload: OutboundCallOutcomePayload): string[] {
  const errors: string[] = [];
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (!payload.prospect_id) errors.push("prospect_id is required");
  if (!payload.twilio_call_sid) errors.push("twilio_call_sid is required");
  if (!payload.outcome) errors.push("outcome is required");
  if (!payload.source_version) errors.push("source_version is required");
  return errors;
}

export function validateOutboundPipelineErrorPayload(payload: OutboundPipelineErrorPayload): string[] {
  const errors: string[] = [];
  if (!payload.tenant_id) errors.push("tenant_id is required");
  if (!payload.error_type) errors.push("error_type is required");
  if (!payload.error_message) errors.push("error_message is required");
  if (!payload.source_version) errors.push("source_version is required");
  return errors;
}
