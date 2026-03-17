import type { Call, CallSessionRow, TranscriptEntry, UrgencyTier, HVACIssueType, EndCallReason } from "@/types/call"

// Helper to safely extract a string from unknown JSONB
function str(val: unknown, fallback = ""): string {
  return typeof val === "string" ? val : fallback
}

function bool(val: unknown, fallback = false): boolean {
  return typeof val === "boolean" ? val : fallback
}

export function transformCallSession(row: CallSessionRow, readIds: Set<string>): Call {
  const cs = row.conversation_state

  // Extract transcript from retell_data if present
  let transcript: TranscriptEntry[] = []
  if (row.retell_data && typeof row.retell_data === "object") {
    const call = (row.retell_data as Record<string, unknown>).call
    if (call && typeof call === "object") {
      const transcriptObj = (call as Record<string, unknown>).transcript_object
      if (Array.isArray(transcriptObj)) {
        transcript = transcriptObj.filter(
          (t): t is TranscriptEntry =>
            typeof t === "object" &&
            t !== null &&
            (t.role === "agent" || t.role === "user") &&
            typeof t.content === "string"
        )
      }
    }
  }

  return {
    id: row.call_id,
    customerName: str(cs.customerName, "Unknown Caller"),
    customerPhone: str(cs.customerPhone),
    serviceAddress: str(cs.serviceAddress),
    problemDescription: str(cs.problemDescription),
    urgency: (str(cs.urgencyTier, "Routine") as UrgencyTier),
    hvacIssueType: (str(cs.hvacIssueType) as HVACIssueType) || null,
    equipmentType: str(cs.equipmentType),
    equipmentBrand: str(cs.equipmentBrand),
    equipmentAge: str(cs.equipmentAge),
    appointmentBooked: bool(cs.appointmentBooked),
    appointmentDateTime: str(cs.appointmentDateTime) || null,
    endCallReason: (str(cs.endCallReason) as EndCallReason) || null,
    isSafetyEmergency: bool(cs.isSafetyEmergency),
    isUrgentEscalation: bool(cs.isUrgentEscalation),
    transcript,
    callbackType: str(cs.callbackType) || null,
    read: readIds.has(row.call_id),
    createdAt: row.created_at,
  }
}
