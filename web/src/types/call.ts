// Types for CallLock support app
// Maps to Supabase call_records table

export type UrgencyTier = "LifeSafety" | "Urgent" | "Routine" | "Estimate"

export type EndCallReason =
  | "wrong_number"
  | "callback_later"
  | "safety_emergency"
  | "urgent_escalation"
  | "out_of_area"
  | "waitlist_added"
  | "completed"
  | "customer_hangup"
  | "sales_lead"
  | "cancelled"
  | "rescheduled"
  | "booking_failed"

export type CallbackOutcome =
  | "reached_customer"
  | "scheduled"
  | "left_voicemail"
  | "no_answer"
  | "resolved_elsewhere"

export interface CallbackTouch {
  id: string
  callId: string
  outcome: CallbackOutcome
  createdAt: string
}

/** Terminal outcomes that remove a call from the unresolved queue */
export const TERMINAL_CALLBACK_OUTCOMES: ReadonlySet<CallbackOutcome> = new Set([
  "reached_customer",
  "scheduled",
  "resolved_elsewhere",
])

/**
 * EndCallReasons that make a call terminal (never enters unresolved queue).
 *
 * Confirmed against EndCallReason enum:
 * - wrong_number, out_of_area, cancelled, completed, rescheduled → terminal
 * - callback_later, booking_failed, customer_hangup, safety_emergency,
 *   urgent_escalation, waitlist_added, sales_lead → non-terminal (stay unresolved)
 *
 * Rationale: rescheduled means the customer was already reached and rebooked.
 * waitlist_added and sales_lead remain unresolved because the owner still
 * needs to follow up or convert.
 */
export const TERMINAL_END_CALL_REASONS: ReadonlySet<EndCallReason> = new Set([
  "wrong_number",
  "out_of_area",
  "cancelled",
  "completed",
  "rescheduled",
])

export type TriageCommand = "Call now" | "Next up" | "Today" | "Can wait"

export type TriageReason =
  | "no_cooling"
  | "no_heating"
  | "estimate_request"
  | "callback_requested"
  | "booking_failed"
  | "urgent_escalation"
  | "generic_service_issue"

export interface TriageResult {
  isUnresolved: boolean
  command: TriageCommand
  evidence: string
  reason: TriageReason
  isStale: boolean
  staleMinutes: number
  callbackWindowStart: string | null
  callbackWindowEnd: string | null
  callbackWindowValid: boolean
}

// Classification types — normalized from Supabase via lookup maps in transforms.ts
export type CallerType = "residential" | "commercial" | "property_manager" | "third_party" | "job_applicant" | "vendor" | "spam" | "unknown"
export type PrimaryIntent = "service" | "maintenance" | "installation" | "estimate" | "complaint" | "followup" | "sales" | "booking_request" | "active_job_issue" | "solicitation" | "admin_billing" | "new_lead" | "unknown"
export type Route = "legitimate" | "spam" | "vendor"
export type RevenueTier = "replacement" | "major_repair" | "standard_repair" | "minor" | "diagnostic" | "unknown"

export type HVACIssueType =
  | "Cooling"
  | "Heating"
  | "Maintenance"
  | "Leaking"
  | "No Cool"
  | "No Heat"
  | "Noisy System"
  | "Odor"
  | "Not Running"
  | "Thermostat"

export interface TranscriptEntry {
  role: "agent" | "user"
  content: string
}

export interface Call {
  id: string
  customerName: string
  customerPhone: string
  serviceAddress: string
  problemDescription: string
  urgency: UrgencyTier
  hvacIssueType: HVACIssueType | null
  equipmentType: string
  equipmentBrand: string
  equipmentAge: string
  appointmentBooked: boolean
  appointmentDateTime: string | null
  endCallReason: EndCallReason | null
  isSafetyEmergency: boolean
  isUrgentEscalation: boolean
  transcript: TranscriptEntry[]
  callbackType: string | null
  read: boolean
  callbackOutcome: CallbackOutcome | null
  callbackOutcomeAt: string | null
  callbackWindowStart: string | null
  callbackWindowEnd: string | null
  callerType: CallerType | null
  primaryIntent: PrimaryIntent | null
  route: Route | null
  revenueTier: RevenueTier | null
  extractionStatus: string | null
  callRecordingUrl: string | null
  createdAt: string
}

// Raw Supabase row shape
export interface CallRecordRow {
  id: string
  tenant_id: string
  call_id: string
  retell_call_id: string
  phone_number: string | null
  transcript: string | null
  raw_retell_payload: Record<string, unknown>
  extracted_fields: Record<string, unknown>
  extraction_status: string
  quality_score: number | null
  tags: string[]
  route: string | null
  urgency_tier: string | null
  caller_type: string | null
  primary_intent: string | null
  revenue_tier: string | null
  booking_id: string | null
  callback_scheduled: boolean
  call_duration_seconds: number | null
  end_call_reason: string | null
  callback_outcome: string | null
  callback_outcome_at: string | null
  call_recording_url: string | null
  created_at: string
  updated_at: string
}

export type CallRecordListRow = Pick<
  CallRecordRow,
  | "id"
  | "tenant_id"
  | "call_id"
  | "retell_call_id"
  | "phone_number"
  | "transcript"
  | "extracted_fields"
  | "extraction_status"
  | "urgency_tier"
  | "end_call_reason"
  | "callback_outcome"
  | "callback_outcome_at"
  | "callback_scheduled"
  | "booking_id"
  | "route"
  | "caller_type"
  | "primary_intent"
  | "revenue_tier"
  | "created_at"
  | "updated_at"
>
