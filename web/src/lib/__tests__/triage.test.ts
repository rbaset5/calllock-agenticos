import { describe, it, expect } from "vitest"
import {
  isUnresolved,
  computeTriage,
  getAssistTemplate,
  triageSort,
  type TriageableCall,
} from "../triage"

function makeCall(overrides: Partial<TriageableCall> = {}): TriageableCall {
  return {
    id: "test-1",
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
    createdAt: new Date().toISOString(),
    ...overrides,
  }
}

describe("isUnresolved", () => {
  it("basic unresolved call returns true", () => {
    expect(isUnresolved(makeCall())).toBe(true)
  })

  it("appointmentBooked returns false", () => {
    expect(isUnresolved(makeCall({ appointmentBooked: true }))).toBe(false)
  })

  it.each([
    "wrong_number" as const,
    "out_of_area" as const,
    "cancelled" as const,
    "completed" as const,
  ])("terminal endCallReason '%s' returns false", (reason) => {
    expect(isUnresolved(makeCall({ endCallReason: reason }))).toBe(false)
  })

  it.each(["callback_later" as const, "booking_failed" as const])(
    "non-terminal endCallReason '%s' returns true",
    (reason) => {
      expect(isUnresolved(makeCall({ endCallReason: reason }))).toBe(true)
    }
  )

  it.each([
    "reached_customer" as const,
    "scheduled" as const,
    "resolved_elsewhere" as const,
  ])("terminal callbackOutcome '%s' returns false", (outcome) => {
    expect(isUnresolved(makeCall({ callbackOutcome: outcome }))).toBe(false)
  })

  it.each(["left_voicemail" as const, "no_answer" as const])(
    "non-terminal callbackOutcome '%s' returns true",
    (outcome) => {
      expect(isUnresolved(makeCall({ callbackOutcome: outcome }))).toBe(true)
    }
  )

  it("rescheduled endCallReason returns false", () => {
    expect(
      isUnresolved(makeCall({ endCallReason: "rescheduled" }))
    ).toBe(false)
  })

  it("outcome edit transition: no_answer (true) -> reached_customer (false)", () => {
    const call = makeCall({ callbackOutcome: "no_answer" })
    expect(isUnresolved(call)).toBe(true)
    const updated = { ...call, callbackOutcome: "reached_customer" as const }
    expect(isUnresolved(updated)).toBe(false)
  })
})

describe("computeTriage", () => {
  const now = Date.now()

  it("safety emergency -> Call now", () => {
    const result = computeTriage(makeCall({ isSafetyEmergency: true }), now)
    expect(result.command).toBe("Call now")
  })

  it("LifeSafety urgency -> Call now", () => {
    const result = computeTriage(makeCall({ urgency: "LifeSafety" }), now)
    expect(result.command).toBe("Call now")
  })

  it("urgent escalation -> Call now", () => {
    const result = computeTriage(makeCall({ isUrgentEscalation: true }), now)
    expect(result.command).toBe("Call now")
  })

  it("Urgent + concrete issue -> Call now", () => {
    const result = computeTriage(
      makeCall({ urgency: "Urgent", problemDescription: "AC leaking water" }),
      now
    )
    expect(result.command).toBe("Call now")
  })

  it("Urgent without detail -> Next up", () => {
    const result = computeTriage(makeCall({ urgency: "Urgent" }), now)
    expect(result.command).toBe("Next up")
  })

  it("callback_later -> Next up", () => {
    const result = computeTriage(
      makeCall({ endCallReason: "callback_later" }),
      now
    )
    expect(result.command).toBe("Next up")
  })

  it("booking_failed -> Next up", () => {
    const result = computeTriage(
      makeCall({ endCallReason: "booking_failed" }),
      now
    )
    expect(result.command).toBe("Next up")
  })

  it("callbackType present -> Next up", () => {
    const result = computeTriage(
      makeCall({ callbackType: "schedule_callback" }),
      now
    )
    expect(result.command).toBe("Next up")
  })

  it("Estimate -> Today", () => {
    const result = computeTriage(makeCall({ urgency: "Estimate" }), now)
    expect(result.command).toBe("Today")
  })

  it("Routine + concrete issue -> Today", () => {
    const result = computeTriage(
      makeCall({ problemDescription: "Thermostat not responding" }),
      now
    )
    expect(result.command).toBe("Today")
  })

  it("low-info call -> Can wait", () => {
    const result = computeTriage(makeCall(), now)
    expect(result.command).toBe("Can wait")
  })

  it("evidence string is <= 40 chars", () => {
    const result = computeTriage(
      makeCall({ isSafetyEmergency: true, problemDescription: "Gas leak detected in basement of the house which is very dangerous" }),
      now
    )
    expect(result.evidence.length).toBeLessThanOrEqual(40)
  })

  it("stale Call now after 15 min", () => {
    const old = new Date(now - 16 * 60 * 1000).toISOString()
    const result = computeTriage(
      makeCall({ isSafetyEmergency: true, createdAt: old }),
      now
    )
    expect(result.isStale).toBe(true)
  })

  it("not stale Call now under 15 min", () => {
    const recent = new Date(now - 5 * 60 * 1000).toISOString()
    const result = computeTriage(
      makeCall({ isSafetyEmergency: true, createdAt: recent }),
      now
    )
    expect(result.isStale).toBe(false)
  })

  it("stale Next up after 60 min", () => {
    const old = new Date(now - 61 * 60 * 1000).toISOString()
    const result = computeTriage(
      makeCall({ endCallReason: "callback_later", createdAt: old }),
      now
    )
    expect(result.isStale).toBe(true)
  })

  it("Today never stale", () => {
    const old = new Date(now - 24 * 60 * 60 * 1000).toISOString()
    const result = computeTriage(
      makeCall({ urgency: "Estimate", createdAt: old }),
      now
    )
    expect(result.isStale).toBe(false)
  })

  it("Can wait never stale", () => {
    const old = new Date(now - 24 * 60 * 60 * 1000).toISOString()
    const result = computeTriage(makeCall({ createdAt: old }), now)
    expect(result.isStale).toBe(false)
  })

  it("valid future callback window", () => {
    const futureStart = new Date(now + 60 * 60 * 1000).toISOString()
    const futureEnd = new Date(now + 2 * 60 * 60 * 1000).toISOString()
    const result = computeTriage(
      makeCall({
        callbackWindowStart: futureStart,
        callbackWindowEnd: futureEnd,
        callbackType: "schedule_callback",
      }),
      now
    )
    expect(result.callbackWindowValid).toBe(true)
  })

  it("past callback window is invalid", () => {
    const pastStart = new Date(now - 3 * 60 * 60 * 1000).toISOString()
    const pastEnd = new Date(now - 2 * 60 * 60 * 1000).toISOString()
    const result = computeTriage(
      makeCall({
        callbackWindowStart: pastStart,
        callbackWindowEnd: pastEnd,
        callbackType: "schedule_callback",
      }),
      now
    )
    expect(result.callbackWindowValid).toBe(false)
  })

  it("missing callback window is invalid", () => {
    const result = computeTriage(makeCall(), now)
    expect(result.callbackWindowValid).toBe(false)
  })
})

describe("getAssistTemplate", () => {
  it("known reason contains relevant keyword", () => {
    expect(getAssistTemplate("no_cooling")).toContain("cooling")
    expect(getAssistTemplate("no_heating")).toContain("heating")
    expect(getAssistTemplate("estimate_request")).toContain("estimate")
    expect(getAssistTemplate("callback_requested")).toContain("returning")
    expect(getAssistTemplate("booking_failed")).toContain("appointment")
    expect(getAssistTemplate("urgent_escalation")).toContain("urgent")
  })

  it("generic fallback has content", () => {
    const tmpl = getAssistTemplate("generic_service_issue")
    expect(tmpl.length).toBeGreaterThan(0)
    expect(tmpl).toContain("following up")
  })

  it("accepts companyName param and substitutes [Company]", () => {
    const tmpl = getAssistTemplate("no_cooling", "Arctic Air HVAC")
    expect(tmpl).toContain("Arctic Air HVAC")
    expect(tmpl).not.toContain("[Company]")
  })
})

describe("triageSort", () => {
  const now = Date.now()

  it("Call now before Next up", () => {
    const callNow = makeCall({
      id: "a",
      isSafetyEmergency: true,
      createdAt: new Date(now).toISOString(),
    })
    const nextUp = makeCall({
      id: "b",
      endCallReason: "callback_later",
      createdAt: new Date(now).toISOString(),
    })
    const sorted = triageSort([nextUp, callNow], now)
    expect(sorted[0].id).toBe("a")
    expect(sorted[1].id).toBe("b")
  })

  it("stale before fresh in same bucket", () => {
    const stale = makeCall({
      id: "stale",
      isSafetyEmergency: true,
      createdAt: new Date(now - 20 * 60 * 1000).toISOString(),
    })
    const fresh = makeCall({
      id: "fresh",
      isSafetyEmergency: true,
      createdAt: new Date(now - 5 * 60 * 1000).toISOString(),
    })
    const sorted = triageSort([fresh, stale], now)
    expect(sorted[0].id).toBe("stale")
    expect(sorted[1].id).toBe("fresh")
  })

  it("valid callback window before no-window in same bucket", () => {
    const withWindow = makeCall({
      id: "windowed",
      endCallReason: "callback_later",
      callbackWindowStart: new Date(now + 60 * 60 * 1000).toISOString(),
      callbackWindowEnd: new Date(now + 2 * 60 * 60 * 1000).toISOString(),
      createdAt: new Date(now).toISOString(),
    })
    const noWindow = makeCall({
      id: "no-window",
      endCallReason: "callback_later",
      createdAt: new Date(now).toISOString(),
    })
    const sorted = triageSort([noWindow, withWindow], now)
    expect(sorted[0].id).toBe("windowed")
    expect(sorted[1].id).toBe("no-window")
  })

  it("signal rank: safety emergency before urgent escalation in same bucket", () => {
    const safety = makeCall({
      id: "safety",
      isSafetyEmergency: true,
      createdAt: new Date(now).toISOString(),
    })
    const urgent = makeCall({
      id: "urgent",
      isUrgentEscalation: true,
      createdAt: new Date(now).toISOString(),
    })
    const sorted = triageSort([urgent, safety], now)
    expect(sorted[0].id).toBe("safety")
    expect(sorted[1].id).toBe("urgent")
  })

  it("recency tiebreak: newer first among identical Can wait calls", () => {
    const older = makeCall({
      id: "older",
      createdAt: new Date(now - 10 * 60 * 1000).toISOString(),
    })
    const newer = makeCall({
      id: "newer",
      createdAt: new Date(now - 2 * 60 * 1000).toISOString(),
    })
    const sorted = triageSort([older, newer], now)
    expect(sorted[0].id).toBe("newer")
    expect(sorted[1].id).toBe("older")
  })
})

describe("isUnresolved — phone-field independence", () => {
  it("call with no customerPhone field is still unresolved (phone does not affect triage)", () => {
    // TriageableCall has no customerPhone — triage is phone-agnostic
    const call = makeCall()
    expect(isUnresolved(call)).toBe(true)
  })

  it("call with reached_customer terminal outcome is resolved", () => {
    expect(isUnresolved(makeCall({ callbackOutcome: "reached_customer" }))).toBe(false)
  })
})

describe("computeTriage — resolved call", () => {
  it("resolved call (appointmentBooked) has isUnresolved=false and command 'Can wait'", () => {
    const call = makeCall({ appointmentBooked: true })
    expect(isUnresolved(call)).toBe(false)
    const result = computeTriage(call, Date.now())
    // resolved calls fall through to Can wait (no active signal)
    expect(result.command).toBe("Can wait")
    expect(result.isUnresolved).toBe(false)
  })
})

describe("getAssistTemplate", () => {
  const reasons = [
    "no_cooling",
    "no_heating",
    "estimate_request",
    "callback_requested",
    "booking_failed",
    "urgent_escalation",
    "generic_service_issue",
  ] as const

  it.each(reasons)("reason '%s' returns a non-empty template string", (reason) => {
    const template = getAssistTemplate(reason, "TestCo")
    expect(typeof template).toBe("string")
    expect(template.length).toBeGreaterThan(0)
    expect(template).toContain("TestCo")
  })
})
