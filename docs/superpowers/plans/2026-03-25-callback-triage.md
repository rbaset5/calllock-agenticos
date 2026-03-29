# Missed-Call Callback Triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a callback triage system to the CallLock App that ranks unresolved calls by urgency, shows triage commands + evidence, captures callback outcomes, surfaces callback assist copy, and respects callback-window timing.

**Architecture:** A shared pure triage engine (`web/src/lib/triage.ts`) is the single source of truth for unresolved status, triage command, evidence, stale rank, and callback-window ordering. Callback outcomes are persisted to explicit columns on `call_records` via a narrow server-owned API route. The triage engine is consumed by server load, realtime inserts, client-side stale timer, and all UI rendering.

**Tech Stack:** Next.js App Router, Supabase (Postgres), TypeScript, Tailwind CSS

---

## Canonical Contracts (Reviewer Concerns)

### Terminal EndCallReasons (exclude from unresolved queue)

| EndCallReason | Terminal? | Rationale |
|---|---|---|
| `wrong_number` | Yes | Not a real lead |
| `out_of_area` | Yes | Cannot service |
| `cancelled` | Yes | Customer withdrew |
| `completed` | Yes | Successfully handled |
| `rescheduled` | Yes | Customer already reached, appointment rebooked |
| `callback_later` | No | Explicit follow-up needed |
| `booking_failed` | No | Attempted but failed — needs retry |
| `safety_emergency` | No | Needs immediate owner attention |
| `urgent_escalation` | No | Needs immediate owner attention |
| `customer_hangup` | No | Unclear outcome — needs review |
| `waitlist_added` | No | Still needs owner follow-up or conversion |
| `sales_lead` | No | Needs owner follow-up to convert |

### Triage Reason Mapping (evidence patterns → callback-assist taxonomy)

| Signal / Evidence Pattern | Triage Reason | Assist Template |
|---|---|---|
| `isSafetyEmergency = true` or `isUrgentEscalation = true` | `urgent_escalation` | Urgent situation opener |
| `hvacIssueType` contains "cool" / "No Cool" | `no_cooling` | Cooling issue opener |
| `hvacIssueType` contains "heat" / "No Heat" | `no_heating` | Heating issue opener |
| `endCallReason = booking_failed` | `booking_failed` | Booking retry opener |
| `endCallReason = callback_later` or `callbackType` present | `callback_requested` | Return call opener |
| `urgency = Estimate` | `estimate_request` | Estimate follow-up opener |
| `problemDescription` or `hvacIssueType` present (no stronger match) | `generic_service_issue` | Generic follow-up opener |
| No evidence available | `generic_service_issue` | Generic follow-up opener |

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `web/src/lib/triage.ts` | Pure triage engine: unresolved check, command assignment, evidence generation, stale detection, callback-window ordering, assist templates |
| `web/src/lib/__tests__/triage.test.ts` | Unit tests for every triage rule and edge case |
| `supabase/migrations/051_callback_workflow.sql` | Add `callback_outcome`, `callback_outcome_at` columns to `call_records` |
| `web/src/app/api/calls/[callId]/outcome/route.ts` | Server-owned PATCH route for persisting callback outcomes |

### Modified files

| File | Changes |
|------|---------|
| `web/src/types/call.ts` | Add `CallbackOutcome` type, `TriageCommand` type, triage-related fields to `Call` interface |
| `web/src/lib/transforms.ts` | Extract `callback_window_start`, `callback_window_end`, `callback_outcome`, `callback_outcome_at` into `Call` |
| `web/src/app/page.tsx` | Select new columns (`callback_outcome`, `callback_outcome_at`), apply triage sort |
| `web/src/hooks/use-realtime-calls.ts` | Subscribe to `UPDATE` events (not just `INSERT`) so outcome changes propagate |
| `web/src/components/mail/mail.tsx` | Add stale-recompute timer, apply triage sort to activity calls |
| `web/src/components/mail/mail-list.tsx` | Render triage block (command + evidence) on far left of each unresolved row |
| `web/src/components/mail/mail-display.tsx` | Add callback outcome selector, callback assist copy section |

---

## Task 1: Types and Contracts

**Files:**
- Modify: `web/src/types/call.ts`

- [ ] **Step 1: Add callback outcome and triage types**

Add these types at the top of `call.ts`, after the existing `EndCallReason` type:

```typescript
export type CallbackOutcome =
  | "reached_customer"
  | "scheduled"
  | "left_voicemail"
  | "no_answer"
  | "resolved_elsewhere"

/** Terminal outcomes that remove a call from the unresolved queue */
export const TERMINAL_CALLBACK_OUTCOMES: ReadonlySet<CallbackOutcome> = new Set([
  "reached_customer",
  "scheduled",
  "resolved_elsewhere",
])

/**
 * EndCallReasons that make a call terminal (never enters unresolved queue).
 *
 * Confirmed against EndCallReason enum:
 * - wrong_number, out_of_area, cancelled, completed, rescheduled → terminal
 * - callback_later, booking_failed, customer_hangup, safety_emergency,
 *   urgent_escalation, waitlist_added, sales_lead → non-terminal (stay unresolved)
 *
 * Rationale: rescheduled means the customer was already reached and rebooked.
 * waitlist_added and sales_lead remain unresolved because the owner still
 * needs to follow up or convert.
 */
export const TERMINAL_END_CALL_REASONS: ReadonlySet<EndCallReason> = new Set([
  "wrong_number",
  "out_of_area",
  "cancelled",
  "completed",
  "rescheduled",
])

export type TriageCommand = "Call now" | "Next up" | "Today" | "Can wait"

export type TriageReason =
  | "no_cooling"
  | "no_heating"
  | "estimate_request"
  | "callback_requested"
  | "booking_failed"
  | "urgent_escalation"
  | "generic_service_issue"

export interface TriageResult {
  isUnresolved: boolean
  command: TriageCommand
  evidence: string
  reason: TriageReason
  isStale: boolean
  staleMinutes: number
  callbackWindowStart: string | null
  callbackWindowEnd: string | null
  callbackWindowValid: boolean
}
```

- [ ] **Step 2: Extend the Call interface**

Add these fields to the `Call` interface (after the existing `read` field):

```typescript
  callbackOutcome: CallbackOutcome | null
  callbackOutcomeAt: string | null
  callbackWindowStart: string | null
  callbackWindowEnd: string | null
```

- [ ] **Step 3: Extend CallRecordRow and CallRecordListRow**

Add to `CallRecordRow`:

```typescript
  callback_outcome: string | null
  callback_outcome_at: string | null
```

Add `"callback_outcome"` and `"callback_outcome_at"` to the `CallRecordListRow` Pick union.

- [ ] **Step 4: Commit**

```bash
git add web/src/types/call.ts
git commit -m "feat(triage): add callback outcome, triage command, and triage result types"
```

---

## Task 2: Supabase Migration

**Files:**
- Create: `supabase/migrations/051_callback_workflow.sql`

- [ ] **Step 1: Write the migration**

```sql
-- Callback workflow columns on call_records
-- callback_outcome: owner-selected outcome after reviewing/acting on a call
-- callback_outcome_at: timestamp of the most recent outcome selection

ALTER TABLE public.call_records
  ADD COLUMN IF NOT EXISTS callback_outcome TEXT
    CHECK (callback_outcome IN (
      'reached_customer', 'scheduled', 'left_voicemail', 'no_answer', 'resolved_elsewhere'
    )),
  ADD COLUMN IF NOT EXISTS callback_outcome_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_call_records_unresolved
  ON public.call_records (tenant_id, created_at DESC)
  WHERE callback_outcome IS NULL
    OR callback_outcome NOT IN ('reached_customer', 'scheduled', 'resolved_elsewhere');
```

- [ ] **Step 2: Commit**

```bash
git add supabase/migrations/051_callback_workflow.sql
git commit -m "feat(triage): add callback_outcome columns to call_records"
```

---

## Task 3: Shared Triage Engine

**Files:**
- Create: `web/src/lib/triage.ts`
- Create: `web/src/lib/__tests__/triage.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `web/src/lib/__tests__/triage.test.ts`:

```typescript
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
  it("returns true for a basic unresolved call", () => {
    expect(isUnresolved(makeCall())).toBe(true)
  })

  it("returns false when appointmentBooked is true", () => {
    expect(isUnresolved(makeCall({ appointmentBooked: true }))).toBe(false)
  })

  it("returns false for terminal end call reasons", () => {
    expect(isUnresolved(makeCall({ endCallReason: "wrong_number" }))).toBe(false)
    expect(isUnresolved(makeCall({ endCallReason: "out_of_area" }))).toBe(false)
    expect(isUnresolved(makeCall({ endCallReason: "cancelled" }))).toBe(false)
    expect(isUnresolved(makeCall({ endCallReason: "completed" }))).toBe(false)
  })

  it("returns true for non-terminal end call reasons", () => {
    expect(isUnresolved(makeCall({ endCallReason: "callback_later" }))).toBe(true)
    expect(isUnresolved(makeCall({ endCallReason: "booking_failed" }))).toBe(true)
  })

  it("returns false for terminal callback outcomes", () => {
    expect(isUnresolved(makeCall({ callbackOutcome: "reached_customer" }))).toBe(false)
    expect(isUnresolved(makeCall({ callbackOutcome: "scheduled" }))).toBe(false)
    expect(isUnresolved(makeCall({ callbackOutcome: "resolved_elsewhere" }))).toBe(false)
  })

  it("returns true for non-terminal callback outcomes", () => {
    expect(isUnresolved(makeCall({ callbackOutcome: "left_voicemail" }))).toBe(true)
    expect(isUnresolved(makeCall({ callbackOutcome: "no_answer" }))).toBe(true)
  })

  it("returns false for rescheduled end call reason", () => {
    expect(isUnresolved(makeCall({ endCallReason: "rescheduled" }))).toBe(false)
  })

  it("transitions from unresolved to resolved when outcome changes", () => {
    // Simulates editing an outcome: no_answer (non-terminal) → reached_customer (terminal)
    const callNoAnswer = makeCall({ callbackOutcome: "no_answer" })
    expect(isUnresolved(callNoAnswer)).toBe(true)

    const callReached = makeCall({ callbackOutcome: "reached_customer" })
    expect(isUnresolved(callReached)).toBe(false)
  })
})

describe("computeTriage", () => {
  it("assigns 'Call now' for safety emergency", () => {
    const result = computeTriage(makeCall({ isSafetyEmergency: true }))
    expect(result.command).toBe("Call now")
  })

  it("assigns 'Call now' for LifeSafety urgency", () => {
    const result = computeTriage(makeCall({ urgency: "LifeSafety" }))
    expect(result.command).toBe("Call now")
  })

  it("assigns 'Call now' for urgent escalation", () => {
    const result = computeTriage(makeCall({ isUrgentEscalation: true }))
    expect(result.command).toBe("Call now")
  })

  it("assigns 'Next up' for callback_later", () => {
    const result = computeTriage(makeCall({ endCallReason: "callback_later" }))
    expect(result.command).toBe("Next up")
  })

  it("assigns 'Next up' for booking_failed", () => {
    const result = computeTriage(makeCall({ endCallReason: "booking_failed" }))
    expect(result.command).toBe("Next up")
  })

  it("assigns 'Next up' for callbackType present", () => {
    const result = computeTriage(makeCall({ callbackType: "immediate" }))
    expect(result.command).toBe("Next up")
  })

  it("assigns 'Today' for estimate request", () => {
    const result = computeTriage(makeCall({ urgency: "Estimate" }))
    expect(result.command).toBe("Today")
  })

  it("assigns 'Today' for routine with concrete issue", () => {
    const result = computeTriage(makeCall({ urgency: "Routine", problemDescription: "AC not cooling" }))
    expect(result.command).toBe("Today")
  })

  it("assigns 'Can wait' for low-information call", () => {
    const result = computeTriage(makeCall({ urgency: "Routine" }))
    expect(result.command).toBe("Can wait")
  })

  it("produces compact evidence string", () => {
    const result = computeTriage(makeCall({ isSafetyEmergency: true, hvacIssueType: "No Cool" }))
    expect(result.evidence.length).toBeLessThanOrEqual(40)
    expect(result.evidence.length).toBeGreaterThan(0)
  })

  it("detects stale for Call now after 15 minutes", () => {
    const fifteenMinAgo = new Date(Date.now() - 16 * 60 * 1000).toISOString()
    const result = computeTriage(makeCall({ isSafetyEmergency: true, createdAt: fifteenMinAgo }))
    expect(result.isStale).toBe(true)
  })

  it("not stale for Call now under 15 minutes", () => {
    const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString()
    const result = computeTriage(makeCall({ isSafetyEmergency: true, createdAt: fiveMinAgo }))
    expect(result.isStale).toBe(false)
  })

  it("detects stale for Next up after 60 minutes", () => {
    const sixtyOneMinAgo = new Date(Date.now() - 61 * 60 * 1000).toISOString()
    const result = computeTriage(makeCall({ endCallReason: "callback_later", createdAt: sixtyOneMinAgo }))
    expect(result.isStale).toBe(true)
  })

  it("does not mark Today or Can wait as stale", () => {
    const dayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
    const result = computeTriage(makeCall({ urgency: "Estimate", createdAt: dayAgo }))
    expect(result.isStale).toBe(false)
  })
})

describe("computeTriage callback window", () => {
  it("marks valid future window", () => {
    const inOneHour = new Date(Date.now() + 60 * 60 * 1000).toISOString()
    const inTwoHours = new Date(Date.now() + 120 * 60 * 1000).toISOString()
    const result = computeTriage(makeCall({
      endCallReason: "callback_later",
      callbackWindowStart: inOneHour,
      callbackWindowEnd: inTwoHours,
    }))
    expect(result.callbackWindowValid).toBe(true)
  })

  it("ignores past window", () => {
    const twoHoursAgo = new Date(Date.now() - 120 * 60 * 1000).toISOString()
    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000).toISOString()
    const result = computeTriage(makeCall({
      endCallReason: "callback_later",
      callbackWindowStart: twoHoursAgo,
      callbackWindowEnd: oneHourAgo,
    }))
    expect(result.callbackWindowValid).toBe(false)
  })

  it("ignores missing window", () => {
    const result = computeTriage(makeCall({ endCallReason: "callback_later" }))
    expect(result.callbackWindowValid).toBe(false)
  })
})

describe("getAssistTemplate", () => {
  it("returns specific template for known reasons", () => {
    const tpl = getAssistTemplate("no_cooling")
    expect(tpl).toContain("cooling")
  })

  it("returns generic fallback for unknown reason", () => {
    const tpl = getAssistTemplate("generic_service_issue")
    expect(tpl.length).toBeGreaterThan(0)
  })
})

describe("triageSort", () => {
  it("sorts Call now before Next up", () => {
    const a = makeCall({ isSafetyEmergency: true })
    const b = makeCall({ endCallReason: "callback_later" })
    const sorted = triageSort([b, a])
    expect(sorted[0].id).toBe(a.id)
  })

  it("sorts stale before fresh within same bucket", () => {
    const stale = makeCall({
      id: "stale",
      isSafetyEmergency: true,
      createdAt: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
    })
    const fresh = makeCall({
      id: "fresh",
      isSafetyEmergency: true,
      createdAt: new Date().toISOString(),
    })
    const sorted = triageSort([fresh, stale])
    expect(sorted[0].id).toBe("stale")
  })

  it("sorts valid callback window before no window within same bucket", () => {
    const withWindow = makeCall({
      id: "window",
      endCallReason: "callback_later",
      callbackWindowStart: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
      callbackWindowEnd: new Date(Date.now() + 90 * 60 * 1000).toISOString(),
      createdAt: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
    })
    const noWindow = makeCall({
      id: "no-window",
      endCallReason: "callback_later",
      createdAt: new Date().toISOString(),
    })
    const sorted = triageSort([noWindow, withWindow])
    expect(sorted[0].id).toBe("window")
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npx vitest run src/lib/__tests__/triage.test.ts`
Expected: FAIL — module `../triage` not found

- [ ] **Step 3: Write the triage engine**

Create `web/src/lib/triage.ts`:

```typescript
import type {
  CallbackOutcome,
  EndCallReason,
  TriageCommand,
  TriageReason,
  TriageResult,
  UrgencyTier,
} from "@/types/call"
import {
  TERMINAL_CALLBACK_OUTCOMES,
  TERMINAL_END_CALL_REASONS,
} from "@/types/call"

/** Minimal call shape needed by the triage engine */
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

// ── Stale thresholds (minutes) ──

const STALE_CALL_NOW_MIN = 15
const STALE_NEXT_UP_MIN = 60

// ── Command bucket ordering ──

const COMMAND_RANK: Record<TriageCommand, number> = {
  "Call now": 0,
  "Next up": 1,
  "Today": 2,
  "Can wait": 3,
}

// ── Signal rank within bucket (lower = higher priority) ──

const SIGNAL_RANK = {
  safety_emergency: 0,
  urgent_escalation: 1,
  follow_up_signal: 2,
  concrete_issue: 3,
  generic: 4,
} as const

// ── Unresolved check ──

export function isUnresolved(call: TriageableCall): boolean {
  if (call.appointmentBooked) return false
  if (call.endCallReason && TERMINAL_END_CALL_REASONS.has(call.endCallReason)) return false
  if (call.callbackOutcome && TERMINAL_CALLBACK_OUTCOMES.has(call.callbackOutcome)) return false
  return true
}

// ── Callback window validation ──

function isCallbackWindowValid(
  start: string | null,
  end: string | null,
  now: number = Date.now()
): boolean {
  if (!start) return false
  try {
    const endTime = end ? new Date(end).getTime() : new Date(start).getTime()
    return endTime > now
  } catch {
    return false
  }
}

// ── Elapsed minutes ──

function elapsedMinutes(createdAt: string, now: number = Date.now()): number {
  return (now - new Date(createdAt).getTime()) / 60_000
}

// ── Evidence generation ──

function pickEvidence(call: TriageableCall, reason: TriageReason): string {
  switch (reason) {
    case "no_cooling": return "no cooling"
    case "no_heating": return "no heating"
    case "estimate_request": return "estimate request"
    case "callback_requested": return "requested callback"
    case "booking_failed": return "booking failed"
    case "urgent_escalation": return "urgent escalation"
    case "generic_service_issue":
      if (call.problemDescription) {
        const truncated = call.problemDescription.slice(0, 28)
        return truncated.length < call.problemDescription.length
          ? truncated + "..."
          : truncated
      }
      return "incomplete details, needs review"
  }
}

// ── Reason classification ──

function classifyReason(call: TriageableCall): TriageReason {
  if (call.isSafetyEmergency || call.isUrgentEscalation) return "urgent_escalation"

  const issue = (call.hvacIssueType ?? "").toLowerCase()
  if (issue.includes("no cool") || issue.includes("cooling")) return "no_cooling"
  if (issue.includes("no heat") || issue.includes("heating")) return "no_heating"

  if (call.endCallReason === "booking_failed") return "booking_failed"
  if (
    call.endCallReason === "callback_later" ||
    call.callbackType
  ) return "callback_requested"

  if (call.urgency === "Estimate") return "estimate_request"

  if (call.problemDescription || call.hvacIssueType) return "generic_service_issue"

  return "generic_service_issue"
}

// ── Signal rank ──

function getSignalRank(call: TriageableCall): number {
  if (call.isSafetyEmergency) return SIGNAL_RANK.safety_emergency
  if (call.isUrgentEscalation) return SIGNAL_RANK.urgent_escalation
  if (
    call.endCallReason === "callback_later" ||
    call.endCallReason === "booking_failed" ||
    call.callbackType
  ) return SIGNAL_RANK.follow_up_signal
  if (call.problemDescription || call.hvacIssueType) return SIGNAL_RANK.concrete_issue
  return SIGNAL_RANK.generic
}

// ── Main triage computation ──

export function computeTriage(
  call: TriageableCall,
  now: number = Date.now()
): TriageResult {
  const reason = classifyReason(call)
  const evidence = pickEvidence(call, reason)
  const windowValid = isCallbackWindowValid(
    call.callbackWindowStart,
    call.callbackWindowEnd,
    now
  )

  // Determine command bucket
  let command: TriageCommand

  if (
    call.isSafetyEmergency ||
    call.urgency === "LifeSafety" ||
    call.isUrgentEscalation
  ) {
    command = "Call now"
  } else if (call.urgency === "Urgent" && (call.problemDescription || call.hvacIssueType)) {
    command = "Call now"
  } else if (
    call.endCallReason === "callback_later" ||
    call.callbackType ||
    call.endCallReason === "booking_failed" ||
    (call.urgency === "Urgent" && !call.problemDescription && !call.hvacIssueType)
  ) {
    command = "Next up"
  } else if (
    call.urgency === "Estimate" ||
    (call.urgency === "Routine" && (call.problemDescription || call.hvacIssueType))
  ) {
    command = "Today"
  } else {
    command = "Can wait"
  }

  // Stale detection (only Call now and Next up)
  const elapsed = elapsedMinutes(call.createdAt, now)
  let isStale = false
  if (command === "Call now" && elapsed >= STALE_CALL_NOW_MIN) isStale = true
  if (command === "Next up" && elapsed >= STALE_NEXT_UP_MIN) isStale = true

  return {
    isUnresolved: isUnresolved(call),
    command,
    evidence,
    reason,
    isStale,
    staleMinutes: Math.floor(elapsed),
    callbackWindowStart: call.callbackWindowStart,
    callbackWindowEnd: call.callbackWindowEnd,
    callbackWindowValid: windowValid,
  }
}

// ── Callback assist templates ──

const ASSIST_TEMPLATES: Record<TriageReason, string> = {
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

export function getAssistTemplate(reason: TriageReason): string {
  return ASSIST_TEMPLATES[reason]
}

// ── Triage-aware sorting ──

export function triageSort<T extends TriageableCall>(calls: T[], now: number = Date.now()): T[] {
  return [...calls].sort((a, b) => {
    const ta = computeTriage(a, now)
    const tb = computeTriage(b, now)

    // 1. Command bucket
    const rankDiff = COMMAND_RANK[ta.command] - COMMAND_RANK[tb.command]
    if (rankDiff !== 0) return rankDiff

    // 2. Within bucket: valid callback window sorts first
    if (ta.callbackWindowValid && !tb.callbackWindowValid) return -1
    if (!ta.callbackWindowValid && tb.callbackWindowValid) return 1
    if (ta.callbackWindowValid && tb.callbackWindowValid) {
      const aStart = new Date(a.callbackWindowStart!).getTime()
      const bStart = new Date(b.callbackWindowStart!).getTime()
      if (aStart !== bStart) return aStart - bStart
    }

    // 3. Stale sorts before fresh
    if (ta.isStale && !tb.isStale) return -1
    if (!ta.isStale && tb.isStale) return 1

    // 4. Signal rank within bucket
    const sigDiff = getSignalRank(a) - getSignalRank(b)
    if (sigDiff !== 0) return sigDiff

    // 5. Recency (most recent first)
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  })
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/lib/__tests__/triage.test.ts`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/triage.ts web/src/lib/__tests__/triage.test.ts
git commit -m "feat(triage): add shared pure triage engine with tests"
```

---

## Task 4: Transform Layer — Extract New Fields

**Files:**
- Modify: `web/src/lib/transforms.ts`

- [ ] **Step 1: Add callback window and outcome extraction**

In `transformCallRecord`, extract the four new fields from `extracted_fields` and the new columns. Add these lines before the `return` statement, and add the fields to the returned object:

```typescript
  // After the existing callbackType extraction (around line 85):
  const callbackWindowStart = str(
    field(fields, "callback_window_start", "callbackWindowStart")
  )
  const callbackWindowEnd = str(
    field(fields, "callback_window_end", "callbackWindowEnd")
  )

  // Read from the new explicit columns (CallRecordRow has them, CallRecordListRow may)
  const callbackOutcome = "callback_outcome" in row
    ? (row.callback_outcome as Call["callbackOutcome"])
    : null
  const callbackOutcomeAt = "callback_outcome_at" in row
    ? (row.callback_outcome_at as string | null)
    : null
```

Add to the returned `Call` object (after `callbackType`):

```typescript
    callbackOutcome,
    callbackOutcomeAt: callbackOutcomeAt ?? null,
    callbackWindowStart: callbackWindowStart || null,
    callbackWindowEnd: callbackWindowEnd || null,
```

- [ ] **Step 2: Commit**

```bash
git add web/src/lib/transforms.ts
git commit -m "feat(triage): extract callback window and outcome fields in transform layer"
```

---

## Task 5: Server Query — Select New Columns

**Files:**
- Modify: `web/src/app/page.tsx`

- [ ] **Step 1: Add new columns to the select query**

In `page.tsx`, add `callback_outcome, callback_outcome_at` to the `.select()` string (line 17). The updated select should be:

```typescript
      .select(
        "id, tenant_id, call_id, retell_call_id, phone_number, transcript, extracted_fields, extraction_status, urgency_tier, end_call_reason, callback_scheduled, booking_id, callback_outcome, callback_outcome_at, created_at, updated_at"
      )
```

- [ ] **Step 2: Apply triage sort to calls before passing to Mail**

Import `triageSort` and `isUnresolved` from `@/lib/triage`, then wrap the transformed calls:

```typescript
import { triageSort, isUnresolved } from "@/lib/triage"
```

After the `calls = rows.map(...)` line, add:

```typescript
      const unresolvedCalls = calls.filter(isUnresolved)
      const resolvedCalls = calls.filter((c) => !isUnresolved(c))
      calls = [...triageSort(unresolvedCalls), ...resolvedCalls]
```

- [ ] **Step 3: Commit**

```bash
git add web/src/app/page.tsx
git commit -m "feat(triage): select callback columns and apply triage sort on server"
```

---

## Task 6: Server Mutation Route — Callback Outcome

**Files:**
- Create: `web/src/app/api/calls/[callId]/outcome/route.ts`

- [ ] **Step 1: Write the PATCH route**

```typescript
import { NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase-server"

const VALID_OUTCOMES = new Set([
  "reached_customer",
  "scheduled",
  "left_voicemail",
  "no_answer",
  "resolved_elsewhere",
])

export async function PATCH(
  request: Request,
  context: { params: Promise<{ callId: string }> }
) {
  const { callId } = await context.params

  let body: { outcome: string }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 })
  }

  if (!body.outcome || !VALID_OUTCOMES.has(body.outcome)) {
    return NextResponse.json(
      { error: `Invalid outcome. Must be one of: ${[...VALID_OUTCOMES].join(", ")}` },
      { status: 400 }
    )
  }

  const supabase = createServerClient()

  const { error } = await supabase
    .from("call_records")
    .update({
      callback_outcome: body.outcome,
      callback_outcome_at: new Date().toISOString(),
    })
    .eq("call_id", callId)

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return NextResponse.json({ ok: true, outcome: body.outcome })
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/app/api/calls/\[callId\]/outcome/route.ts
git commit -m "feat(triage): add server-owned PATCH route for callback outcomes"
```

---

## Task 7: Realtime — Subscribe to Updates

**Files:**
- Modify: `web/src/hooks/use-realtime-calls.ts`

- [ ] **Step 1: Add UPDATE subscription**

In the existing `useEffect` that sets up the Supabase channel, chain a second `.on()` listener for `UPDATE` events. When an update arrives, merge the updated row into the existing calls array:

```typescript
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "call_records",
        },
        (payload) => {
          const row = payload.new as CallRecordRow
          const updated = transformCallRecord(row, readIdsRef.current)
          setCalls((prev) =>
            prev.map((c) => (c.id === updated.id ? updated : c))
          )
        }
      )
```

Add this between the existing `.on("INSERT", ...)` and `.subscribe()` calls.

- [ ] **Step 2: Commit**

```bash
git add web/src/hooks/use-realtime-calls.ts
git commit -m "feat(triage): subscribe to call_records UPDATE events for outcome changes"
```

---

## Task 8: Mail Component — Triage Sort + Stale Timer

**Files:**
- Modify: `web/src/components/mail/mail.tsx`

- [ ] **Step 1: Import triage functions**

Add to imports:

```typescript
import { triageSort, isUnresolved } from "@/lib/triage"
```

- [ ] **Step 2: Replace activityCalls computation with triage-sorted version**

Replace the existing `activityCalls` line (currently line 52) and the `testCalls` line. Preserve the existing `filter` behavior while adding triage sort:

```typescript
  const unresolvedCalls = React.useMemo(
    () => calls.filter(isUnresolved),
    [calls]
  )
  const resolvedCalls = React.useMemo(
    () => calls.filter((c) => !isUnresolved(c)),
    [calls]
  )

  const [now, setNow] = React.useState(Date.now)

  const triageSortedCalls = React.useMemo(
    () => [...triageSort(unresolvedCalls, now), ...resolvedCalls],
    [unresolvedCalls, resolvedCalls, now]
  )

  // Preserve existing filter logic: "scheduled" filters to booked calls only
  const activityCalls = filter === "scheduled"
    ? triageSortedCalls.filter((c) => c.appointmentBooked)
    : triageSortedCalls
```

- [ ] **Step 3: Add stale-recompute timer**

Add a `useEffect` that ticks `now` every 30 seconds while the activity view is active:

```typescript
  React.useEffect(() => {
    if (view !== "activity") return
    const interval = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(interval)
  }, [view])
```

- [ ] **Step 4: Commit**

```bash
git add web/src/components/mail/mail.tsx
git commit -m "feat(triage): apply triage sort and stale timer to activity feed"
```

---

## Task 9: Mail List — Triage Block UI

**Files:**
- Modify: `web/src/components/mail/mail-list.tsx`

- [ ] **Step 1: Import triage functions**

Add to imports:

```typescript
import { computeTriage, isUnresolved } from "@/lib/triage"
```

- [ ] **Step 2: Add triage command color map**

After the existing `getUrgencyChip` function, add:

```typescript
const COMMAND_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  "Call now": { bg: "bg-[#7f2927]/20", text: "text-[#ff9993]", border: "border-l-[#ff9993]" },
  "Next up":  { bg: "bg-[#92400e]/20", text: "text-[#fbbf24]", border: "border-l-[#fbbf24]" },
  "Today":    { bg: "bg-[#1e3a5f]/20", text: "text-[#93c5fd]", border: "border-l-[#93c5fd]" },
  "Can wait": { bg: "bg-[#252626]",     text: "text-[#acabaa]", border: "border-l-[#acabaa]/30" },
}
```

- [ ] **Step 3: Add triage block to activity view rows**

In the activity view section (the `return` block starting around line 126), update each row to render the triage block on the far left. Inside the `items.map` callback, add triage computation:

```typescript
        const triage = computeTriage(item)
        const unresolved = isUnresolved(item)
        const style = COMMAND_STYLES[triage.command] ?? COMMAND_STYLES["Can wait"]
```

Then wrap the existing row content in a flex layout with the triage block on the left. The triage block should be:

```tsx
              {unresolved && (
                <div className={cn(
                  "w-[72px] shrink-0 flex flex-col items-start justify-center gap-0.5 pr-3 border-l-2 pl-2",
                  style.border
                )}>
                  <span className={cn("text-[10px] font-bold uppercase tracking-tight", style.text)}>
                    {triage.command}
                  </span>
                  <span className="text-[9px] text-[#acabaa] leading-tight line-clamp-2">
                    {triage.evidence}
                  </span>
                  {triage.isStale && (
                    <span className="text-[8px] text-[#ff9993]/70 font-bold mt-0.5">
                      {triage.staleMinutes}m ago
                    </span>
                  )}
                </div>
              )}
```

Also add callback window indicator when present:

```tsx
              {triage.callbackWindowValid && triage.callbackWindowStart && (
                <span className="text-[8px] text-[#93c5fd] mt-1">
                  Available {new Date(triage.callbackWindowStart).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
                </span>
              )}
```

- [ ] **Step 4: Commit**

```bash
git add web/src/components/mail/mail-list.tsx
git commit -m "feat(triage): render triage block with command, evidence, and stale indicator"
```

---

## Task 10: Mail Display — Callback Outcome Capture + Assist

**Files:**
- Modify: `web/src/components/mail/mail-display.tsx`

- [ ] **Step 1: Import types and triage functions**

Add to imports:

```typescript
import type { CallbackOutcome, TriageReason } from "@/types/call"
import { computeTriage, getAssistTemplate, isUnresolved } from "@/lib/triage"
```

- [ ] **Step 2: Add callback outcome state and submit handler**

Inside `MailDisplay`, after the existing `activeTab` state, add:

```typescript
  const [submittingOutcome, setSubmittingOutcome] = useState(false)

  const handleOutcome = async (outcome: CallbackOutcome) => {
    if (!call || submittingOutcome) return
    setSubmittingOutcome(true)
    try {
      const res = await fetch(`/api/calls/${call.id}/outcome`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome }),
      })
      if (!res.ok) throw new Error("Failed to save outcome")
    } catch {
      // Outcome save failed — user can retry
    } finally {
      setSubmittingOutcome(false)
    }
  }
```

- [ ] **Step 3: Add outcome selector UI to the summary tab**

After the existing "Best Next Move" section in the summary tab, add a callback outcome section. This should appear only for unresolved calls:

```tsx
            {/* Callback Outcome */}
            {isUnresolved(call) && (
              <div className="space-y-4">
                <h4 className="font-headline font-bold text-[#acabaa] text-xs uppercase tracking-widest">
                  Mark Callback Outcome
                </h4>
                <div className="flex flex-wrap gap-2">
                  {([
                    ["reached_customer", "Reached Customer"],
                    ["scheduled", "Scheduled"],
                    ["left_voicemail", "Left Voicemail"],
                    ["no_answer", "No Answer"],
                    ["resolved_elsewhere", "Resolved Elsewhere"],
                  ] as const).map(([value, label]) => (
                    <button
                      key={value}
                      onClick={() => handleOutcome(value)}
                      disabled={submittingOutcome}
                      className={cn(
                        "px-4 py-2 rounded-lg text-sm font-semibold transition-all",
                        call.callbackOutcome === value
                          ? "bg-[#10b981] text-white"
                          : "bg-[#252626] text-[#acabaa] hover:bg-[#3b3b3b] hover:text-[#e7e5e4]",
                        submittingOutcome && "opacity-50 cursor-not-allowed"
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {call.callbackOutcome && (
                  <p className="text-xs text-[#acabaa]">
                    Current: <span className="text-[#e7e5e4] font-medium">{call.callbackOutcome.replace(/_/g, " ")}</span>
                    {call.callbackOutcomeAt && (
                      <> at {format(new Date(call.callbackOutcomeAt), "h:mm a")}</>
                    )}
                  </p>
                )}
              </div>
            )}
```

- [ ] **Step 4: Add callback window display and callback assist section**

After the callback outcome section, add the callback window (when present) and the assist template. Both appear only for unresolved calls:

```tsx
            {/* Callback Window (detail view — CEO criterion: visible in both inbox and detail) */}
            {isUnresolved(call) && (() => {
              const triage = computeTriage(call)
              if (!triage.callbackWindowValid || !triage.callbackWindowStart) return null
              const startTime = new Date(triage.callbackWindowStart)
              const endTime = triage.callbackWindowEnd ? new Date(triage.callbackWindowEnd) : null
              return (
                <div className="space-y-4">
                  <h4 className="font-headline font-bold text-[#acabaa] text-xs uppercase tracking-widest">
                    Callback Window
                  </h4>
                  <div className="bg-[#1e3a5f]/10 p-4 rounded-xl border border-[#93c5fd]/20 flex items-center gap-3">
                    <svg className="h-5 w-5 text-[#93c5fd] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div>
                      <p className="text-sm text-[#e7e5e4] font-semibold">
                        {format(startTime, "h:mm a")}
                        {endTime && <> &ndash; {format(endTime, "h:mm a")}</>}
                      </p>
                      <p className="text-xs text-[#93c5fd]">Customer available</p>
                    </div>
                  </div>
                </div>
              )
            })()}

            {/* Callback Assist */}
            {isUnresolved(call) && (() => {
              const triage = computeTriage(call)
              const template = getAssistTemplate(triage.reason)
              return (
                <div className="space-y-4">
                  <h4 className="font-headline font-bold text-[#acabaa] text-xs uppercase tracking-widest">
                    Callback Opener
                  </h4>
                  <div className="bg-[#252626] p-5 rounded-xl border border-[#484848]/10">
                    <p className="text-sm text-[#e7e5e4] leading-relaxed italic">
                      &ldquo;{template}&rdquo;
                    </p>
                    <p className="text-[10px] text-[#acabaa] mt-3 uppercase tracking-widest">
                      {triage.reason.replace(/_/g, " ")}
                    </p>
                  </div>
                </div>
              )
            })()}
```

- [ ] **Step 5: Commit**

```bash
git add web/src/components/mail/mail-display.tsx
git commit -m "feat(triage): add callback outcome capture and assist template to detail view"
```

---

## Task 11: Vitest Configuration (if needed)

**Files:**
- Check: `web/vitest.config.ts` or `web/package.json` for vitest setup

- [ ] **Step 1: Verify vitest is available**

Run: `cd web && npx vitest --version`

If vitest is not installed:

```bash
cd web && npm install -D vitest
```

Add a `vitest.config.ts` if one doesn't exist:

```typescript
import { defineConfig } from "vitest/config"
import path from "path"

export default defineConfig({
  test: {
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
```

- [ ] **Step 2: Run full test suite**

Run: `cd web && npx vitest run src/lib/__tests__/triage.test.ts`
Expected: All tests PASS

- [ ] **Step 3: Commit (only if config was added)**

```bash
git add web/vitest.config.ts web/package.json web/package-lock.json
git commit -m "chore: add vitest configuration"
```

---

## Task 12: Integration Smoke Test

- [ ] **Step 1: Start dev server**

Run: `cd web && npm run dev`

- [ ] **Step 2: Verify triage block renders**

Open the app. Activity feed should show triage blocks on unresolved call rows with command labels and evidence lines.

- [ ] **Step 3: Verify callback outcome capture**

Open a call detail view. Click one of the outcome buttons. Verify the button highlights and the outcome persists after page reload.

- [ ] **Step 4: Verify stale indicator**

Find a call older than 15 minutes that would be in the "Call now" bucket. Verify it shows a stale time indicator.

- [ ] **Step 5: Verify assist template**

Open an unresolved call detail. Verify the "Callback Opener" section shows a relevant template.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat(triage): missed-call callback triage system complete"
```

---

## Dependency Graph

```
Task 1 (types) ──┬── Task 3 (triage engine)
                  ├── Task 4 (transforms)
                  ├── Task 6 (mutation route)
                  │
Task 2 (migration)    (independent, can run in parallel with Task 1)
                  │
Task 3 ───────────┬── Task 5 (page query + sort)
                  ├── Task 8 (mail sort + timer)
                  ├── Task 9 (mail list UI)
                  └── Task 10 (mail display UI)
                  │
Task 4 ───────────┤
Task 6 ───────────┤
Task 7 (realtime) ┘   (depends on Task 4 for updated transform)
                  │
Task 11 (vitest)  ──── (needed before Task 3 tests run)
Task 12 (smoke)   ──── (after all tasks)
```

**Critical path:** Task 11 (vitest) -> Task 1 (types) -> Task 3 (engine) -> Task 5 + 8 + 9 + 10 -> Task 12

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | DONE_WITH_CONCERNS | 5 proposals, 4 accepted, 1 deferred |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 5 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAR (FULL) | score: 5/10 -> 9/10, 6 decisions |
| Outside Voice | Claude subagent | Blind spot check | 1 | issues_found | 8 findings, 5 substantive, all resolved |

- **AMENDMENTS:** See `~/.claude/plans/dapper-brewing-stroustrup.md` for 12 amendments (6 eng + 6 design)
- **TODOS:** 3 new items (API auth, dashboard stats, unresolved query guarantee)
- **UNRESOLVED:** 0
- **VERDICT:** CEO + ENG + DESIGN CLEARED — ready to implement
