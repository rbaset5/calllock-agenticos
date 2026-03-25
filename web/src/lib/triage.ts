import type {
  EndCallReason,
  CallbackOutcome,
  UrgencyTier,
  TriageCommand,
  TriageReason,
  TriageResult,
} from "@/types/call"
import {
  TERMINAL_END_CALL_REASONS,
  TERMINAL_CALLBACK_OUTCOMES,
} from "@/types/call"

// ---------------------------------------------------------------------------
// TriageableCall — the minimal slice of a Call needed for triage
// ---------------------------------------------------------------------------

export interface TriageableCall {
  id: string
  appointmentBooked: boolean
  endCallReason: EndCallReason | null
  callbackOutcome: CallbackOutcome | null
  isSafetyEmergency: boolean
  isUrgentEscalation: boolean
  urgency: UrgencyTier
  problemDescription: string
  hvacIssueType: string | null
  callbackType: string | null
  callbackWindowStart: string | null
  callbackWindowEnd: string | null
  createdAt: string
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COMMAND_RANK: Record<TriageCommand, number> = {
  "Call now": 0,
  "Next up": 1,
  Today: 2,
  "Can wait": 3,
}

const STALE_THRESHOLDS: Partial<Record<TriageCommand, number>> = {
  "Call now": 15,
  "Next up": 60,
}

const SIGNAL_RANK_MAP = {
  safety: 0,
  urgent_escalation: 1,
  follow_up: 2,
  concrete_issue: 3,
  generic: 4,
} as const

type SignalRank = (typeof SIGNAL_RANK_MAP)[keyof typeof SIGNAL_RANK_MAP]

// ---------------------------------------------------------------------------
// Templates
// ---------------------------------------------------------------------------

const TEMPLATES: Record<TriageReason, string> = {
  no_cooling:
    "Hi, this is [Company]. I'm calling about the cooling issue you reported. Can you tell me what's happening with your system right now?",
  no_heating:
    "Hi, this is [Company]. I'm calling about the heating issue you reported. Is your system running at all, or is it completely off?",
  estimate_request:
    "Hi, this is [Company]. I'm following up on your request for an estimate. I'd like to get a few details so we can get you an accurate quote.",
  callback_requested:
    "Hi, this is [Company] returning your call. How can I help you today?",
  booking_failed:
    "Hi, this is [Company]. We had some trouble getting your appointment set up earlier. Let me get that sorted out for you right now.",
  urgent_escalation:
    "Hi, this is [Company]. I understand you have an urgent situation. Can you walk me through what's going on so we can get someone out to you?",
  generic_service_issue:
    "Hi, this is [Company]. I'm following up on your recent call. Can you confirm the issue you're experiencing so we can help?",
}

// ---------------------------------------------------------------------------
// isUnresolved
// ---------------------------------------------------------------------------

export function isUnresolved(call: TriageableCall): boolean {
  if (call.appointmentBooked) return false
  if (
    call.endCallReason &&
    TERMINAL_END_CALL_REASONS.has(call.endCallReason)
  )
    return false
  if (
    call.callbackOutcome &&
    TERMINAL_CALLBACK_OUTCOMES.has(call.callbackOutcome)
  )
    return false
  return true
}

// ---------------------------------------------------------------------------
// classifyReason (internal)
// ---------------------------------------------------------------------------

function classifyReason(call: TriageableCall): TriageReason {
  if (call.isSafetyEmergency || call.isUrgentEscalation)
    return "urgent_escalation"

  const issue = (call.hvacIssueType ?? "").toLowerCase()
  if (issue.includes("cool") || issue.includes("no cool")) return "no_cooling"
  if (issue.includes("heat") || issue.includes("no heat")) return "no_heating"

  if (call.endCallReason === "booking_failed") return "booking_failed"
  if (call.endCallReason === "callback_later" || call.callbackType)
    return "callback_requested"
  if (call.urgency === "Estimate") return "estimate_request"
  if (call.problemDescription || call.hvacIssueType)
    return "generic_service_issue"

  return "generic_service_issue"
}

// ---------------------------------------------------------------------------
// hasConcrete — does the call have a concrete issue description?
// ---------------------------------------------------------------------------

function hasConcrete(call: TriageableCall): boolean {
  return !!(call.problemDescription || call.hvacIssueType)
}

// ---------------------------------------------------------------------------
// computeCommand
// ---------------------------------------------------------------------------

function computeCommand(call: TriageableCall): TriageCommand {
  // Tier 1: immediate
  if (
    call.isSafetyEmergency ||
    call.urgency === "LifeSafety" ||
    call.isUrgentEscalation
  )
    return "Call now"

  if (call.urgency === "Urgent" && hasConcrete(call)) return "Call now"

  // Tier 2: follow-up needed
  if (
    call.endCallReason === "callback_later" ||
    call.callbackType ||
    call.endCallReason === "booking_failed" ||
    (call.urgency === "Urgent" && !hasConcrete(call))
  )
    return "Next up"

  // Tier 3: today
  if (call.urgency === "Estimate") return "Today"
  if (call.urgency === "Routine" && hasConcrete(call)) return "Today"

  // Tier 4: can wait
  return "Can wait"
}

// ---------------------------------------------------------------------------
// buildEvidence — short human-readable string, max 40 chars
// ---------------------------------------------------------------------------

function buildEvidence(call: TriageableCall, reason: TriageReason): string {
  const parts: string[] = []
  if (call.isSafetyEmergency) parts.push("Safety emergency")
  else if (call.isUrgentEscalation) parts.push("Urgent escalation")
  else if (call.urgency === "LifeSafety") parts.push("Life safety")

  if (call.hvacIssueType) parts.push(call.hvacIssueType)
  else if (call.problemDescription) {
    const desc = call.problemDescription.slice(0, 30)
    parts.push(desc)
  }

  if (call.endCallReason === "booking_failed") parts.push("Booking failed")
  if (call.endCallReason === "callback_later") parts.push("Callback req")

  const raw = parts.join("; ") || reason.replace(/_/g, " ")
  return raw.length > 40 ? raw.slice(0, 40) : raw
}

// ---------------------------------------------------------------------------
// signalRank — numeric rank for sorting within a bucket
// ---------------------------------------------------------------------------

function signalRank(call: TriageableCall): SignalRank {
  if (call.isSafetyEmergency) return SIGNAL_RANK_MAP.safety
  if (call.isUrgentEscalation) return SIGNAL_RANK_MAP.urgent_escalation
  if (call.endCallReason === "callback_later" || call.callbackType)
    return SIGNAL_RANK_MAP.follow_up
  if (hasConcrete(call)) return SIGNAL_RANK_MAP.concrete_issue
  return SIGNAL_RANK_MAP.generic
}

// ---------------------------------------------------------------------------
// callbackWindowValid
// ---------------------------------------------------------------------------

function isCallbackWindowValid(call: TriageableCall, now: number): boolean {
  const ref = call.callbackWindowEnd ?? call.callbackWindowStart
  if (!ref) return false
  return new Date(ref).getTime() > now
}

// ---------------------------------------------------------------------------
// computeTriage
// ---------------------------------------------------------------------------

export function computeTriage(
  call: TriageableCall,
  now: number = Date.now()
): TriageResult {
  const command = computeCommand(call)
  const reason = classifyReason(call)
  const evidence = buildEvidence(call, reason)

  const ageMs = now - new Date(call.createdAt).getTime()
  const ageMin = ageMs / 60_000
  const threshold = STALE_THRESHOLDS[command]
  const isStale = threshold != null ? ageMin >= threshold : false

  const callbackWindowValid = isCallbackWindowValid(call, now)

  return {
    isUnresolved: isUnresolved(call),
    command,
    evidence,
    reason,
    isStale,
    staleMinutes: Math.floor(ageMin),
    callbackWindowStart: call.callbackWindowStart,
    callbackWindowEnd: call.callbackWindowEnd,
    callbackWindowValid,
  }
}

// ---------------------------------------------------------------------------
// getAssistTemplate
// ---------------------------------------------------------------------------

export function getAssistTemplate(
  reason: TriageReason,
  companyName: string = "our company"
): string {
  return TEMPLATES[reason].replace(/\[Company\]/g, companyName)
}

// ---------------------------------------------------------------------------
// triageSort
// ---------------------------------------------------------------------------

export function triageSort<T extends TriageableCall>(
  calls: T[],
  now: number = Date.now()
): T[] {
  const triageCache = new Map<string, TriageResult>()
  for (const c of calls) {
    triageCache.set(c.id, computeTriage(c, now))
  }

  return [...calls].sort((a, b) => {
    const ta = triageCache.get(a.id)!
    const tb = triageCache.get(b.id)!

    // 1. Command bucket rank
    const rankDiff = COMMAND_RANK[ta.command] - COMMAND_RANK[tb.command]
    if (rankDiff !== 0) return rankDiff

    // 2. Valid callback window first
    if (ta.callbackWindowValid !== tb.callbackWindowValid)
      return ta.callbackWindowValid ? -1 : 1

    // 3. Stale before fresh
    if (ta.isStale !== tb.isStale) return ta.isStale ? -1 : 1

    // 4. Signal rank
    const sigDiff = signalRank(a) - signalRank(b)
    if (sigDiff !== 0) return sigDiff

    // 5. Recency tiebreak (newest first)
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  })
}
