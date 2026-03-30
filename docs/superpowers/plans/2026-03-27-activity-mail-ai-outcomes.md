# Activity/Mail AI Outcomes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote `Escalated by AI` and `Booked by AI` into first-class Activity/mail sections while keeping owner callback workflows intact and making default selection deterministic.

**Architecture:** Keep the existing `assignBucket()` action-queue vs handled taxonomy intact, then derive display-specific sections from that existing output in a new pure helper shared by the server page and client mail view. Move selection priority into testable pure logic so both the first render and subsequent reselection use the same ordering rules.

**Tech Stack:** Next.js 16, React 19, TypeScript, Vitest, existing mail UI components in `web/src/components/mail/`

---

## File Structure

### Existing files to modify

- `web/src/app/page.tsx`
  Responsibility: fetch and pre-order calls before rendering the Activity/mail view.
- `web/src/components/mail/mail.tsx`
  Responsibility: derive sectioned calls, maintain selected call state, render mobile/desktop mail shells.
- `web/src/components/mail/mail-list.tsx`
  Responsibility: render section headers, card states, and lower-priority handled bucket UI.
- `web/src/components/mail/mail-display.tsx`
  Responsibility: detail-pane copy and call outcome summaries.
- `web/src/components/mail/pulse-bar.tsx`
  Responsibility: compact top-of-feed counts and labels.
- `web/src/components/mail/selection-state.ts`
  Responsibility: deterministic initial/stored selection helpers.
- `web/src/components/mail/__tests__/selection-state.test.ts`
  Responsibility: regression coverage for default selection and stored selection validation.
- `web/src/components/mail/__tests__/mail-list.test.tsx`
  Responsibility: lightweight render smoke test for section order, `Other AI Handled` collapse shell, and non-muted booked/escalated cards.
- `web/src/components/mail/lead-intel.tsx`
  Responsibility: right-rail metadata copy for booked calls.
- `web/src/components/mail/mail-copy.ts`
  Responsibility: pure copy helpers for handled summary text and AI receptionist summary text used by the detail pane.
- `web/src/components/mail/__tests__/mail-copy.test.ts`
  Responsibility: regression coverage for booked/escalated detail copy using full `Call` fixtures.
- `web/src/components/mail/dev-fixtures.ts`
  Responsibility: deterministic local Activity/mail fixture data for visual QA in development mode only.
- `web/src/lib/__tests__/triage.test.ts`
  Responsibility: regression coverage for `assignBucket()` and related triage helpers.

### New files to create

- `web/src/lib/mail-sections.ts`
  Responsibility: derive display sections from existing bucket assignments, build ordered section lists, and expose shared selection-priority helpers.
- `web/src/lib/__tests__/mail-sections.test.ts`
  Responsibility: regression coverage for display-section mapping, section ordering, and default-selection priority.

## Task 1: Add Failing Tests For Display Sections

**Files:**
- Create: `web/src/lib/mail-sections.ts`
- Test: `web/src/lib/__tests__/mail-sections.test.ts`
- Modify: `web/src/lib/__tests__/triage.test.ts`

- [ ] **Step 1: Write the failing section-mapping tests**

Add `web/src/lib/__tests__/mail-sections.test.ts` with focused pure-logic cases:

```ts
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
```

- [ ] **Step 2: Write the failing `assignBucket()` regression cases**

Extend `web/src/lib/__tests__/triage.test.ts` with spec-specific assertions that preserve the existing bucket semantics used by the new display helper:

```ts
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd web && npm test -- src/lib/__tests__/mail-sections.test.ts src/lib/__tests__/triage.test.ts
```

Expected:

- `mail-sections.test.ts` fails because `mail-sections.ts` does not exist yet.
- Any new assertions fail because the helper functions are missing.

- [ ] **Step 4: Implement the minimal pure helper**

Create `web/src/lib/mail-sections.ts` with shared display-group logic:

```ts
import { assignBucket, triageSort, followUpSort, type BucketAssignment, type TriageableCall } from "@/lib/triage"

export type MailDisplaySection =
  | "ESCALATED_BY_AI"
  | "NEW_LEADS"
  | "FOLLOW_UPS"
  | "BOOKED_BY_AI"
  | "OTHER_AI_HANDLED"

export function getDisplaySection(
  call: TriageableCall,
  assignment: BucketAssignment = assignBucket(call)
): MailDisplaySection {
  if (assignment.bucket === "ACTION_QUEUE" && assignment.subGroup === "FOLLOW_UP") {
    return "FOLLOW_UPS"
  }
  if (assignment.bucket === "ACTION_QUEUE") return "NEW_LEADS"
  if (assignment.handledReason === "escalated") return "ESCALATED_BY_AI"
  if (assignment.handledReason === "booked") return "BOOKED_BY_AI"
  return "OTHER_AI_HANDLED"
}

export function getDefaultSelectedId<T extends TriageableCall>(calls: T[], now = Date.now()): string | null {
  const sections = partitionMailSections(calls, now)
  return (
    sections.ESCALATED_BY_AI[0]?.id ??
    sections.NEW_LEADS[0]?.id ??
    sections.FOLLOW_UPS[0]?.id ??
    sections.BOOKED_BY_AI[0]?.id ??
    sections.OTHER_AI_HANDLED[0]?.id ??
    null
  )
}
```

Implement the full file with:

- `partitionMailSections(calls, now)` returning sorted arrays for all five sections
- `orderCallsForMail(calls, now)` returning the sections flattened in spec order
- newest-first sorting for `ESCALATED_BY_AI`, `BOOKED_BY_AI`, and `OTHER_AI_HANDLED`

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
cd web && npm test -- src/lib/__tests__/mail-sections.test.ts src/lib/__tests__/triage.test.ts
```

Expected: PASS for the new helper tests and the updated triage regressions.

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/mail-sections.ts web/src/lib/__tests__/mail-sections.test.ts web/src/lib/__tests__/triage.test.ts
git commit -m "test: add mail section mapping coverage"
```

## Task 2: Move Selection Priority Into Shared Logic

**Files:**
- Modify: `web/src/components/mail/selection-state.ts`
- Modify: `web/src/components/mail/__tests__/selection-state.test.ts`
- Modify: `web/src/app/page.tsx`
- Modify: `web/src/components/mail/mail.tsx`
- Use: `web/src/lib/mail-sections.ts`

- [ ] **Step 1: Write the failing selection-state tests**

Update `web/src/components/mail/__tests__/selection-state.test.ts` so it stops assuming “first call wins” and instead asserts spec order:

```ts
import type { TriageableCall } from "@/lib/triage"

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
```

- [ ] **Step 2: Run the selection test to verify it fails**

Run:

```bash
cd web && npm test -- src/components/mail/__tests__/selection-state.test.ts
```

Expected: FAIL because `getInitialSelectedId()` still returns `calls[0]?.id`.

- [ ] **Step 3: Implement the minimal selection-state changes**

Update `web/src/components/mail/selection-state.ts` to delegate to `getDefaultSelectedId()`:

```ts
import { getDefaultSelectedId } from "@/lib/mail-sections"
import type { TriageableCall } from "@/lib/triage"

export function getInitialSelectedId(
  calls: ReadonlyArray<TriageableCall>
): string | null {
  return getDefaultSelectedId([...calls])
}
```

Keep `resolveStoredSelectedId()` unchanged except for the wider type if needed.

- [ ] **Step 4: Apply the shared ordering on the server page**

Update `web/src/app/page.tsx` to replace the manual three-way split with the new helper:

```ts
import { orderCallsForMail } from "@/lib/mail-sections"

// after transformCallRecord()
calls = orderCallsForMail(rows.map((row) => transformCallRecord(row, emptyReadIds)))
```

This keeps the first server-rendered list and the initial selected ID aligned.

- [ ] **Step 5: Use the shared sections and reselection rule in `mail.tsx`**

Update `web/src/components/mail/mail.tsx` to:

- replace the inline `NEW_LEADS / FOLLOW_UPS / AI_HANDLED` splitting with `partitionMailSections()`
- compute `allSectionedCalls` from the five spec-order sections
- update the “auto-select when current selection disappears” effect to use `getDefaultSelectedId(mergedCalls, now)` instead of actionable-only fallback

Minimal effect shape:

```ts
React.useEffect(() => {
  const nextSelectedId = getDefaultSelectedId(mergedCalls, now)
  const stillPresent = mergedCalls.some((call) => call.id === selectedId)
  if (!stillPresent && nextSelectedId !== selectedId) {
    setSelectedId(nextSelectedId)
  }
}, [mergedCalls, now, selectedId])
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
cd web && npm test -- src/components/mail/__tests__/selection-state.test.ts src/lib/__tests__/mail-sections.test.ts
```

Expected: PASS with spec-ordered default selection.

- [ ] **Step 7: Commit**

```bash
git add web/src/components/mail/selection-state.ts web/src/components/mail/__tests__/selection-state.test.ts web/src/app/page.tsx web/src/components/mail/mail.tsx web/src/lib/mail-sections.ts
git commit -m "feat: apply mail section ordering and selection priority"
```

## Task 3: Render The New Top-Level Sections In Mail List And Pulse Bar

**Files:**
- Modify: `web/src/components/mail/mail.tsx`
- Modify: `web/src/components/mail/mail-list.tsx`
- Modify: `web/src/components/mail/pulse-bar.tsx`
- Create: `web/src/components/mail/__tests__/mail-list.test.tsx`
- Create: `web/src/components/mail/dev-fixtures.ts`
- Modify: `web/src/app/page.tsx`

- [ ] **Step 1: Write the failing UI-facing pure assertions**

Before touching JSX, extend `web/src/lib/__tests__/mail-sections.test.ts` with a flattening assertion that codifies the new order:

```ts
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
```

- [ ] **Step 2: Run the focused test to verify it fails if ordering is incomplete**

Run:

```bash
cd web && npm test -- src/lib/__tests__/mail-sections.test.ts
```

Expected: FAIL if the helper is not yet sorting all five sections in spec order.

- [ ] **Step 3: Update `mail.tsx` bucket shape and empty-state copy**

Replace the current:

```ts
{ NEW_LEADS, FOLLOW_UPS, AI_HANDLED }
```

with:

```ts
{
  ESCALATED_BY_AI,
  NEW_LEADS,
  FOLLOW_UPS,
  BOOKED_BY_AI,
  OTHER_AI_HANDLED,
}
```

Update:

- `allSectionedCalls`
- `pulseBarCounts`
- `actionQueueEmpty`
- “All caught up” copy so it no longer says only `AI handled X calls`

Preferred copy when action queues are empty but wins exist:

- `All caught up`
- `AI booked 2 calls and escalated 1 urgent issue`

Keep this assembled from counts rather than hard-coding one phrase.

- [ ] **Step 4: Update `mail-list.tsx` to render the new section headers**

Render in this order:

1. `Escalated by AI`
2. `New Leads`
3. `Follow-ups`
4. `Booked by AI`
5. `Other AI Handled`

Implementation notes:

- stop applying `opacity-50` to booked/escalated cards
- keep quieter treatment only for `OTHER_AI_HANDLED`
- keep `Other AI Handled` collapsible
- keep hidden-when-empty behavior for all sections
- update the sub-count summary to exclude `booked` and `escalated`, since they now have their own sections
- add explicit card-level styling for the new top-level AI outcomes:
  - `ESCALATED_BY_AI` cards should use visible danger treatment, such as a danger-tinted chip, border, icon, or label treatment that clearly differentiates them from neutral queue items
  - `BOOKED_BY_AI` cards should use visible success treatment, such as a success-tinted chip, border, icon, or label treatment that clearly differentiates them from neutral queue items
  - `OTHER_AI_HANDLED` should remain the quietest visual treatment in the handled family

Representative JSX shape:

```tsx
{buckets.ESCALATED_BY_AI.length > 0 && (
  <>
    <h3 className="... text-cl-danger">Escalated by AI ({buckets.ESCALATED_BY_AI.length})</h3>
    <div className="flex flex-col gap-1">
      {buckets.ESCALATED_BY_AI.map((item) => renderCard(item, "ESCALATED_BY_AI"))}
    </div>
  </>
)}
```

- [ ] **Step 5: Update `pulse-bar.tsx` labels**

Change `PulseBarProps` to accept the new counts and show operator-facing labels:

```ts
interface PulseBarProps {
  escalated: number
  leads: number
  followUps: number
  booked: number
  otherHandled: number
}
```

Preferred visible labels:

- `urgent escalations`
- `calls needing you`
- `follow-ups`
- `booked by AI`

`otherHandled` can be omitted from the bar if that keeps the strip cleaner; do not force a noisy archive count into the bar.

- [ ] **Step 6: Add a lightweight render smoke test for `MailList`**

Create `web/src/components/mail/__tests__/mail-list.test.tsx` using `renderToStaticMarkup` from `react-dom/server` so the plan verifies UI-only requirements without introducing a new test framework:

```tsx
import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"
import { MailList } from "../mail-list"

it("renders top-level sections in spec order and keeps Other AI Handled collapsible", () => {
  const html = renderToStaticMarkup(
    <MailList
      items={allItems}
      selected={null}
      onSelect={() => {}}
      buckets={buckets}
      bucketMap={bucketMap}
    />
  )

  expect(html.indexOf("Escalated by AI")).toBeLessThan(html.indexOf("New Leads"))
  expect(html.indexOf("New Leads")).toBeLessThan(html.indexOf("Follow-ups"))
  expect(html.indexOf("Follow-ups")).toBeLessThan(html.indexOf("Booked by AI"))
  expect(html.indexOf("Booked by AI")).toBeLessThan(html.indexOf("Other AI Handled"))
  expect(html).toContain("other-ai-handled-list")
})
```

Also assert that booked/escalated cards do not render the old muted handled opacity class while `Other AI Handled` does.
Also assert that booked/escalated cards render distinct success/danger treatment markers or classes, so the test proves they are visually differentiated from `Other AI Handled`, not merely unmuted.
Also assert that `New Leads` and `Follow-ups` still render their callback controls after the section refactor.

- [ ] **Step 7: Add a deterministic dev fixture path for visual QA**

Create `web/src/components/mail/dev-fixtures.ts` exporting a small `getMailDevFixtures()` helper that returns at least:

- one escalated call
- one new lead
- one follow-up
- one booked call
- one other-handled call

Update `web/src/app/page.tsx` to allow a development-only fixture mode, for example:

```ts
const fixtureMode =
  process.env.NODE_ENV === "development" &&
  process.env.CALLLOCK_MAIL_FIXTURES === "1"

if (fixtureMode) {
  calls = orderCallsForMail(getMailDevFixtures())
  return <Mail initialCalls={calls} />
}
```

Requirements:

- fixture mode must be dev-only
- production behavior must remain Supabase-backed
- the fixture helper should live outside the page component so it can be reused for local QA

- [ ] **Step 8: Run tests to verify logic still passes**

Run:

```bash
cd web && npm test -- src/lib/__tests__/mail-sections.test.ts src/components/mail/__tests__/selection-state.test.ts src/components/mail/__tests__/mail-list.test.tsx src/lib/__tests__/triage.test.ts
```

Expected: PASS. The UI render changes rely on the already-tested helpers, so these logic tests are the regression gate for this task.

- [ ] **Step 9: Commit**

```bash
git add web/src/app/page.tsx web/src/components/mail/mail.tsx web/src/components/mail/mail-list.tsx web/src/components/mail/pulse-bar.tsx web/src/components/mail/dev-fixtures.ts web/src/components/mail/__tests__/mail-list.test.tsx web/src/lib/mail-sections.ts web/src/lib/__tests__/mail-sections.test.ts
git commit -m "feat: surface escalated and booked AI sections"
```

## Task 4: Update Detail Copy And Remove Incorrect Booked Semantics

**Files:**
- Create: `web/src/components/mail/mail-copy.ts`
- Create: `web/src/components/mail/__tests__/mail-copy.test.ts`
- Modify: `web/src/components/mail/mail-display.tsx`
- Modify: `web/src/components/mail/lead-intel.tsx`
- Modify: `web/src/components/mail/mail-list.tsx`
- Modify: `web/src/components/mail/__tests__/mail-list.test.tsx`

- [ ] **Step 1: Write the failing copy-focused assertions**

Create `web/src/components/mail/__tests__/mail-copy.test.ts` with full `Call` fixtures so appointment-time copy can be tested without type gaps:

```ts
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

it("uses booked language in the AI receptionist summary", () => {
  const call = makeCall({ appointmentBooked: true })
  expect(buildAISummary(call)).toContain("appointment was successfully scheduled")
})

it("uses escalation language in the AI receptionist summary", () => {
  const call = makeCall({ isSafetyEmergency: true, problemDescription: "Smell of gas" })
  expect(buildAISummary(call)).toContain("escalated")
})
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
cd web && npm test -- src/components/mail/__tests__/mail-copy.test.ts
```

Expected: FAIL because `mail-copy.ts` does not exist yet.

- [ ] **Step 3: Implement the minimal pure copy helper and wire it in**

Create `web/src/components/mail/mail-copy.ts`:

```ts
import { format, isToday, isTomorrow } from "date-fns"
import type { Call } from "@/types/call"
import type { BucketAssignment } from "@/lib/triage"

export function getHandledSummary(call: Call, assignment: BucketAssignment): string {
  if (assignment.handledReason === "escalated") {
    return call.isSafetyEmergency
      ? "Safety emergency escalated to dispatch"
      : "Urgent issue escalated for immediate handling"
  }
  if (assignment.handledReason === "booked") {
    return "Appointment secured by AI"
  }
  if (assignment.handledReason === "non_customer") {
    return "Blocked: non-customer call (spam/vendor)"
  }
  if (assignment.handledReason === "wrong_number") {
    return "Dismissed: wrong number or out of service area"
  }
  return "Resolved: callback completed"
}

export function buildAISummary(call: Call): string {
  // migrate the current local helper out of mail-display.tsx and update its
  // booked/escalated language to match the spec.
}
```

Then update `web/src/components/mail/mail-display.tsx` to import both helpers instead of defining `buildAISummary()` inline.

- [ ] **Step 4: Update the handled banner and the AI receptionist summary**

Replace the generic booked line:

```tsx
Booked: appointment scheduled by AI
```

with success-forward copy:

```tsx
Appointment secured by AI
```

For escalations, prefer:

```tsx
Safety emergency escalated to dispatch
```

or a generic urgent version when the safety bit is absent.

Keep appointment time rendering below the summary when `appointmentDateTime` exists.

Also update the separate `AI Receptionist Summary` content so it no longer uses generic booked wording and does explicitly mention escalation when the AI escalated the call.

- [ ] **Step 5: Fix the incorrect booked semantic in `lead-intel.tsx`**

Remove the current `appointmentBooked ? "Returning Customer" : "New Prospect"` shortcut. It is not supported by the data model.

Replace with a neutral status card such as:

```tsx
<p className="text-xs text-cl-text-primary font-bold">
  {call.appointmentBooked ? "Appointment Secured" : "Open Lead"}
</p>
<p className="text-[10px] text-cl-text-muted">
  {call.appointmentBooked
    ? "This call ended with a confirmed appointment."
    : "This lead still needs owner review or follow-up."}
</p>
```

- [ ] **Step 6: Update any remaining list/detail handled labels**

Audit `mail-list.tsx` and `mail-display.tsx` for lingering generic copy such as:

- `AI Handled`
- `Booked:`
- `resolved` labels where the spec wants `Booked by AI` or `Escalated by AI`

Do not rename `Other AI Handled`; only the booked/escalated cases change meaning.

Extend `web/src/components/mail/__tests__/mail-list.test.tsx` so the render smoke test also asserts operator-facing list-card labels for handled outcomes, for example:

```tsx
expect(html).toContain("Safety emergency escalated")
expect(html).toContain("Appointment secured")
expect(html).not.toContain(">booked<")
expect(html).not.toContain(">escalated<")
```

This keeps success-forward and escalation-forward card copy covered, not just detail-pane copy.

- [ ] **Step 7: Run tests to verify they pass**

Run:

```bash
cd web && npm test -- src/components/mail/__tests__/mail-copy.test.ts src/lib/__tests__/mail-sections.test.ts src/components/mail/__tests__/selection-state.test.ts src/components/mail/__tests__/mail-list.test.tsx src/lib/__tests__/triage.test.ts
```

Expected: PASS for the copy helper regressions and no failures from earlier section logic.

- [ ] **Step 8: Commit**

```bash
git add web/src/components/mail/mail-copy.ts web/src/components/mail/__tests__/mail-copy.test.ts web/src/components/mail/mail-display.tsx web/src/components/mail/lead-intel.tsx web/src/components/mail/mail-list.tsx web/src/lib/mail-sections.ts web/src/lib/__tests__/mail-sections.test.ts
git commit -m "feat: update AI outcome detail copy"
```

## Task 5: Final Verification Sweep

**Files:**
- Verify all files touched in Tasks 1-4

- [ ] **Step 1: Run the full mail/triage test suite**

Run:

```bash
cd web && npm test -- src/lib/__tests__/triage.test.ts src/lib/__tests__/mail-sections.test.ts src/components/mail/__tests__/selection-state.test.ts src/components/mail/__tests__/mail-list.test.tsx src/components/mail/__tests__/mail-copy.test.ts
```

Expected: PASS with zero failing tests.

- [ ] **Step 2: Run lint on touched files**

Run:

```bash
cd web && npx eslint src/app/page.tsx src/lib/mail-sections.ts src/lib/__tests__/mail-sections.test.ts src/lib/__tests__/triage.test.ts src/components/mail/mail.tsx src/components/mail/mail-list.tsx src/components/mail/mail-display.tsx src/components/mail/mail-copy.ts src/components/mail/__tests__/mail-copy.test.ts src/components/mail/__tests__/mail-list.test.tsx src/components/mail/pulse-bar.tsx src/components/mail/selection-state.ts src/components/mail/__tests__/selection-state.test.ts src/components/mail/lead-intel.tsx
```

Expected: exit code 0.

- [ ] **Step 3: Run a production build**

Run:

```bash
cd web && npm run build
```

Expected: successful Next.js production build with no TypeScript errors.

- [ ] **Step 4: Run a visual verification pass**

Start the app:

```bash
cd web && npm run dev
```

Then verify the Activity/mail view in a browser session or Playwright run against `http://localhost:3000`:

- `Escalated by AI` renders above all other sections when present
- `Booked by AI` renders as its own top-level section
- `Other AI Handled` remains collapsible
- booked/escalated cards are not muted with the old handled opacity treatment
- booked cards visibly use success treatment and escalated cards visibly use danger treatment
- empty-state copy no longer implies every non-actionable item is generic “AI handled”

Before opening the browser, seed deterministic local fixture data through the new pure helpers or a dedicated test harness path rather than editing `CallsPage` inline. The goal is to guarantee at least one escalated, one booked, and one other-handled item in the rendered list without transient production-code edits.
Use the explicit fixture path added in Task 3, Step 7:

```bash
cd web && CALLLOCK_MAIL_FIXTURES=1 npm run dev
```

Then open the Activity/mail view and verify against that deterministic fixture dataset.

- [ ] **Step 5: Inspect the diff**

Run:

```bash
BASE=$(git merge-base HEAD main)
git diff --stat "$BASE"..HEAD -- web/src/app/page.tsx web/src/lib/mail-sections.ts web/src/lib/__tests__/mail-sections.test.ts web/src/lib/__tests__/triage.test.ts web/src/components/mail/mail.tsx web/src/components/mail/mail-list.tsx web/src/components/mail/mail-display.tsx web/src/components/mail/mail-copy.ts web/src/components/mail/__tests__/mail-copy.test.ts web/src/components/mail/__tests__/mail-list.test.tsx web/src/components/mail/pulse-bar.tsx web/src/components/mail/selection-state.ts web/src/components/mail/__tests__/selection-state.test.ts web/src/components/mail/lead-intel.tsx
git diff "$BASE"..HEAD -- web/src/app/page.tsx web/src/lib/mail-sections.ts web/src/lib/__tests__/mail-sections.test.ts web/src/lib/__tests__/triage.test.ts web/src/components/mail/mail.tsx web/src/components/mail/mail-list.tsx web/src/components/mail/mail-display.tsx web/src/components/mail/mail-copy.ts web/src/components/mail/__tests__/mail-copy.test.ts web/src/components/mail/__tests__/mail-list.test.tsx web/src/components/mail/pulse-bar.tsx web/src/components/mail/selection-state.ts web/src/components/mail/__tests__/selection-state.test.ts web/src/components/mail/lead-intel.tsx
```

Expected:

- only Activity/mail-view files changed
- no unrelated dashboard/home changes

- [ ] **Step 6: Final commit if verification required follow-up fixes**

```bash
git add web/src/app/page.tsx web/src/lib/mail-sections.ts web/src/lib/__tests__/mail-sections.test.ts web/src/lib/__tests__/triage.test.ts web/src/components/mail/mail.tsx web/src/components/mail/mail-list.tsx web/src/components/mail/mail-display.tsx web/src/components/mail/mail-copy.ts web/src/components/mail/__tests__/mail-copy.test.ts web/src/components/mail/__tests__/mail-list.test.tsx web/src/components/mail/pulse-bar.tsx web/src/components/mail/selection-state.ts web/src/components/mail/__tests__/selection-state.test.ts web/src/components/mail/lead-intel.tsx
git commit -m "chore: finalize activity mail AI outcome verification"
```

## Notes For The Implementer

- Do not rewrite `assignBucket()` into a brand-new taxonomy. The spec explicitly wants display groups derived from the current action-queue/handled-reason model.
- Keep TDD strict. Every new helper or behavior change must be introduced with a failing test first.
- Prefer pure helper extraction over UI-coupled logic. That keeps the tests fast and avoids introducing a new component-test dependency for this scoped IA change.
- Do not touch `/dashboard`; this plan is Activity/mail only.
