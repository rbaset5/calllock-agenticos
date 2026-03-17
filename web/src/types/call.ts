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
  call_recording_url: string | null
  synced_to_app: boolean
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
  | "extracted_fields"
  | "extraction_status"
  | "urgency_tier"
  | "end_call_reason"
  | "callback_scheduled"
  | "booking_id"
  | "synced_to_app"
  | "created_at"
  | "updated_at"
>
