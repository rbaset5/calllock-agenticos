import { describe, expect, it } from "vitest"
import type { Call } from "@/types/call"
import { buildAISummary, getHandledSummary } from "../mail-copy"
import { assignBucket } from "@/lib/triage"

function makeCall(overrides: Partial<Call> = {}): Call {
  return {
    id: "call-1",
    customerName: "Avery",
    customerPhone: "15551234567",
    serviceAddress: "123 Main St",
    problemDescription: "",
    urgency: "Routine",
    hvacIssueType: null,
    equipmentType: "",
    equipmentBrand: "",
    equipmentAge: "",
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
    createdAt: new Date().toISOString(),
    ...overrides,
  }
}

describe("getHandledSummary", () => {
  it("returns success-forward copy for booked calls", () => {
    const call = makeCall({
      appointmentBooked: true,
      appointmentDateTime: "2026-03-27T16:30:00.000Z",
    })
    expect(getHandledSummary(call, assignBucket(call))).toContain("Appointment secured")
  })

  it("returns escalation-forward copy for escalated calls", () => {
    const call = makeCall({ isSafetyEmergency: true })
    expect(getHandledSummary(call, assignBucket(call))).toContain("Safety emergency escalated")
  })

  it("preserves wrong-number detail copy", () => {
    const call = makeCall({ endCallReason: "wrong_number" })
    expect(getHandledSummary(call, assignBucket(call))).toContain("wrong number")
  })

  it("preserves non-customer detail copy", () => {
    const call = makeCall({ route: "spam" })
    expect(getHandledSummary(call, assignBucket(call))).toContain("non-customer")
  })
})

describe("buildAISummary", () => {
  it("uses booked language in the AI receptionist summary", () => {
    const call = makeCall({ appointmentBooked: true })
    expect(buildAISummary(call)).toContain("appointment was successfully scheduled")
  })

  it("uses escalation language in the AI receptionist summary", () => {
    const call = makeCall({ isSafetyEmergency: true, problemDescription: "Smell of gas" })
    expect(buildAISummary(call)).toContain("escalated")
  })
})
