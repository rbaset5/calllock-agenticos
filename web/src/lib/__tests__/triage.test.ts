import { describe, it, expect } from "vitest"
import {
  isUnresolved,
  computeTriage,
  getAssistTemplate,
  triageSort,
  assignBucket,
  followUpSort,
  isHotFollowUp,
  isActionable,
  getCallbackReason,
  getFollowUpSubtype,
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

describe("getCallbackReason", () => {
  it("returns booking_failed when endCallReason is booking_failed", () => {
    expect(getCallbackReason(makeCall({ endCallReason: "booking_failed" }))).toBe("Booking failed")
  })

  it("returns AI promised callback when endCallReason is callback_later", () => {
    expect(getCallbackReason(makeCall({ endCallReason: "callback_later" }))).toBe("AI promised callback")
  })

  it("returns AI promised callback when callbackType is set", () => {
    expect(getCallbackReason(makeCall({ callbackType: "schedule_callback" }))).toBe("AI promised callback")
  })

  it("returns urgent needs details when urgent call has no concrete details", () => {
    expect(
      getCallbackReason(
        makeCall({
          urgency: "Urgent",
          problemDescription: "",
          hvacIssueType: null,
        })
      )
    ).toBe("Urgent, needs details")
  })

  it("returns null when no callback reason applies", () => {
    expect(getCallbackReason(makeCall({ urgency: "Routine", problemDescription: "Capacitor issue" }))).toBeNull()
  })

  it("uses first-match precedence: booking_failed beats callbackType", () => {
    expect(
      getCallbackReason(
        makeCall({
          endCallReason: "booking_failed",
          callbackType: "schedule_callback",
        })
      )
    ).toBe("Booking failed")
  })
})

describe("getFollowUpSubtype", () => {
  it("returns booking_failed for booking_failed endCallReason", () => {
    expect(getFollowUpSubtype(makeCall({ endCallReason: "booking_failed" }))).toBe("booking_failed")
  })

  it("returns complaint for complaint intent", () => {
    expect(getFollowUpSubtype(makeCall({ primaryIntent: "complaint" }))).toBe("complaint")
  })

  it("returns active_job_issue for active job issue intent", () => {
    expect(getFollowUpSubtype(makeCall({ primaryIntent: "active_job_issue" }))).toBe("active_job_issue")
  })

  it("returns promised_callback for callback_later endCallReason", () => {
    expect(getFollowUpSubtype(makeCall({ endCallReason: "callback_later" }))).toBe("promised_callback")
  })

  it("returns promised_callback for callbackType", () => {
    expect(getFollowUpSubtype(makeCall({ callbackType: "schedule_callback" }))).toBe("promised_callback")
  })

  it("returns retry_voicemail for left_voicemail outcome", () => {
    expect(getFollowUpSubtype(makeCall({ callbackOutcome: "left_voicemail" }))).toBe("retry_voicemail")
  })

  it("returns retry_no_answer for no_answer outcome", () => {
    expect(getFollowUpSubtype(makeCall({ callbackOutcome: "no_answer" }))).toBe("retry_no_answer")
  })

  it("returns generic_followup when no subtype matches", () => {
    expect(getFollowUpSubtype(makeCall({ primaryIntent: "followup" }))).toBe("generic_followup")
  })

  it("uses first-match precedence when multiple follow-up signals exist", () => {
    expect(
      getFollowUpSubtype(
        makeCall({
          endCallReason: "booking_failed",
          primaryIntent: "complaint",
          callbackOutcome: "no_answer",
        })
      )
    ).toBe("booking_failed")
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

// ---------------------------------------------------------------------------
// assignBucket
// ---------------------------------------------------------------------------

describe("assignBucket", () => {
  // Rule 1: terminal callbackOutcome → AI_HANDLED resolved
  it("reached_customer → AI_HANDLED resolved", () => {
    const r = assignBucket(makeCall({ callbackOutcome: "reached_customer" }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("resolved")
  })

  it("scheduled → AI_HANDLED resolved", () => {
    const r = assignBucket(makeCall({ callbackOutcome: "scheduled" }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("resolved")
  })

  it("resolved_elsewhere → AI_HANDLED resolved", () => {
    const r = assignBucket(makeCall({ callbackOutcome: "resolved_elsewhere" }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("resolved")
  })

  // Rule 2: route spam/vendor
  it("route=spam → AI_HANDLED non_customer", () => {
    const r = assignBucket(makeCall({ route: "spam" }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("non_customer")
  })

  it("route=vendor → AI_HANDLED non_customer", () => {
    const r = assignBucket(makeCall({ route: "vendor" }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("non_customer")
  })

  // Rule 3: non-service caller types
  it("callerType=job_applicant → AI_HANDLED non_customer", () => {
    const r = assignBucket(makeCall({ callerType: "job_applicant" }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("non_customer")
  })

  it("callerType=spam → AI_HANDLED non_customer", () => {
    const r = assignBucket(makeCall({ callerType: "spam" }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("non_customer")
  })

  // Rule 4: wrong number / out of area
  it("endCallReason=wrong_number → AI_HANDLED wrong_number", () => {
    const r = assignBucket(makeCall({ endCallReason: "wrong_number" }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("wrong_number")
  })

  it("endCallReason=out_of_area → AI_HANDLED wrong_number", () => {
    const r = assignBucket(makeCall({ endCallReason: "out_of_area" }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("wrong_number")
  })

  // Rule 5: emergencies
  it("isSafetyEmergency → AI_HANDLED escalated with marker", () => {
    const r = assignBucket(makeCall({ isSafetyEmergency: true }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("escalated")
    expect(r.escalationMarker).toBe(true)
  })

  it("urgency=LifeSafety → AI_HANDLED escalated with marker", () => {
    const r = assignBucket(makeCall({ urgency: "LifeSafety" }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.escalationMarker).toBe(true)
  })

  // Rule 6: appointment booked
  it("appointmentBooked → AI_HANDLED booked", () => {
    const r = assignBucket(makeCall({ appointmentBooked: true }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("booked")
  })

  // Rule 7: terminal endCallReason
  it("endCallReason=cancelled → AI_HANDLED resolved", () => {
    const r = assignBucket(makeCall({ endCallReason: "cancelled" }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("resolved")
  })

  // Rule 8: leads
  it("endCallReason=waitlist_added → ACTION_QUEUE NEW_LEAD", () => {
    const r = assignBucket(makeCall({ endCallReason: "waitlist_added" }))
    expect(r.bucket).toBe("ACTION_QUEUE")
    expect(r.subGroup).toBe("NEW_LEAD")
  })

  it("endCallReason=sales_lead → ACTION_QUEUE NEW_LEAD", () => {
    const r = assignBucket(makeCall({ endCallReason: "sales_lead" }))
    expect(r.bucket).toBe("ACTION_QUEUE")
    expect(r.subGroup).toBe("NEW_LEAD")
  })

  // Rule 9: legacy follow-up signals
  it("endCallReason=callback_later → ACTION_QUEUE FOLLOW_UP", () => {
    const r = assignBucket(makeCall({ endCallReason: "callback_later" }))
    expect(r.bucket).toBe("ACTION_QUEUE")
    expect(r.subGroup).toBe("FOLLOW_UP")
  })

  it("endCallReason=booking_failed → ACTION_QUEUE FOLLOW_UP", () => {
    const r = assignBucket(makeCall({ endCallReason: "booking_failed" }))
    expect(r.bucket).toBe("ACTION_QUEUE")
    expect(r.subGroup).toBe("FOLLOW_UP")
  })

  // Rule 10: follow-up intents
  it("primaryIntent=followup → ACTION_QUEUE FOLLOW_UP", () => {
    const r = assignBucket(makeCall({ primaryIntent: "followup" }))
    expect(r.bucket).toBe("ACTION_QUEUE")
    expect(r.subGroup).toBe("FOLLOW_UP")
  })

  it("primaryIntent=complaint → ACTION_QUEUE FOLLOW_UP", () => {
    const r = assignBucket(makeCall({ primaryIntent: "complaint" }))
    expect(r.bucket).toBe("ACTION_QUEUE")
    expect(r.subGroup).toBe("FOLLOW_UP")
  })

  it("primaryIntent=active_job_issue → ACTION_QUEUE FOLLOW_UP", () => {
    const r = assignBucket(makeCall({ primaryIntent: "active_job_issue" }))
    expect(r.bucket).toBe("ACTION_QUEUE")
    expect(r.subGroup).toBe("FOLLOW_UP")
  })

  // Rule 11: retry outcomes
  it("callbackOutcome=left_voicemail → ACTION_QUEUE FOLLOW_UP", () => {
    const r = assignBucket(makeCall({ callbackOutcome: "left_voicemail" }))
    expect(r.bucket).toBe("ACTION_QUEUE")
    expect(r.subGroup).toBe("FOLLOW_UP")
  })

  it("callbackOutcome=no_answer → ACTION_QUEUE FOLLOW_UP", () => {
    const r = assignBucket(makeCall({ callbackOutcome: "no_answer" }))
    expect(r.bucket).toBe("ACTION_QUEUE")
    expect(r.subGroup).toBe("FOLLOW_UP")
  })

  // Rule 12: default
  it("default (all nulls) → ACTION_QUEUE NEW_LEAD", () => {
    const r = assignBucket(makeCall())
    expect(r.bucket).toBe("ACTION_QUEUE")
    expect(r.subGroup).toBe("NEW_LEAD")
  })

  // Backward compat: null classification fields
  it("null classification fields → ACTION_QUEUE NEW_LEAD", () => {
    const r = assignBucket(makeCall({
      callerType: null,
      primaryIntent: null,
      route: null,
      revenueTier: null,
    }))
    expect(r.bucket).toBe("ACTION_QUEUE")
    expect(r.subGroup).toBe("NEW_LEAD")
  })

  // Extraction guard
  it("extraction_status=pending + null classification → NEW_LEAD (not classified)", () => {
    const r = assignBucket(makeCall({
      extractionStatus: "pending",
      callerType: null,
      primaryIntent: null,
      route: null,
    }))
    expect(r.bucket).toBe("ACTION_QUEUE")
    expect(r.subGroup).toBe("NEW_LEAD")
  })

  it("extraction_status=pending + route=spam → AI_HANDLED (classification present)", () => {
    const r = assignBucket(makeCall({
      extractionStatus: "pending",
      route: "spam",
    }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("non_customer")
  })
})

// ---------------------------------------------------------------------------
// followUpSort
// ---------------------------------------------------------------------------

describe("followUpSort", () => {
  it("booking_failed sorts first (highest conversion likelihood)", () => {
    const retry = makeCall({ id: "retry", callbackOutcome: "no_answer" })
    const booking = makeCall({ id: "booking", endCallReason: "booking_failed" })
    const complaint = makeCall({ id: "complaint", primaryIntent: "complaint" })
    const sorted = followUpSort([retry, complaint, booking])
    expect(sorted[0].id).toBe("booking")
  })

  it("complaint sorts before AI-promised callback", () => {
    const promised = makeCall({ id: "promised", callbackType: "schedule_callback" })
    const complaint = makeCall({ id: "complaint", primaryIntent: "complaint" })
    const sorted = followUpSort([promised, complaint])
    expect(sorted[0].id).toBe("complaint")
  })

  it("active_job_issue sorts before retry", () => {
    const retry = makeCall({ id: "retry", callbackOutcome: "no_answer" })
    const active = makeCall({ id: "active", primaryIntent: "active_job_issue" })
    const sorted = followUpSort([retry, active])
    expect(sorted[0].id).toBe("active")
  })

  it("AI-promised callback sorts before retry", () => {
    const retry = makeCall({ id: "retry", callbackOutcome: "left_voicemail" })
    const promised = makeCall({ id: "promised", endCallReason: "callback_later" })
    const sorted = followUpSort([retry, promised])
    expect(sorted[0].id).toBe("promised")
  })

  it("retry sorts before generic followup", () => {
    const generic = makeCall({ id: "generic", primaryIntent: "followup" })
    const retry = makeCall({ id: "retry", callbackOutcome: "no_answer" })
    const sorted = followUpSort([generic, retry])
    expect(sorted[0].id).toBe("retry")
  })

  it("full ordering: booking_failed > complaint > AI-promised > retry > generic", () => {
    const generic = makeCall({ id: "generic", primaryIntent: "followup" })
    const retry = makeCall({ id: "retry", callbackOutcome: "left_voicemail" })
    const promised = makeCall({ id: "promised", callbackType: "schedule_callback" })
    const complaint = makeCall({ id: "complaint", primaryIntent: "complaint" })
    const booking = makeCall({ id: "booking", endCallReason: "booking_failed" })
    const sorted = followUpSort([generic, retry, promised, complaint, booking])
    expect(sorted.map(c => c.id)).toEqual(["booking", "complaint", "promised", "retry", "generic"])
  })

  it("within same tier: newest first", () => {
    const older = makeCall({ id: "older", endCallReason: "booking_failed", createdAt: "2026-03-27T10:00:00Z" })
    const newer = makeCall({ id: "newer", endCallReason: "booking_failed", createdAt: "2026-03-27T14:00:00Z" })
    const sorted = followUpSort([older, newer])
    expect(sorted[0].id).toBe("newer")
  })

  it("handles null primaryIntent without crashing", () => {
    const call = makeCall({ primaryIntent: null })
    expect(() => followUpSort([call])).not.toThrow()
  })

  it("handles null callbackOutcome without crashing", () => {
    const call = makeCall({ callbackOutcome: null })
    expect(() => followUpSort([call])).not.toThrow()
  })
})

// ---------------------------------------------------------------------------
// isHotFollowUp
// ---------------------------------------------------------------------------

describe("isHotFollowUp", () => {
  it("booking_failed is hot", () => {
    expect(isHotFollowUp(makeCall({ endCallReason: "booking_failed" }))).toBe(true)
  })

  it("complaint is hot", () => {
    expect(isHotFollowUp(makeCall({ primaryIntent: "complaint" }))).toBe(true)
  })

  it("active_job_issue is hot", () => {
    expect(isHotFollowUp(makeCall({ primaryIntent: "active_job_issue" }))).toBe(true)
  })

  it("left_voicemail is NOT hot", () => {
    expect(isHotFollowUp(makeCall({ callbackOutcome: "left_voicemail" }))).toBe(false)
  })

  it("callback_later is NOT hot", () => {
    expect(isHotFollowUp(makeCall({ endCallReason: "callback_later" }))).toBe(false)
  })

  it("generic followup is NOT hot", () => {
    expect(isHotFollowUp(makeCall({ primaryIntent: "followup" }))).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// isActionable
// ---------------------------------------------------------------------------

describe("isActionable", () => {
  it("default call (NEW_LEAD) is actionable", () => {
    expect(isActionable(makeCall())).toBe(true)
  })

  it("spam call (AI_HANDLED) is not actionable", () => {
    expect(isActionable(makeCall({ route: "spam" }))).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// assignBucket — mail-section regression cases
// ---------------------------------------------------------------------------

describe("assignBucket mail-section regressions", () => {
  it("safety emergency stays AI_HANDLED with handledReason=escalated", () => {
    const r = assignBucket(makeCall({ isSafetyEmergency: true }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("escalated")
  })

  it("appointmentBooked stays AI_HANDLED with handledReason=booked", () => {
    const r = assignBucket(makeCall({ appointmentBooked: true }))
    expect(r.bucket).toBe("AI_HANDLED")
    expect(r.handledReason).toBe("booked")
  })
})
