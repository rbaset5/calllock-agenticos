# Unified Bookings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge "Booked by AI" and "Scheduled Bookings" into a single "Bookings" section with lifecycle states, removing the Scheduled Bookings tab.

**Architecture:** Rename the internal `BOOKED_BY_AI` section key to `BOOKINGS` and eliminate `SCHEDULED_BOOKINGS`. Confirmed/rescheduled bookings stay in the same section with sort-based visual differentiation. The detail panel simplifies from 3 buttons to 2 (Confirm / Cancel) with an optional notes field.

**Tech Stack:** React, TypeScript, Vitest, Tailwind CSS, existing Supabase API routes.

**Spec:** `docs/superpowers/specs/2026-03-28-unified-bookings-section.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `web/src/lib/mail-sections.ts` | Modify | Rename BOOKED_BY_AI → BOOKINGS, remove SCHEDULED_BOOKINGS |
| `web/src/lib/__tests__/mail-sections.test.ts` | Modify | Update section mapping assertions |
| `web/src/components/mail/mail-list.tsx` | Modify | Remove 3rd tab, update CardSection type, lifecycle indicators |
| `web/src/components/mail/__tests__/mail-list.test.tsx` | Modify | Remove scheduled tab tests, add lifecycle ordering |
| `web/src/components/mail/mail.tsx` | Modify | Update bucket names, remove scheduled references |
| `web/src/components/mail/mail-display.tsx` | Modify | 2-button confirmation UI + notes field |
| `web/src/components/ui/calendar-with-event-slots.tsx` | Modify | Accept all booking states, dot color by status |

---

### Task 1: Rename section key in mail-sections.ts

**Files:**
- Modify: `web/src/lib/mail-sections.ts`
- Modify: `web/src/lib/__tests__/mail-sections.test.ts`

- [ ] **Step 1: Update test expectations**

In `web/src/lib/__tests__/mail-sections.test.ts`, update all references from `BOOKED_BY_AI` to `BOOKINGS` and `SCHEDULED_BOOKINGS` to `BOOKINGS`. The key change: confirmed and rescheduled bookings now map to `BOOKINGS`, not `SCHEDULED_BOOKINGS`.

Replace the test block starting at line 41:

```typescript
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
```

Update `getDefaultSelectedId` test at line 92:

```typescript
  it("falls back to booked, then other handled, then null", () => {
    expect(getDefaultSelectedId([makeCall({ id: "booked", appointmentBooked: true })])).toBe("booked")
    expect(getDefaultSelectedId([makeCall({ id: "confirmed", appointmentBooked: true, bookingStatus: "confirmed" })])).toBe("confirmed")
    expect(getDefaultSelectedId([makeCall({ id: "wrong", endCallReason: "wrong_number" })])).toBe("wrong")
    expect(getDefaultSelectedId([])).toBeNull()
  })
```

Update `orderCallsForMail` test at line 124:

```typescript
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
      "confirmed",
      "booked",
      "other",
    ])
  })
```

Add a new test for lifecycle sort order within the Bookings section:

```typescript
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npx vitest run src/lib/__tests__/mail-sections.test.ts`
Expected: Multiple failures — `BOOKINGS` not found, sort order doesn't match.

- [ ] **Step 3: Update mail-sections.ts**

Replace the entire file `web/src/lib/mail-sections.ts`:

```typescript
import { assignBucket, triageSort, followUpSort, type BucketAssignment, type TriageableCall } from "@/lib/triage"

export type MailDisplaySection =
  | "ESCALATED_BY_AI"
  | "NEW_LEADS"
  | "FOLLOW_UPS"
  | "BOOKINGS"
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
  if (assignment.handledReason === "booked") {
    if (call.bookingStatus === "cancelled") {
      return "OTHER_AI_HANDLED"
    }
    return "BOOKINGS"
  }
  return "OTHER_AI_HANDLED"
}

export interface MailSections<T extends TriageableCall> {
  ESCALATED_BY_AI: T[]
  NEW_LEADS: T[]
  FOLLOW_UPS: T[]
  BOOKINGS: T[]
  OTHER_AI_HANDLED: T[]
}

function newestFirst<T extends TriageableCall>(calls: T[]): T[] {
  return [...calls].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  )
}

/** Sort bookings: unconfirmed (null) first, then confirmed, then rescheduled. Newest first within each group. */
function bookingSort<T extends TriageableCall>(calls: T[]): T[] {
  const priority: Record<string, number> = { confirmed: 1, rescheduled: 2 }
  return [...calls].sort((a, b) => {
    const ap = a.bookingStatus === null ? 0 : (priority[a.bookingStatus] ?? 3)
    const bp = b.bookingStatus === null ? 0 : (priority[b.bookingStatus] ?? 3)
    if (ap !== bp) return ap - bp
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  })
}

export function partitionMailSections<T extends TriageableCall>(
  calls: T[],
  now: number = Date.now()
): MailSections<T> {
  const escalated: T[] = []
  const newLeads: T[] = []
  const followUps: T[] = []
  const bookings: T[] = []
  const otherHandled: T[] = []

  for (const call of calls) {
    const assignment = assignBucket(call)
    const section = getDisplaySection(call, assignment)
    if (section === "ESCALATED_BY_AI") escalated.push(call)
    else if (section === "NEW_LEADS") newLeads.push(call)
    else if (section === "FOLLOW_UPS") followUps.push(call)
    else if (section === "BOOKINGS") bookings.push(call)
    else otherHandled.push(call)
  }

  return {
    ESCALATED_BY_AI: newestFirst(escalated),
    NEW_LEADS: triageSort(newLeads, now),
    FOLLOW_UPS: followUpSort(followUps),
    BOOKINGS: bookingSort(bookings),
    OTHER_AI_HANDLED: newestFirst(otherHandled),
  }
}

export function orderCallsForMail<T extends TriageableCall>(
  calls: T[],
  now: number = Date.now()
): T[] {
  const sections = partitionMailSections(calls, now)
  return [
    ...sections.ESCALATED_BY_AI,
    ...sections.NEW_LEADS,
    ...sections.FOLLOW_UPS,
    ...sections.BOOKINGS,
    ...sections.OTHER_AI_HANDLED,
  ]
}

export function getDefaultSelectedId<T extends TriageableCall>(
  calls: T[],
  now: number = Date.now()
): string | null {
  const sections = partitionMailSections(calls, now)
  return (
    sections.ESCALATED_BY_AI[0]?.id ??
    sections.NEW_LEADS[0]?.id ??
    sections.FOLLOW_UPS[0]?.id ??
    sections.BOOKINGS[0]?.id ??
    sections.OTHER_AI_HANDLED[0]?.id ??
    null
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/lib/__tests__/mail-sections.test.ts`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/mail-sections.ts web/src/lib/__tests__/mail-sections.test.ts
git commit -m "refactor: rename BOOKED_BY_AI to BOOKINGS, remove SCHEDULED_BOOKINGS section"
```

---

### Task 2: Update mail.tsx bucket wiring

**Files:**
- Modify: `web/src/components/mail/mail.tsx`

- [ ] **Step 1: Update bucket type and references**

In `web/src/components/mail/mail.tsx`, make these changes:

1. Replace the `buckets` object construction (lines 74-81) to use the new key:

```typescript
    return {
      buckets: {
        ESCALATED_BY_AI: sections.ESCALATED_BY_AI,
        NEW_LEADS: sections.NEW_LEADS,
        FOLLOW_UPS: sections.FOLLOW_UPS,
        BOOKINGS: sections.BOOKINGS,
        OTHER_AI_HANDLED: sections.OTHER_AI_HANDLED,
      },
      bucketMap: map,
    }
```

2. Update `allSectionedCalls` (lines 88-94):

```typescript
  const allSectionedCalls = React.useMemo(
    () => [
      ...buckets.BOOKINGS,
      ...buckets.NEW_LEADS,
      ...buckets.ESCALATED_BY_AI,
      ...buckets.FOLLOW_UPS,
      ...buckets.OTHER_AI_HANDLED,
    ],
    [buckets]
  )
```

3. Update `pulseBarCounts` (lines 189-196):

```typescript
  const pulseBarCounts = React.useMemo(() => ({
    escalated: buckets.ESCALATED_BY_AI.length,
    leads: buckets.NEW_LEADS.length,
    followUps: buckets.FOLLOW_UPS.length,
    bookings: buckets.BOOKINGS.length,
    otherHandled: buckets.OTHER_AI_HANDLED.length,
  }), [buckets])
```

4. Update `actionQueueEmpty` (lines 216-220):

```typescript
  const actionQueueEmpty =
    buckets.ESCALATED_BY_AI.length === 0 &&
    buckets.NEW_LEADS.length === 0 &&
    buckets.FOLLOW_UPS.length === 0 &&
    buckets.BOOKINGS.length === 0
```

5. Update `totalHandled` (lines 222-223):

```typescript
  const totalHandled = buckets.OTHER_AI_HANDLED.length
```

6. Update `buildCaughtUpSubtitle` (lines 225-233) — replace `buckets.BOOKED_BY_AI` with `buckets.BOOKINGS`:

```typescript
  function buildCaughtUpSubtitle(): string {
    const bookedCount = buckets.BOOKINGS.length
    const escalatedCount = buckets.ESCALATED_BY_AI.length
    if (bookedCount === 0 && escalatedCount === 0) return ""
    const parts: string[] = []
    if (bookedCount > 0) parts.push(`AI booked ${bookedCount} ${bookedCount === 1 ? "call" : "calls"}`)
    if (escalatedCount > 0) parts.push(`escalated ${escalatedCount} urgent ${escalatedCount === 1 ? "issue" : "issues"}`)
    return parts.join(" and ")
  }
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit 2>&1 | head -30`
Expected: Type errors in `mail-list.tsx` (still references old keys). That's expected — we fix it in Task 3.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/mail/mail.tsx
git commit -m "refactor: update mail.tsx to use BOOKINGS bucket key"
```

---

### Task 3: Update mail-list.tsx — remove tab, update types

**Files:**
- Modify: `web/src/components/mail/mail-list.tsx`
- Modify: `web/src/components/mail/__tests__/mail-list.test.tsx`

- [ ] **Step 1: Update test expectations**

In `web/src/components/mail/__tests__/mail-list.test.tsx`:

1. Replace the `buckets` object (lines 54-61):

```typescript
const buckets = {
  ESCALATED_BY_AI: [escalatedCall],
  NEW_LEADS: [leadCall],
  FOLLOW_UPS: [followUpCall],
  BOOKINGS: [bookedCall, scheduledCall],
  OTHER_AI_HANDLED: [otherCall],
}
```

2. Update the first render test (line 84, 87) — replace `"Booked by AI"` with `"Bookings"` and remove `"Scheduled Bookings"`:

```typescript
  it("renders Active tab content by default and exposes all tab buttons", () => {
    const html = renderToStaticMarkup(
      <MailList
        items={allItems}
        selected={null}
        onSelect={() => {}}
        buckets={buckets}
        bucketMap={bucketMap}
      />
    )

    expect(html).toContain("Bookings")
    expect(html).toContain("New Leads")
    expect(html).toContain("Timeline")
    expect(html).not.toContain("Scheduled Bookings")
  })
```

3. Update the ordering test (line 90) — replace `"Booked by AI"` with `"Bookings"`:

```typescript
  it("renders Bookings FIRST in active tab, before New Leads", () => {
    const html = renderToStaticMarkup(
      <MailList
        items={allItems}
        selected={null}
        onSelect={() => {}}
        buckets={buckets}
        bucketMap={bucketMap}
      />
    )

    expect(html.indexOf("Bookings")).toBeLessThan(html.indexOf("New Leads"))
  })
```

4. Update `sectionLabel` test (lines 198-199):

```typescript
    expect(sectionLabel("BOOKINGS")).toBe("Bookings")
```

Remove the `SCHEDULED_BOOKINGS` line entirely.

5. Update `sectionColor` test (lines 209-210):

```typescript
    expect(sectionColor("BOOKINGS")).toBe("text-cl-success")
```

Remove the `SCHEDULED_BOOKINGS` line entirely.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npx vitest run src/components/mail/__tests__/mail-list.test.ts`
Expected: Failures — old keys still in production code.

- [ ] **Step 3: Update mail-list.tsx**

Make these changes in `web/src/components/mail/mail-list.tsx`:

1. Update `MailListProps` interface (lines 40-47) — replace bucket type:

```typescript
  buckets?: {
    ESCALATED_BY_AI: Call[]
    NEW_LEADS: Call[]
    FOLLOW_UPS: Call[]
    BOOKINGS: Call[]
    OTHER_AI_HANDLED: Call[]
  }
```

2. Update `CardSection` type (line 120):

```typescript
type CardSection = "ESCALATED_BY_AI" | "NEW_LEADS" | "FOLLOW_UPS" | "BOOKINGS" | "OTHER_AI_HANDLED"
```

3. Update `sectionLabel` (lines 122-131):

```typescript
export function sectionLabel(section: CardSection): string {
  const labels: Record<CardSection, string> = {
    ESCALATED_BY_AI: "Escalated",
    NEW_LEADS: "New",
    FOLLOW_UPS: "Follow-up",
    BOOKINGS: "Bookings",
    OTHER_AI_HANDLED: "Handled",
  }
  return labels[section] ?? ""
}
```

4. Update `sectionColor` (lines 134-143):

```typescript
export function sectionColor(section: CardSection): string {
  const colors: Record<CardSection, string> = {
    ESCALATED_BY_AI: "text-cl-danger",
    NEW_LEADS: "text-cl-accent",
    FOLLOW_UPS: "text-cl-text-muted",
    BOOKINGS: "text-cl-success",
    OTHER_AI_HANDLED: "text-cl-text-muted/60",
  }
  return colors[section] ?? "text-cl-text-muted"
}
```

5. Update `activeTab` state (line 163) — remove `"scheduled"` option:

```typescript
  const [activeTab, setActiveTab] = useState<"timeline" | "active">("active")
```

6. Remove `reschedulingId` and `rescheduleDateTime` state (lines 165-166) — delete these lines.

7. Update `timelineCalls` memo (lines 220-234) — replace `BOOKED_BY_AI` and `SCHEDULED_BOOKINGS` with `BOOKINGS`:

```typescript
  const timelineCalls = useMemo(() => {
    const source = buckets
      ? [
          ...buckets.ESCALATED_BY_AI,
          ...buckets.NEW_LEADS,
          ...buckets.FOLLOW_UPS,
          ...buckets.BOOKINGS,
          ...buckets.OTHER_AI_HANDLED,
        ]
      : items
    return [...source].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    )
  }, [buckets, items])
```

8. Update `timelineSectionById` memo (lines 254-265) — replace old keys:

```typescript
  const timelineSectionById = useMemo(() => {
    const sectionById = new Map<string, CardSection>()
    if (buckets) {
      for (const call of buckets.ESCALATED_BY_AI) sectionById.set(call.id, "ESCALATED_BY_AI")
      for (const call of buckets.NEW_LEADS) sectionById.set(call.id, "NEW_LEADS")
      for (const call of buckets.FOLLOW_UPS) sectionById.set(call.id, "FOLLOW_UPS")
      for (const call of buckets.BOOKINGS) sectionById.set(call.id, "BOOKINGS")
      for (const call of buckets.OTHER_AI_HANDLED) sectionById.set(call.id, "OTHER_AI_HANDLED")
    }
    return sectionById
  }, [buckets])
```

9. In the `renderCard` function, update the `BOOKED_BY_AI` indicator (around line 304) to show lifecycle state:

Replace the existing `{section === "BOOKED_BY_AI" && (` block with:

```typescript
        {section === "BOOKINGS" && (
          <div
            className="h-6 w-6 rounded-full flex items-center justify-center"
            aria-label={item.bookingStatus === "confirmed" ? "Confirmed" : item.bookingStatus === "rescheduled" ? "Rescheduled" : "Needs confirmation"}
          >
            {item.bookingStatus === "confirmed" ? (
              <CheckCircle2 className="h-4 w-4 text-cl-success" />
            ) : item.bookingStatus === "rescheduled" ? (
              <RotateCcw className="h-4 w-4 text-amber-400" />
            ) : (
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cl-success opacity-60 motion-reduce:animate-none" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-cl-success" />
              </span>
            )}
          </div>
        )}
```

10. Remove the Scheduled panel rendering block (around lines 315-329) that shows `CONF`/`IRMD` and `RSCH`/`EDLD` labels. This is no longer needed — the lifecycle indicator above handles it.

11. In the card body, update the `BOOKED_BY_AI` appointment time rendering (around line 422) to show for all `BOOKINGS`:

Replace `{section === "BOOKED_BY_AI" && (` with `{section === "BOOKINGS" && (`.

Also update the appointment time to be right-aligned in the card header. In the card header div (the flex row with the customer name), add the appointment time on the right:

```typescript
          {section === "BOOKINGS" && item.appointmentDateTime && (
            <span className="text-xs font-mono text-cl-text-primary shrink-0">
              {formatAppointmentTime(item.appointmentDateTime)}
            </span>
          )}
```

12. Remove the Scheduled status badge rendering (around lines 488-497).

13. Remove the "Scheduled Bookings" tab button entirely (lines 650-673). The tab bar should only have "Timeline" and "Active".

14. Remove the "Scheduled Bookings tab" content block (lines 831-853).

15. Update the `bookedCount` and `scheduledCount` variables (lines 614-616):

```typescript
    const bookingsCount = buckets.BOOKINGS.length
    const otherCount = buckets.OTHER_AI_HANDLED.length
```

16. In the Active tab content, update the calendar section (around line 735-744):

Replace `bookedCount` with `bookingsCount` and `buckets.BOOKED_BY_AI` with `buckets.BOOKINGS`:

```typescript
              {bookingsCount > 0 && (
                <div className="-ml-4">
                  <CalendarWithEventSlots
                    calls={buckets.BOOKINGS}
                    selectedCallId={selected}
                    onSelectCall={onSelect}
                    onBookingStatusChange={onBookingStatusChange}
                  />
                </div>
              )}
```

17. Update the Bookings section header (currently "Booked by AI") — this section header appears before the calendar. If there's a heading that says "Booked by AI", rename it to "Bookings":

Find any `"Booked by AI"` string and replace with `"Bookings"`.

- [ ] **Step 4: Run tests**

Run: `cd web && npx vitest run src/components/mail/__tests__/mail-list.test.ts`
Expected: All tests pass.

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit 2>&1 | head -30`
Expected: No errors (or only errors in mail-display.tsx which we fix in Task 4).

- [ ] **Step 6: Commit**

```bash
git add web/src/components/mail/mail-list.tsx web/src/components/mail/__tests__/mail-list.test.tsx
git commit -m "feat: unified Bookings section with lifecycle indicators, remove Scheduled tab"
```

---

### Task 4: Simplify mail-display.tsx confirmation UI

**Files:**
- Modify: `web/src/components/mail/mail-display.tsx`

- [ ] **Step 1: Update section detection**

Replace lines 180-181:

```typescript
  const isBooking = mailSection === "BOOKINGS"
  const isBookingUnconfirmed = isBooking && call.bookingStatus === null
  const isBookingConfirmed = isBooking && (call.bookingStatus === "confirmed" || call.bookingStatus === "rescheduled")
```

Remove the old `isBookedUnconfirmed` and `isScheduled` variables.

- [ ] **Step 2: Remove reschedule picker state**

Remove `showReschedulePicker`, `setShowReschedulePicker`, `rescheduleDateTime`, `setRescheduleDateTime` state variables (lines 52-53). They are no longer needed since the Reschedule button is removed.

- [ ] **Step 3: Replace unconfirmed booking UI (lines 279-351)**

Replace the `{isBookedUnconfirmed && (` block with:

```typescript
        {isBookingUnconfirmed && (
          <div className="bg-cl-bg-panel p-4 rounded-md space-y-3">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cl-success opacity-60 motion-reduce:animate-none" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-cl-success" />
              </span>
              <p className="text-sm text-cl-success font-semibold">AI booked — needs confirmation</p>
            </div>
            {call.appointmentDateTime && (
              <p className="text-sm text-cl-text-primary font-medium">
                {(() => {
                  try {
                    const d = new Date(call.appointmentDateTime)
                    if (isToday(d)) return `Today @ ${format(d, "h:mm a")}`
                    if (isTomorrow(d)) return `Tomorrow @ ${format(d, "h:mm a")}`
                    return format(d, "MMM d @ h:mm a")
                  } catch { return call.appointmentDateTime }
                })()}
              </p>
            )}
            <details className="group">
              <summary className="text-xs text-cl-text-muted cursor-pointer hover:text-cl-text-primary select-none">
                Add notes (optional)
              </summary>
              <textarea
                placeholder="Gate code, special instructions..."
                className="mt-2 w-full h-20 px-3 py-2 rounded-md bg-cl-bg-chip text-cl-text-primary text-sm border border-cl-border/20 focus:outline-none focus:border-cl-accent resize-none"
                id={`booking-notes-${call.id}`}
              />
            </details>
            <div className="flex flex-wrap gap-2">
              <button
                disabled={submittingBooking}
                onClick={async () => {
                  const notes = (document.getElementById(`booking-notes-${call.id}`) as HTMLTextAreaElement | null)?.value || ""
                  const body: Record<string, string> = { status: "confirmed" }
                  if (notes) body.notes = notes
                  onBookingStatusChange?.(call.id, "confirmed")
                  setSubmittingBooking(true)
                  try {
                    const res = await fetch(`/api/calls/${call.id}/booking-status`, {
                      method: "PATCH",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(body),
                    })
                    if (!res.ok) throw new Error("not-ok")
                  } catch {
                    if (call.bookingStatus !== null) onBookingStatusChange?.(call.id, call.bookingStatus)
                    toast.error("Couldn't save — try again")
                  } finally {
                    setSubmittingBooking(false)
                  }
                }}
                className="px-4 py-2 rounded-full text-[0.6875rem] uppercase font-semibold bg-cl-success/20 text-cl-success hover:bg-cl-success/30 disabled:opacity-50 min-h-[44px]"
                aria-label={`Confirm booking for ${call.customerName || "caller"}`}
              >
                <CheckCircle2 className="h-3 w-3 inline mr-1" />
                {submittingBooking ? "Saving..." : "Confirm"}
              </button>
              <button
                disabled={submittingBooking}
                onClick={() => handleBookingAction("cancelled")}
                className="px-4 py-2 rounded-full text-[0.6875rem] uppercase font-semibold bg-cl-bg-chip text-cl-text-muted hover:bg-cl-bg-chip-hover disabled:opacity-50 min-h-[44px]"
                aria-label={`Cancel booking for ${call.customerName || "caller"}`}
              >
                <X className="h-3 w-3 inline mr-1" />
                Cancel
              </button>
            </div>
          </div>
        )}
```

- [ ] **Step 4: Replace confirmed booking UI (lines 354-380)**

Replace the `{isScheduled && (` block with:

```typescript
        {isBookingConfirmed && (
          <div className="bg-cl-success/10 p-4 rounded-md space-y-2">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-cl-success" />
              <p className="text-sm text-cl-success font-semibold">
                Confirmed
              </p>
              {call.bookingStatusAt && (
                <span className="text-[0.6875rem] text-cl-text-muted">
                  {formatDistanceToNow(new Date(call.bookingStatusAt), { addSuffix: true })}
                </span>
              )}
            </div>
            {call.appointmentDateTime && (
              <p className="text-sm text-cl-text-primary font-medium">
                {(() => {
                  try {
                    const d = new Date(call.appointmentDateTime)
                    if (isToday(d)) return `Today @ ${format(d, "h:mm a")}`
                    if (isTomorrow(d)) return `Tomorrow @ ${format(d, "h:mm a")}`
                    return format(d, "MMM d @ h:mm a")
                  } catch { return call.appointmentDateTime }
                })()}
              </p>
            )}
            {call.bookingNotes && (
              <p className="text-xs text-cl-text-muted mt-1">{call.bookingNotes}</p>
            )}
            <button
              disabled={submittingBooking}
              onClick={() => handleBookingAction("cancelled")}
              className="px-3 py-1.5 rounded-full text-[0.625rem] uppercase font-semibold bg-cl-bg-chip text-cl-text-muted hover:bg-cl-bg-chip-hover disabled:opacity-50 min-h-[44px]"
              aria-label={`Cancel booking for ${call.customerName || "caller"}`}
            >
              <X className="h-3 w-3 inline mr-1" />
              Cancel booking
            </button>
          </div>
        )}
```

- [ ] **Step 5: Update the outcome buttons section**

Find where `isBookedUnconfirmed` or `isScheduled` are referenced in the outcome buttons conditional (around line 435 where callback outcome dropdown is rendered). Replace references with `isBookingUnconfirmed` and `isBookingConfirmed`.

The pattern `"scheduled"` in the outcome config dropdown (line 435) should also be reviewed — if the outcome buttons should be hidden for bookings, add `!isBooking` to the conditional.

- [ ] **Step 6: Verify TypeScript compiles cleanly**

Run: `cd web && npx tsc --noEmit 2>&1 | head -30`
Expected: No type errors.

- [ ] **Step 7: Commit**

```bash
git add web/src/components/mail/mail-display.tsx
git commit -m "feat: 2-button confirmation UI with optional notes for bookings"
```

---

### Task 5: Update calendar widget for all booking states

**Files:**
- Modify: `web/src/components/ui/calendar-with-event-slots.tsx`

- [ ] **Step 1: Update dot color logic**

In `web/src/components/ui/calendar-with-event-slots.tsx`, find where booking dots are rendered on the calendar. Update the dot styling to distinguish by `bookingStatus`:

- `bookingStatus === null` → outline dot (ring-only, e.g. `ring-2 ring-cl-success bg-transparent`)
- `bookingStatus === "confirmed"` → filled green dot (`bg-cl-success`)
- `bookingStatus === "rescheduled"` → filled amber dot (`bg-amber-400`)

Find the existing dot rendering (around line 153 where `"Booked by AI"` appears) and update:

```typescript
  const dotClass = call.bookingStatus === "confirmed"
    ? "bg-cl-success"
    : call.bookingStatus === "rescheduled"
      ? "bg-amber-400"
      : "ring-2 ring-cl-success bg-transparent"
```

Also update any `"Booked by AI"` text to `"Bookings"`.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit 2>&1 | head -30`
Expected: Clean.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/ui/calendar-with-event-slots.tsx
git commit -m "feat: calendar dots distinguish unconfirmed, confirmed, and rescheduled bookings"
```

---

### Task 6: Update booking-status API to accept notes

**Files:**
- Modify: `web/src/app/api/calls/[callId]/booking-status/route.ts`

- [ ] **Step 1: Check if notes are already supported**

Read `web/src/app/api/calls/[callId]/booking-status/route.ts` to verify if the `notes` field is already accepted in the request body and saved to `booking_notes`.

- [ ] **Step 2: Add notes support if missing**

If the route doesn't already handle `notes`, update the request body parsing and the Supabase update to include:

```typescript
  const notes = body.notes as string | undefined
  // ... in the .update() call:
  booking_notes: notes ?? null,
```

- [ ] **Step 3: Run existing API tests**

Run: `cd web && npx vitest run src/app/api/calls/\\[callId\\]/booking-status/__tests__/route.test.ts`
Expected: All existing tests pass. Add a test for notes if not already covered.

- [ ] **Step 4: Commit**

```bash
git add web/src/app/api/calls/\[callId\]/booking-status/route.ts
git commit -m "feat: accept notes field in booking-status API"
```

---

### Task 7: Mobile calendar collapse (deferred)

The spec calls for the calendar widget to collapse to a compact "Next 3 appointments" strip on mobile (< 640px). This is a standalone responsive enhancement to `CalendarWithEventSlots` that doesn't block the core unified bookings feature. Implement after the core merge is verified.

---

### Task 8: Run full test suite and verify

- [ ] **Step 1: Run all tests**

Run: `cd web && npx vitest run`
Expected: All tests pass.

- [ ] **Step 2: Run TypeScript check**

Run: `cd web && npx tsc --noEmit`
Expected: Clean.

- [ ] **Step 3: Verify dev server**

Run: `cd web && npm run dev` and visually check:
- Active tab shows "Bookings" section at top (not "Booked by AI")
- Only 2 tabs visible: "Timeline" and "Active" (no "Scheduled Bookings")
- Booking cards show pulsing dot for unconfirmed, checkmark for confirmed
- Detail panel shows Confirm/Cancel buttons with optional notes for unconfirmed
- Detail panel shows "Confirmed" badge with read-only notes for confirmed

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address integration issues from unified bookings merge"
```
