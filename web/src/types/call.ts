// Types for CallLock support app
// Maps to Supabase call_sessions table

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
// conversation_state is Record<string, unknown> — we don't own this schema.
// The V2 backend writes ConversationState JSONB; we extract defensively in transforms.ts.
export interface CallSessionRow {
  call_id: string
  conversation_state: Record<string, unknown>
  retell_data?: Record<string, unknown>
  synced_to_dashboard: boolean
  created_at: string
}
