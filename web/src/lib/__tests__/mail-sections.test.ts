import { describe, expect, it } from "vitest"
import { assignBucket, type TriageableCall } from "../triage"
import {
  getDisplaySection,
  getDefaultSelectedId,
  orderCallsForMail,
} from "../mail-sections"

function makeCall(overrides: Partial<TriageableCall> = {}): TriageableCall {
  return {
    id: "call-1",
    appointmentBooked: false,
    endCallReason: null,
    callbackOutcome: null,
    isSafetyEmergency: false,
    isUrgentEscalation: false,
    urgency: "Routine",
    problemDescription: "",
    hvacIssueType: null,
    callbackType: null,
    callbackWindowStart: null,
    callbackWindowEnd: null,
    callbackOutcomeAt: null,
    callerType: null,
    primaryIntent: null,
    route: null,
    revenueTier: null,
    extractionStatus: null,
    createdAt: new Date().toISOString(),
    ...overrides,
  }
}

describe("getDisplaySection", () => {
  it("maps escalated handled calls to ESCALATED_BY_AI", () => {
    const call = makeCall({ isSafetyEmergency: true })
    expect(getDisplaySection(call, assignBucket(call))).toBe("ESCALATED_BY_AI")
  })

  it("maps booked handled calls to BOOKED_BY_AI", () => {
    const call = makeCall({ appointmentBooked: true })
    expect(getDisplaySection(call, assignBucket(call))).toBe("BOOKED_BY_AI")
  })

  it("maps wrong-number handled calls to OTHER_AI_HANDLED", () => {
    const call = makeCall({ endCallReason: "wrong_number" })
    expect(getDisplaySection(call, assignBucket(call))).toBe("OTHER_AI_HANDLED")
  })

  it("maps non-customer handled calls to OTHER_AI_HANDLED", () => {
    const call = makeCall({ route: "spam" })
    expect(getDisplaySection(call, assignBucket(call))).toBe("OTHER_AI_HANDLED")
  })

  it("maps resolved handled calls to OTHER_AI_HANDLED", () => {
    const call = makeCall({ callbackOutcome: "reached_customer" })
    expect(getDisplaySection(call, assignBucket(call))).toBe("OTHER_AI_HANDLED")
  })

  it("lets escalation win over booking when both signals appear", () => {
    const call = makeCall({ appointmentBooked: true, isSafetyEmergency: true })
    expect(getDisplaySection(call, assignBucket(call))).toBe("ESCALATED_BY_AI")
  })
})

describe("getDefaultSelectedId", () => {
  it("prefers escalated over actionable and booked", () => {
    const calls = [
      makeCall({ id: "booked", appointmentBooked: true }),
      makeCall({ id: "lead" }),
      makeCall({ id: "urgent", isSafetyEmergency: true }),
    ]
    expect(getDefaultSelectedId(calls)).toBe("urgent")
  })

  it("falls back to booked, then other handled, then null", () => {
    expect(getDefaultSelectedId([makeCall({ id: "booked", appointmentBooked: true })])).toBe("booked")
    expect(getDefaultSelectedId([makeCall({ id: "wrong", endCallReason: "wrong_number" })])).toBe("wrong")
    expect(getDefaultSelectedId([])).toBeNull()
  })

  it("picks the newest escalated item when multiple escalations exist", () => {
    const calls = [
      makeCall({ id: "older-escalated", isSafetyEmergency: true, createdAt: "2026-03-27T10:00:00.000Z" }),
      makeCall({ id: "newer-escalated", isSafetyEmergency: true, createdAt: "2026-03-27T11:00:00.000Z" }),
    ]
    expect(getDefaultSelectedId(calls)).toBe("newer-escalated")
  })

  it("picks the newest booked item when booked is the highest available section", () => {
    const calls = [
      makeCall({ id: "older-booked", appointmentBooked: true, createdAt: "2026-03-27T10:00:00.000Z" }),
      makeCall({ id: "newer-booked", appointmentBooked: true, createdAt: "2026-03-27T11:00:00.000Z" }),
    ]
    expect(getDefaultSelectedId(calls)).toBe("newer-booked")
  })

  it("picks the newest other-handled item when that is the only section", () => {
    const calls = [
      makeCall({ id: "older-other", endCallReason: "wrong_number", createdAt: "2026-03-27T10:00:00.000Z" }),
      makeCall({ id: "newer-other", route: "spam", createdAt: "2026-03-27T11:00:00.000Z" }),
    ]
    expect(getDefaultSelectedId(calls)).toBe("newer-other")
  })
})

describe("orderCallsForMail", () => {
  it("orders sections as escalated, new leads, follow-ups, booked, other handled", () => {
    const calls = [
      makeCall({ id: "other", endCallReason: "wrong_number" }),
      makeCall({ id: "booked", appointmentBooked: true }),
      makeCall({ id: "follow", endCallReason: "callback_later" }),
      makeCall({ id: "lead" }),
      makeCall({ id: "escalated", isSafetyEmergency: true }),
    ]

    expect(orderCallsForMail(calls).map((call) => call.id)).toEqual([
      "escalated",
      "lead",
      "follow",
      "booked",
      "other",
    ])
  })

  it("orders handled sections newest-first within each section", () => {
    const calls = [
      makeCall({ id: "older-booked", appointmentBooked: true, createdAt: "2026-03-27T10:00:00.000Z" }),
      makeCall({ id: "newer-booked", appointmentBooked: true, createdAt: "2026-03-27T11:00:00.000Z" }),
      makeCall({ id: "older-escalated", isSafetyEmergency: true, createdAt: "2026-03-27T08:00:00.000Z" }),
      makeCall({ id: "newer-escalated", isSafetyEmergency: true, createdAt: "2026-03-27T09:00:00.000Z" }),
    ]

    expect(orderCallsForMail(calls).map((call) => call.id)).toEqual([
      "newer-escalated",
      "older-escalated",
      "newer-booked",
      "older-booked",
    ])
  })
})
