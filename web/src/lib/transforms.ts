import type {
  Call,
  CallRecordListRow,
  CallRecordRow,
  EndCallReason,
  HVACIssueType,
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
    customerName: str(field(fields, "customer_name", "customerName"), "Unknown Caller"),
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
    createdAt: row.created_at,
  }
}
