import { describe, it, expect } from "vitest"
import { transformCallSession } from "../transforms"
import type { CallSessionRow } from "@/types/call"

describe("transformCallSession", () => {
  const emptyReadIds = new Set<string>()

  it("extracts all fields from a complete conversation_state", () => {
    const row: CallSessionRow = {
      call_id: "call_123",
      conversation_state: {
        callId: "call_123",
        customerName: "Janice",
        customerPhone: "+15125551234",
        serviceAddress: "1211 Squawk Street",
        problemDescription: "AC blowing warm air",
        urgencyTier: "Urgent",
        hvacIssueType: "Cooling",
        equipmentType: "AC unit",
        equipmentBrand: "Carrier",
        equipmentAge: "10 years",
        appointmentBooked: true,
        appointmentDateTime: "2026-03-10T08:00:00",
        endCallReason: "completed",
        isSafetyEmergency: false,
        isUrgentEscalation: true,
        callbackType: "service",
      },
      retell_data: {
        call: {
          transcript_object: [
            { role: "agent", content: "Thanks for calling ACE Cooling" },
            { role: "user", content: "My AC is blowing warm air" },
          ],
        },
      },
      synced_to_dashboard: true,
      created_at: "2026-03-05T10:00:00Z",
    }

    const call = transformCallSession(row, emptyReadIds)

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
    expect(call.transcript).toHaveLength(2)
    expect(call.transcript[0].role).toBe("agent")
    expect(call.callbackType).toBe("service")
    expect(call.read).toBe(false)
    expect(call.createdAt).toBe("2026-03-05T10:00:00Z")
  })

  it("handles missing fields with safe defaults", () => {
    const row: CallSessionRow = {
      call_id: "call_empty",
      conversation_state: {},
      synced_to_dashboard: false,
      created_at: "2026-03-05T10:00:00Z",
    }

    const call = transformCallSession(row, emptyReadIds)

    expect(call.id).toBe("call_empty")
    expect(call.customerName).toBe("Unknown Caller")
    expect(call.customerPhone).toBe("")
    expect(call.problemDescription).toBe("")
    expect(call.urgency).toBe("Routine")
    expect(call.hvacIssueType).toBeNull()
    expect(call.appointmentBooked).toBe(false)
    expect(call.appointmentDateTime).toBeNull()
    expect(call.endCallReason).toBeNull()
    expect(call.isSafetyEmergency).toBe(false)
    expect(call.isUrgentEscalation).toBe(false)
    expect(call.transcript).toHaveLength(0)
    expect(call.callbackType).toBeNull()
  })

  it("respects readIds set", () => {
    const row: CallSessionRow = {
      call_id: "call_read",
      conversation_state: {},
      synced_to_dashboard: false,
      created_at: "2026-03-05T10:00:00Z",
    }

    const readIds = new Set(["call_read"])
    const call = transformCallSession(row, readIds)

    expect(call.read).toBe(true)
  })

  it("filters invalid transcript entries", () => {
    const row: CallSessionRow = {
      call_id: "call_bad_transcript",
      conversation_state: {},
      retell_data: {
        call: {
          transcript_object: [
            { role: "agent", content: "Hello" },
            { role: "tool_call_invocation", name: "lookup_caller" },
            null,
            { role: "user", content: "Hi" },
            { role: "user" }, // missing content
          ],
        },
      },
      synced_to_dashboard: false,
      created_at: "2026-03-05T10:00:00Z",
    }

    const call = transformCallSession(row, emptyReadIds)

    expect(call.transcript).toHaveLength(2)
    expect(call.transcript[0].content).toBe("Hello")
    expect(call.transcript[1].content).toBe("Hi")
  })
})
