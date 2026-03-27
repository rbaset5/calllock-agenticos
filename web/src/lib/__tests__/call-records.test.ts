import { describe, expect, it } from "vitest"
import {
  CALLS_PAGE_SIZE,
  filterCalls,
  mergeCalls,
  trimCallRecordPage,
} from "@/lib/call-records"
import type { Call, CallRecordListRow } from "@/types/call"

function buildCall(overrides: Partial<Call> = {}): Call {
  return {
    id: "call-1",
    customerName: "Jane Doe",
    customerPhone: "+15551234567",
    serviceAddress: "123 Main St",
    problemDescription: "AC not cooling",
    urgency: "Urgent",
    hvacIssueType: "No Cool",
    equipmentType: "Central AC",
    equipmentBrand: "Carrier",
    equipmentAge: "12 years",
    appointmentBooked: false,
    appointmentDateTime: null,
    endCallReason: null,
    isSafetyEmergency: false,
    isUrgentEscalation: false,
    transcript: [],
    callbackType: null,
    read: false,
    callbackOutcome: null,
    callbackOutcomeAt: null,
    callbackWindowStart: null,
    callbackWindowEnd: null,
    callerType: null,
    primaryIntent: null,
    route: null,
    revenueTier: null,
    extractionStatus: null,
    callRecordingUrl: null,
    createdAt: "2026-03-18T15:00:00Z",
    ...overrides,
  }
}

function buildRow(index: number): CallRecordListRow {
  return {
    id: `row-${index}`,
    tenant_id: "tenant-1",
    call_id: `call-${index}`,
    retell_call_id: `retell-${index}`,
    phone_number: `+1555000${index}`,
    transcript: null,
    extracted_fields: {},
    extraction_status: "completed",
    urgency_tier: "routine",
    end_call_reason: null,
    callback_outcome: null,
    callback_outcome_at: null,
    callback_scheduled: false,
    booking_id: null,
    route: null,
    caller_type: null,
    primary_intent: null,
    revenue_tier: null,
    created_at: `2026-03-18T15:${String(index).padStart(2, "0")}:00Z`,
    updated_at: `2026-03-18T15:${String(index).padStart(2, "0")}:30Z`,
  }
}

describe("filterCalls", () => {
  const calls = [
    buildCall(),
    buildCall({
      id: "call-2",
      customerName: "John Smith",
      customerPhone: "+15557654321",
      problemDescription: "Furnace making loud noise",
    }),
  ]

  it("matches customer name, phone, and problem description", () => {
    expect(filterCalls(calls, "jane")).toHaveLength(1)
    expect(filterCalls(calls, "6543")).toHaveLength(1)
    expect(filterCalls(calls, "loud noise")).toHaveLength(1)
  })

  it("returns all calls when the query is blank", () => {
    expect(filterCalls(calls, "   ")).toEqual(calls)
  })
})

describe("mergeCalls", () => {
  it("deduplicates by call id while keeping incoming prepend order", () => {
    const existing = [buildCall(), buildCall({ id: "call-2" })]
    const incoming = [
      buildCall({ id: "call-3" }),
      buildCall({ id: "call-1", customerName: "Updated Jane" }),
    ]

    expect(mergeCalls(existing, incoming, "prepend").map((call) => call.id)).toEqual([
      "call-3",
      "call-1",
      "call-2",
    ])
  })
})

describe("trimCallRecordPage", () => {
  it("keeps hasMore false when the page is within the limit", () => {
    const rows = Array.from({ length: 3 }, (_, index) => buildRow(index))

    expect(trimCallRecordPage(rows)).toEqual({
      rows,
      hasMore: false,
    })
  })

  it("trims an extra row and marks hasMore", () => {
    const rows = Array.from(
      { length: CALLS_PAGE_SIZE + 1 },
      (_, index) => buildRow(index)
    )

    const result = trimCallRecordPage(rows)

    expect(result.rows).toHaveLength(CALLS_PAGE_SIZE)
    expect(result.hasMore).toBe(true)
  })
})
