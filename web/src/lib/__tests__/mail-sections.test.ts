import { describe, expect, it } from "vitest"
import { assignBucket, type TriageableCall } from "../triage"
import {
  countHandledReasons,
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
    bookingStatus: null,
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

  it("maps booked handled calls with no bookingStatus to BOOKINGS", () => {
    const call = makeCall({ appointmentBooked: true, bookingStatus: null })
    expect(getDisplaySection(call, assignBucket(call))).toBe("BOOKINGS")
  })

  it("maps booked calls with confirmed status to BOOKINGS", () => {
    const call = makeCall({ appointmentBooked: true, bookingStatus: "confirmed" })
    expect(getDisplaySection(call, assignBucket(call))).toBe("BOOKINGS")
  })

  it("maps booked calls with rescheduled status to BOOKINGS", () => {
    const call = makeCall({ appointmentBooked: true, bookingStatus: "rescheduled" })
    expect(getDisplaySection(call, assignBucket(call))).toBe("BOOKINGS")
  })

  it("maps booked calls with cancelled status to OTHER_AI_HANDLED", () => {
    const call = makeCall({ appointmentBooked: true, bookingStatus: "cancelled" })
    expect(getDisplaySection(call, assignBucket(call))).toBe("OTHER_AI_HANDLED")
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
    expect(getDefaultSelectedId([makeCall({ id: "confirmed", appointmentBooked: true, bookingStatus: "confirmed" })])).toBe("confirmed")
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
  it("orders sections as escalated, new leads, follow-ups, bookings, other handled", () => {
    const calls = [
      makeCall({ id: "other", endCallReason: "wrong_number" }),
      makeCall({ id: "booked", appointmentBooked: true }),
      makeCall({ id: "confirmed", appointmentBooked: true, bookingStatus: "confirmed" }),
      makeCall({ id: "follow", endCallReason: "callback_later" }),
      makeCall({ id: "lead" }),
      makeCall({ id: "escalated", isSafetyEmergency: true }),
    ]

    expect(orderCallsForMail(calls).map((call) => call.id)).toEqual([
      "escalated",
      "lead",
      "follow",
      "booked",
      "confirmed",
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

  it("sorts bookings: unconfirmed first, then confirmed, then rescheduled (newest first within group)", () => {
    const calls = [
      makeCall({ id: "confirmed-old", appointmentBooked: true, bookingStatus: "confirmed", createdAt: "2026-03-27T10:00:00.000Z" }),
      makeCall({ id: "unconfirmed-new", appointmentBooked: true, bookingStatus: null, createdAt: "2026-03-27T12:00:00.000Z" }),
      makeCall({ id: "confirmed-new", appointmentBooked: true, bookingStatus: "confirmed", createdAt: "2026-03-27T14:00:00.000Z" }),
      makeCall({ id: "unconfirmed-old", appointmentBooked: true, bookingStatus: null, createdAt: "2026-03-27T08:00:00.000Z" }),
    ]

    const ordered = orderCallsForMail(calls)
    const ids = ordered.map((c) => c.id)
    expect(ids).toEqual([
      "unconfirmed-new",
      "unconfirmed-old",
      "confirmed-new",
      "confirmed-old",
    ])
  })
})

describe("countHandledReasons", () => {
  it("counts booked, filtered, resolved, and other correctly for mixed handled calls", () => {
    const booked = makeCall({ id: "booked", appointmentBooked: true })
    const filteredSpam = makeCall({ id: "filtered-spam", route: "spam" })
    const filteredWrongRoute = makeCall({ id: "filtered-vendor", route: "vendor" })
    const resolved = makeCall({ id: "resolved", callbackOutcome: "reached_customer" })
    const escalated = makeCall({ id: "escalated", isSafetyEmergency: true })
    const calls = [booked, filteredSpam, filteredWrongRoute, resolved, escalated]
    const bucketMap = new Map(calls.map((call) => [call.id, assignBucket(call)]))

    expect(countHandledReasons(calls, bucketMap)).toEqual({
      booked: 1,
      filtered: 2,
      resolved: 1,
      other: 1,
    })
  })

  it("returns zeros for empty input", () => {
    expect(countHandledReasons([], new Map())).toEqual({
      booked: 0,
      filtered: 0,
      resolved: 0,
      other: 0,
    })
  })

  it("treats missing bucket assignment as other", () => {
    const loneCall = makeCall({ id: "lone" })
    expect(countHandledReasons([loneCall], new Map())).toEqual({
      booked: 0,
      filtered: 0,
      resolved: 0,
      other: 1,
    })
  })

  it("counts escalated handled calls as other", () => {
    const escalated = makeCall({ id: "esc", isSafetyEmergency: true })
    const bucketMap = new Map([[escalated.id, assignBucket(escalated)]])
    expect(countHandledReasons([escalated], bucketMap)).toEqual({
      booked: 0,
      filtered: 0,
      resolved: 0,
      other: 1,
    })
  })

  it("counts all-same-type sets correctly", () => {
    const a = makeCall({ id: "a", callbackOutcome: "resolved_elsewhere" })
    const b = makeCall({ id: "b", callbackOutcome: "scheduled" })
    const c = makeCall({ id: "c", callbackOutcome: "reached_customer" })
    const calls = [a, b, c]
    const bucketMap = new Map(calls.map((call) => [call.id, assignBucket(call)]))
    expect(countHandledReasons(calls, bucketMap)).toEqual({
      booked: 0,
      filtered: 0,
      resolved: 3,
      other: 0,
    })
  })

  it("handles larger handled sets deterministically", () => {
    const calls = Array.from({ length: 24 }, (_, idx) => {
      if (idx < 6) return makeCall({ id: `booked-${idx}`, appointmentBooked: true })
      if (idx < 12) return makeCall({ id: `filtered-${idx}`, route: idx % 2 === 0 ? "spam" : "vendor" })
      if (idx < 18) return makeCall({ id: `resolved-${idx}`, callbackOutcome: "scheduled" })
      return makeCall({ id: `other-${idx}`, isSafetyEmergency: true })
    })
    const bucketMap = new Map(calls.map((call) => [call.id, assignBucket(call)]))
    expect(countHandledReasons(calls, bucketMap)).toEqual({
      booked: 6,
      filtered: 6,
      resolved: 6,
      other: 6,
    })
  })
})
