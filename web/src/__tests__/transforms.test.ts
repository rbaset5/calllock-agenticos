import { describe, expect, it } from "vitest"
import {
  mapUrgency,
  parseTranscript,
  transformCallRecord,
} from "@/lib/transforms"
import type { CallRecordListRow, CallRecordRow } from "@/types/call"

function buildCallRecordRow(
  overrides: Partial<CallRecordRow> = {}
): CallRecordRow {
  return {
    id: "row_123",
    tenant_id: "tenant_123",
    call_id: "call_123",
    retell_call_id: "retell_123",
    phone_number: "+15125551234",
    transcript: "Agent: Thanks for calling\nUser: My AC is broken",
    raw_retell_payload: {},
    extracted_fields: {
      customer_name: "Janice",
      service_address: "1211 Squawk Street",
      problem_description: "AC blowing warm air",
      hvac_issue_type: "Cooling",
      equipment_type: "AC unit",
      equipment_brand: "Carrier",
      equipment_age: "10 years",
      appointment_booked: true,
      appointment_datetime: "2026-03-10T08:00:00",
      is_safety_emergency: false,
      is_urgent_escalation: true,
      callback_type: "service",
    },
    extraction_status: "completed",
    quality_score: 0.98,
    tags: ["vip"],
    route: "dispatcher",
    urgency_tier: "urgent",
    caller_type: "customer",
    primary_intent: "repair",
    revenue_tier: "high",
    booking_id: "booking_123",
    callback_scheduled: false,
    call_duration_seconds: 245,
    end_call_reason: "completed",
    callback_outcome: null,
    callback_outcome_at: null,
    call_recording_url: "https://example.com/recording.mp3",
    created_at: "2026-03-05T10:00:00Z",
    updated_at: "2026-03-05T10:05:00Z",
    ...overrides,
  }
}

describe("transformCallRecord", () => {
  it("maps a complete row into the app Call shape", () => {
    const row = buildCallRecordRow()

    const call = transformCallRecord(row, new Set())

    expect(call.id).toBe("call_123")
    expect(call.customerName).toBe("Janice")
    expect(call.customerPhone).toBe("+15125551234")
    expect(call.serviceAddress).toBe("1211 Squawk Street")
    expect(call.problemDescription).toBe("AC blowing warm air")
    expect(call.urgency).toBe("Urgent")
    expect(call.hvacIssueType).toBe("Cooling")
    expect(call.equipmentType).toBe("AC unit")
    expect(call.equipmentBrand).toBe("Carrier")
    expect(call.equipmentAge).toBe("10 years")
    expect(call.appointmentBooked).toBe(true)
    expect(call.appointmentDateTime).toBe("2026-03-10T08:00:00")
    expect(call.endCallReason).toBe("completed")
    expect(call.isSafetyEmergency).toBe(false)
    expect(call.isUrgentEscalation).toBe(true)
    expect(call.callbackType).toBe("service")
    expect(call.transcript).toEqual([
      { role: "agent", content: "Thanks for calling" },
      { role: "user", content: "My AC is broken" },
    ])
    expect(call.read).toBe(false)
    expect(call.createdAt).toBe("2026-03-05T10:00:00Z")
  })

  it("uses safe defaults when extracted_fields is empty", () => {
    const row: CallRecordListRow = {
      id: "row_empty",
      tenant_id: "tenant_123",
      call_id: "call_empty",
      retell_call_id: "retell_empty",
      phone_number: null,
      transcript: null,
      extracted_fields: {},
      extraction_status: "pending",
      urgency_tier: null,
      end_call_reason: null,
      callback_outcome: null,
      callback_outcome_at: null,
      callback_scheduled: false,
      booking_id: null,
      route: null,
      caller_type: null,
      primary_intent: null,
      revenue_tier: null,
      created_at: "2026-03-05T10:00:00Z",
      updated_at: "2026-03-05T10:05:00Z",
    }

    const call = transformCallRecord(row, new Set())

    expect(call.id).toBe("call_empty")
    expect(call.customerName).toBe("Unknown Caller")
    expect(call.customerPhone).toBe("")
    expect(call.serviceAddress).toBe("")
    expect(call.problemDescription).toBe("")
    expect(call.urgency).toBe("Routine")
    expect(call.hvacIssueType).toBeNull()
    expect(call.equipmentType).toBe("")
    expect(call.equipmentBrand).toBe("")
    expect(call.equipmentAge).toBe("")
    expect(call.appointmentBooked).toBe(false)
    expect(call.appointmentDateTime).toBeNull()
    expect(call.endCallReason).toBeNull()
    expect(call.isSafetyEmergency).toBe(false)
    expect(call.isUrgentEscalation).toBe(false)
    expect(call.callbackType).toBeNull()
    expect(call.transcript).toEqual([])
  })

  it("respects the readIds state keyed by call_id", () => {
    const row = buildCallRecordRow({ call_id: "call_read" })

    const call = transformCallRecord(row, new Set(["call_read"]))

    expect(call.read).toBe(true)
  })
})

describe("mapUrgency", () => {
  it("maps all known tiers", () => {
    expect(mapUrgency("emergency")).toBe("LifeSafety")
    expect(mapUrgency("urgent")).toBe("Urgent")
    expect(mapUrgency("routine")).toBe("Routine")
    expect(mapUrgency("estimate")).toBe("Estimate")
  })

  it("falls back to Routine for unknown and null values", () => {
    expect(mapUrgency("unexpected")).toBe("Routine")
    expect(mapUrgency(null)).toBe("Routine")
  })
})

describe("parseTranscript", () => {
  it("parses Agent and User lines", () => {
    expect(
      parseTranscript("Agent: Hello there\nUser: Need AC help")
    ).toEqual([
      { role: "agent", content: "Hello there" },
      { role: "user", content: "Need AC help" },
    ])
  })

  it("skips unrecognized lines", () => {
    expect(
      parseTranscript(
        "System: ignored\nAgent: Hello there\nRandom text\nUser: Need AC help"
      )
    ).toEqual([
      { role: "agent", content: "Hello there" },
      { role: "user", content: "Need AC help" },
    ])
  })

  it("returns an empty array for empty or whitespace-only input", () => {
    expect(parseTranscript("")).toEqual([])
    expect(parseTranscript("   \n\t  ")).toEqual([])
  })
})
