import { describe, expect, it } from "vitest"
import type { TriageableCall } from "@/lib/triage"

import {
  getInitialSelectedId,
  resolveStoredSelectedId,
} from "../selection-state"

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
    bookingStatus: null,
    createdAt: new Date().toISOString(),
    ...overrides,
  }
}

describe("selection-state", () => {
  it("prefers escalated, then new leads, then follow-ups, then booked, then other handled", () => {
    const calls = [
      makeCall({ id: "other", endCallReason: "wrong_number" }),
      makeCall({ id: "booked", appointmentBooked: true }),
      makeCall({ id: "follow", endCallReason: "callback_later" }),
      makeCall({ id: "lead" }),
      makeCall({ id: "escalated", isSafetyEmergency: true }),
    ]
    expect(getInitialSelectedId(calls)).toBe("escalated")
  })

  it("returns null for empty list", () => {
    expect(getInitialSelectedId([])).toBeNull()
  })

  it("accepts stored id only when present in current calls", () => {
    const calls = [makeCall({ id: "a" }), makeCall({ id: "b" }), makeCall({ id: "c" })]
    expect(resolveStoredSelectedId(calls, "b")).toBe("b")
    expect(resolveStoredSelectedId(calls, "missing")).toBeNull()
    expect(resolveStoredSelectedId(calls, null)).toBeNull()
  })
})
