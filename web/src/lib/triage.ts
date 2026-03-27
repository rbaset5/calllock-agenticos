import type {
  CallerType,
  CallbackOutcome,
  EndCallReason,
  PrimaryIntent,
  Route,
  RevenueTier,
  TriageCommand,
  TriageReason,
  TriageResult,
  UrgencyTier,
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
  callbackOutcomeAt: string | null
  callerType: CallerType | null
  primaryIntent: PrimaryIntent | null
  route: Route | null
  revenueTier: RevenueTier | null
  extractionStatus: string | null
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

  // Staleness measures time since last owner action (or call arrival if untouched)
  const lastActionTime = call.callbackOutcomeAt
    ? Math.max(new Date(call.callbackOutcomeAt).getTime(), new Date(call.createdAt).getTime())
    : new Date(call.createdAt).getTime()
  const ageMs = now - lastActionTime
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

// ---------------------------------------------------------------------------
// SectionKey + assignSection
// ---------------------------------------------------------------------------

export type SectionKey = "NEEDS_CALLBACK" | "HANDLED" | "UPCOMING"

/**
 * Assign a call to exactly one UI section.
 *
 * 1. appointmentBooked → UPCOMING
 * 2. terminal callbackOutcome OR terminal endCallReason → HANDLED
 * 3. otherwise → NEEDS_CALLBACK
 */
export function assignSection(call: TriageableCall): SectionKey {
  if (call.appointmentBooked) return "UPCOMING"

  if (
    call.callbackOutcome &&
    TERMINAL_CALLBACK_OUTCOMES.has(call.callbackOutcome)
  )
    return "HANDLED"

  if (
    call.endCallReason &&
    TERMINAL_END_CALL_REASONS.has(call.endCallReason)
  )
    return "HANDLED"

  return "NEEDS_CALLBACK"
}

// ---------------------------------------------------------------------------
// Bucket System (IA Redesign)
// ---------------------------------------------------------------------------

export type BucketKey = "ACTION_QUEUE" | "AI_HANDLED"
export type ActionSubGroup = "NEW_LEAD" | "FOLLOW_UP"
export type HandledReason = "escalated" | "resolved" | "non_customer" | "wrong_number" | "booked"

export interface BucketAssignment {
  bucket: BucketKey
  subGroup: ActionSubGroup | null
  escalationMarker: boolean
  handledReason: HandledReason | null
}

const NON_SERVICE_CALLER_TYPES = new Set<CallerType>(["job_applicant", "vendor", "spam"])
const FOLLOW_UP_INTENTS = new Set<PrimaryIntent>(["followup", "complaint", "active_job_issue"])
const RETRY_OUTCOMES = new Set<CallbackOutcome>(["left_voicemail", "no_answer"])
const FOLLOW_UP_END_REASONS = new Set<EndCallReason>(["callback_later", "booking_failed"])

function handled(reason: HandledReason, escalation = false): BucketAssignment {
  return { bucket: "AI_HANDLED", subGroup: null, escalationMarker: escalation, handledReason: reason }
}

function actionQueue(subGroup: ActionSubGroup): BucketAssignment {
  return { bucket: "ACTION_QUEUE", subGroup, escalationMarker: false, handledReason: null }
}

/**
 * Assign a call to a UI bucket. Order matters — first match wins.
 *
 * If extraction is pending and classification fields are all null,
 * classification-dependent rules (route, callerType, primaryIntent)
 * are skipped and the call falls through to NEW_LEAD.
 */
export function assignBucket(call: TriageableCall): BucketAssignment {
  // 1. Terminal callback outcome → resolved
  if (call.callbackOutcome && TERMINAL_CALLBACK_OUTCOMES.has(call.callbackOutcome))
    return handled("resolved")

  // Extraction guard: if pending and no classification data, skip classification rules
  const hasClassification = !!(call.route || call.callerType || call.primaryIntent)
  const isPendingExtraction = call.extractionStatus === "pending" && !hasClassification

  if (!isPendingExtraction) {
    // 2. Spam/vendor route
    if (call.route === "spam" || call.route === "vendor")
      return handled("non_customer")

    // 3. Non-service caller types
    if (call.callerType && NON_SERVICE_CALLER_TYPES.has(call.callerType))
      return handled("non_customer")
  }

  // 4. Wrong number / out of area (stable field, not classification-dependent)
  if (call.endCallReason === "wrong_number" || call.endCallReason === "out_of_area")
    return handled("wrong_number")

  // 5. Emergencies → AI escalated
  if (call.isSafetyEmergency || call.urgency === "LifeSafety" || call.isUrgentEscalation)
    return handled("escalated", true)

  // 6. Appointment booked → AI handled (Phase 2 adds confirmation workflow)
  if (call.appointmentBooked)
    return handled("booked")

  // 7. Terminal end-call reasons
  if (call.endCallReason && TERMINAL_END_CALL_REASONS.has(call.endCallReason))
    return handled("resolved")

  // 8. Leads from waitlist/sales
  if (call.endCallReason === "waitlist_added" || call.endCallReason === "sales_lead")
    return actionQueue("NEW_LEAD")

  // 9. Legacy follow-up signals
  if (call.endCallReason && FOLLOW_UP_END_REASONS.has(call.endCallReason))
    return actionQueue("FOLLOW_UP")

  // 10. Follow-up intents (classification-dependent, guarded)
  if (!isPendingExtraction && call.primaryIntent && FOLLOW_UP_INTENTS.has(call.primaryIntent))
    return actionQueue("FOLLOW_UP")

  // 11. Retry outcomes
  if (call.callbackOutcome && RETRY_OUTCOMES.has(call.callbackOutcome))
    return actionQueue("FOLLOW_UP")

  // 12. Default → new lead
  return actionQueue("NEW_LEAD")
}

/**
 * Check if a call is in the owner's action queue (replaces isUnresolved for rendering).
 */
export function isActionable(call: TriageableCall): boolean {
  return assignBucket(call).bucket === "ACTION_QUEUE"
}

// ---------------------------------------------------------------------------
// followUpSort — sort follow-up calls by urgency + recency
// ---------------------------------------------------------------------------

export function followUpSort<T extends TriageableCall>(calls: T[]): T[] {
  return [...calls].sort((a, b) => {
    // 1. Active issues first (complaint, active_job_issue)
    const aActive = FOLLOW_UP_INTENTS.has(a.primaryIntent as PrimaryIntent) && a.primaryIntent !== "followup" ? 0 : 1
    const bActive = FOLLOW_UP_INTENTS.has(b.primaryIntent as PrimaryIntent) && b.primaryIntent !== "followup" ? 0 : 1
    if (aActive !== bActive) return aActive - bActive

    // 2. Callback retries before generic followup
    const aRetry = RETRY_OUTCOMES.has(a.callbackOutcome as CallbackOutcome) ? 0 : 1
    const bRetry = RETRY_OUTCOMES.has(b.callbackOutcome as CallbackOutcome) ? 0 : 1
    if (aRetry !== bRetry) return aRetry - bRetry

    // 3. Recency (newest first, guard against NaN)
    const aTime = new Date(a.createdAt).getTime() || 0
    const bTime = new Date(b.createdAt).getTime() || 0
    return bTime - aTime
  })
}
