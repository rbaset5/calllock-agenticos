import type { Call, CallRecordListRow } from "@/types/call"

export const CALLS_PAGE_SIZE = 100

export const CALL_RECORD_LIST_COLUMNS =
  "id, tenant_id, call_id, retell_call_id, phone_number, transcript, extracted_fields, extraction_status, urgency_tier, end_call_reason, callback_outcome, callback_outcome_at, booking_status, booking_status_at, booking_notes, callback_scheduled, booking_id, route, caller_type, primary_intent, revenue_tier, created_at, updated_at"

export function trimCallRecordPage(rows: CallRecordListRow[]): {
  rows: CallRecordListRow[]
  hasMore: boolean
} {
  if (rows.length <= CALLS_PAGE_SIZE) {
    return { rows, hasMore: false }
  }

  return {
    rows: rows.slice(0, CALLS_PAGE_SIZE),
    hasMore: true,
  }
}

export function filterCalls(calls: Call[], query: string): Call[] {
  const normalizedQuery = query.trim().toLowerCase()
  if (!normalizedQuery) {
    return calls
  }

  return calls.filter((call) => {
    return [
      call.customerName,
      call.customerPhone,
      call.problemDescription,
    ].some((value) => value.toLowerCase().includes(normalizedQuery))
  })
}

export function mergeCalls(
  existingCalls: Call[],
  incomingCalls: Call[],
  placement: "prepend" | "append"
): Call[] {
  const merged =
    placement === "prepend"
      ? [...incomingCalls, ...existingCalls]
      : [...existingCalls, ...incomingCalls]

  const seen = new Set<string>()
  return merged.filter((call) => {
    if (seen.has(call.id)) {
      return false
    }
    seen.add(call.id)
    return true
  })
}
