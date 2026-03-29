import type {
  BookingStatus,
  Call,
  CallerType,
  CallRecordListRow,
  CallRecordRow,
  EndCallReason,
  HVACIssueType,
  PrimaryIntent,
  RevenueTier,
  Route,
  TranscriptEntry,
  UrgencyTier,
} from "@/types/call"

function str(val: unknown, fallback = ""): string {
  return typeof val === "string" ? val : fallback
}

function bool(val: unknown, fallback = false): boolean {
  return typeof val === "boolean" ? val : fallback
}

const URGENCY_MAP: Record<string, UrgencyTier> = {
  emergency: "LifeSafety",
  urgent: "Urgent",
  routine: "Routine",
  estimate: "Estimate",
}

const ROUTE_MAP: Record<string, Route> = {
  legitimate: "legitimate",
  spam: "spam",
  vendor: "vendor",
}

const CALLER_TYPE_MAP: Record<string, CallerType> = {
  residential: "residential",
  commercial: "commercial",
  property_manager: "property_manager",
  third_party: "third_party",
  job_applicant: "job_applicant",
  vendor: "vendor",
  spam: "spam",
  unknown: "unknown",
}

const PRIMARY_INTENT_MAP: Record<string, PrimaryIntent> = {
  service: "service",
  maintenance: "maintenance",
  installation: "installation",
  estimate: "estimate",
  complaint: "complaint",
  followup: "followup",
  sales: "sales",
  booking_request: "booking_request",
  active_job_issue: "active_job_issue",
  solicitation: "solicitation",
  admin_billing: "admin_billing",
  new_lead: "new_lead",
  unknown: "unknown",
}

const REVENUE_TIER_MAP: Record<string, RevenueTier> = {
  replacement: "replacement",
  major_repair: "major_repair",
  standard_repair: "standard_repair",
  minor: "minor",
  diagnostic: "diagnostic",
  unknown: "unknown",
}

function getFields(row: CallRecordRow | CallRecordListRow): Record<string, unknown> {
  return typeof row.extracted_fields === "object" && row.extracted_fields !== null
    ? row.extracted_fields
    : {}
}

function field(
  fields: Record<string, unknown>,
  snakeKey: string,
  camelKey?: string
): unknown {
  return fields[snakeKey] ?? (camelKey ? fields[camelKey] : undefined)
}

export function formatPhone(phone: string): string {
  const digits = phone.replace(/\D/g, "")
  const national = digits.startsWith("1") && digits.length === 11 ? digits.slice(1) : digits
  if (national.length === 10) {
    return `(${national.slice(0, 3)}) ${national.slice(3, 6)}-${national.slice(6)}`
  }
  return phone
}

export function mapUrgency(tier: string | null): UrgencyTier {
  if (!tier) return "Routine"
  return URGENCY_MAP[tier.toLowerCase()] ?? "Routine"
}

export function parseTranscript(raw: string): TranscriptEntry[] {
  if (!raw.trim()) return []

  return raw
    .split("\n")
    .map((line) => line.trim())
    .flatMap((line): TranscriptEntry[] => {
      const match = /^(Agent|User):\s*(.+)$/i.exec(line)
      if (!match) return []

      return [
        {
          role: match[1].toLowerCase() === "agent" ? "agent" : "user",
          content: match[2],
        },
      ]
    })
}

export function transformCallRecord(
  row: CallRecordRow | CallRecordListRow,
  readIds: Set<string>
): Call {
  const fields = getFields(row)
  const transcript = "transcript" in row && typeof row.transcript === "string"
    ? parseTranscript(row.transcript)
    : []

  const appointmentDateTime = str(
    field(fields, "appointment_datetime", "appointmentDateTime")
  )
  const callbackType = str(field(fields, "callback_type", "callbackType"))
  const hvacIssueType = str(field(fields, "hvac_issue_type", "hvacIssueType"))

  return {
    id: row.call_id,
    customerName: str(field(fields, "customer_name", "customerName")) || "Unknown Caller",
    customerPhone:
      row.phone_number ?? str(field(fields, "customer_phone", "customerPhone")),
    serviceAddress: str(field(fields, "service_address", "serviceAddress")),
    problemDescription: str(
      field(fields, "problem_description", "problemDescription")
    ),
    urgency: mapUrgency(row.urgency_tier),
    hvacIssueType: (hvacIssueType as HVACIssueType) || null,
    equipmentType: str(field(fields, "equipment_type", "equipmentType")),
    equipmentBrand: str(field(fields, "equipment_brand", "equipmentBrand")),
    equipmentAge: str(field(fields, "equipment_age", "equipmentAge")),
    appointmentBooked: bool(
      field(fields, "appointment_booked", "appointmentBooked")
    ),
    appointmentDateTime: appointmentDateTime || null,
    endCallReason: (row.end_call_reason as EndCallReason) ?? null,
    isSafetyEmergency: bool(
      field(fields, "is_safety_emergency", "isSafetyEmergency")
    ),
    isUrgentEscalation: bool(
      field(fields, "is_urgent_escalation", "isUrgentEscalation")
    ),
    transcript,
    callbackType: callbackType || null,
    read: readIds.has(row.call_id),
    callbackOutcome: (row.callback_outcome as import("@/types/call").CallbackOutcome) ?? null,
    callbackOutcomeAt: row.callback_outcome_at ?? null,
    bookingStatus: ((row as CallRecordRow).booking_status as BookingStatus) ?? null,
    bookingStatusAt: (row as CallRecordRow).booking_status_at ?? null,
    bookingNotes: (row as CallRecordRow).booking_notes ?? null,
    callbackWindowStart: str(field(fields, "callback_window_start", "callbackWindowStart")) || null,
    callbackWindowEnd: str(field(fields, "callback_window_end", "callbackWindowEnd")) || null,
    callerType: CALLER_TYPE_MAP[(row as CallRecordRow).caller_type ?? ""] ?? null,
    primaryIntent: PRIMARY_INTENT_MAP[(row as CallRecordRow).primary_intent ?? ""] ?? null,
    route: ROUTE_MAP[(row as CallRecordRow).route ?? ""] ?? null,
    revenueTier: REVENUE_TIER_MAP[(row as CallRecordRow).revenue_tier ?? ""] ?? null,
    extractionStatus: row.extraction_status ?? null,
    callRecordingUrl: (row as CallRecordRow).call_recording_url ?? null,
    createdAt: row.created_at,
  }
}
