# Unified Bookings Section

**Date**: 2026-03-28
**Status**: Approved (design-reviewed)
**Branch**: `founder/wire-llm-todos`

## Summary

Merge "Booked by AI" and "Scheduled Bookings" into a single "Bookings" section at the top of the Active tab. Remove the dedicated Scheduled Bookings tab. Show the full booking lifecycle (AI booked → operator confirmed) with visual states and sort priority within one unified section.

## Motivation

The two-step booking flow (AI books → operator confirms) reduces no-show rates by giving the customer a human touchpoint. Currently this lifecycle is split across two UI locations — unconfirmed in the Active tab, confirmed in a separate Scheduled Bookings tab. Merging them into one section makes the lifecycle visible at a glance and simplifies navigation from 3 tabs to 2.

## Design

### Tab Structure

Remove the "Scheduled Bookings" tab. Two tabs remain:

- **Timeline** — chronological call feed
- **Active** — prioritized sections (Bookings → New Leads → Escalated → Follow-ups → Other)

### Section: "Bookings"

**Position**: Top of Active tab (position 1, before New Leads).
**Color**: Muted, desaturated green (low-chroma, e.g. `#6b8f71`) that coexists with the Obsidian Archive's monochromatic charcoal palette. Used for indicators and badges only. Section header text uses `on-surface` (`#e7e5e4`), not green.
**Header**: `Bookings ({count})` where count includes all non-cancelled bookings.
**Empty state**: When zero bookings exist, the section is hidden entirely. New Leads becomes the first visible section.

### Booking Card Content Hierarchy

Each booking card displays information in this priority order:

1. **Customer name / phone** (left-aligned, `on-surface`, semibold) — who
2. **Appointment date/time** (right-aligned, same weight as name) — when. This is prominent because scheduling is the card's purpose.
3. **Service type / problem description** (below name, `on-surface-variant`, truncated) — what they need
4. **Lifecycle state indicator** (pulsing dot / checkmark / badge) — status
5. **Booking notes preview** (muted, below problem description, if present) — operational details

### Lifecycle States

| State | `bookingStatus` value | Card indicator | Sort priority |
|-------|----------------------|----------------|---------------|
| Needs confirmation | `null` | Pulsing muted-green dot + "Needs confirmation" tag | 1 (top) |
| Confirmed | `"confirmed"` | Muted-green checkmark + "Confirmed" + timestamp | 2 |
| Cancelled | `"cancelled"` | Card moves to Other AI Handled | N/A |

Within each priority group, sort newest first.

**Note on Reschedule**: The UI exposes two buttons (Confirm / Cancel), not three. If the operator rescheduled the appointment in their field service software (ServiceTitan, HouseCall Pro, etc.), they record the change via the notes field when confirming. The `rescheduled` status remains in the data model for future use but is not exposed as a separate UI action. CallLock is the activity feed, not the scheduling system.

### Calendar Widget

The existing `CalendarWithEventSlots` component at the top of the Bookings section shows all non-cancelled bookings (unconfirmed + confirmed). Visual distinction:

- Unconfirmed: outline/hollow dot on the calendar
- Confirmed: filled muted-green dot

**Mobile (< 640px)**: Calendar collapses to a compact "Next 3 appointments" strip. Tap to expand full calendar. Cards are the primary view on mobile.

### Operator Confirmation UI (Detail Panel)

**Unconfirmed state** (`bookingStatus === null`):

1. **Action buttons**: Confirm | Cancel (row of 2 buttons, `secondary_container` style per Obsidian Archive). 44px minimum touch targets.
2. **Notes field**: Collapsible text area below buttons. Placeholder: "Gate code, special instructions...". Expands on click/focus. Notes are optional for Confirm, submitted with the status change in the same API call.
3. **On action**: Optimistic UI update via existing `PATCH /api/calls/[callId]/booking-status` endpoint. Disable both buttons + show spinner on the clicked button during the API call. On error: toast/inline error message, re-enable buttons, roll back optimistic state. On success: card transitions to confirmed state.

**Confirmed state** (`bookingStatus === "confirmed"`):

- Status badge: muted-green "Confirmed" with timestamp
- Notes displayed as muted text block below the badge (always visible, not behind a tap). If no notes, nothing shows.
- Secondary "Cancel" button available permanently (smaller, tertiary style). Operators can undo accidental confirmations at any time.

### Transition Animation

When the operator confirms a booking:
- Card indicator transitions smoothly from pulsing dot to checkmark (200ms ease)
- Brief muted-green flash on the indicator (200ms) for tactile feedback
- Card slides down in the list below other unconfirmed cards
- Animation respects `prefers-reduced-motion` (instant state change, no animation)

### Accessibility

- Pulsing dot: `aria-label="Needs confirmation"` (static dot when `prefers-reduced-motion` is active)
- Lifecycle badge: `role="status"` for screen reader announcements on state change
- Confirm/Cancel buttons: descriptive `aria-label`s (e.g., "Confirm booking for John Smith")
- All interactive elements: 44px minimum touch targets
- Color: muted green indicators paired with text labels — never color-only differentiation

### Data Model

No schema changes. Existing columns are sufficient:

- `booking_status`: `confirmed | rescheduled | cancelled` (null = unconfirmed)
- `booking_status_at`: ISO timestamp of last status change
- `booking_notes`: free-text operator notes

### Code Changes

#### `web/src/lib/mail-sections.ts`

- Remove `SCHEDULED_BOOKINGS` from `MailDisplaySection` union type
- Remove `SCHEDULED_BOOKINGS` from `MailSections` interface
- Rename `BOOKED_BY_AI` to `BOOKINGS` throughout (internal key)
- `getDisplaySection`: confirmed bookings return `BOOKINGS` (not a separate section). Cancelled bookings return `OTHER_AI_HANDLED`.
- `partitionMailSections`: Remove `scheduled` array. All booked calls go to `bookings` array.
- `orderCallsForMail`: Remove `SCHEDULED_BOOKINGS` from the feed order.

#### `web/src/components/mail/mail-list.tsx`

- Remove `SCHEDULED_BOOKINGS` from `CardSection` type
- Remove third tab ("Scheduled Bookings") from tab bar
- Update Bookings section rendering: sort unconfirmed first, then confirmed (within each group, newest first)
- Update card rendering: appointment date/time right-aligned in card header, lifecycle state indicator (pulsing dot / checkmark)
- Remove `scheduledCount` and associated tab badge logic
- Section label: `"Bookings"`, section header uses `on-surface` color
- Mobile: calendar collapses to compact "Next 3 appointments" strip below 640px

#### `web/src/components/mail/mail-display.tsx`

- Consolidate booking confirmation UI: 2 action buttons (Confirm / Cancel) + collapsible notes field for unconfirmed state
- For confirmed state: status badge + always-visible read-only notes + secondary "Cancel" button
- Remove separate `isScheduled` / `isBookedUnconfirmed` branching — replace with single `isBooking` check with sub-states
- Loading state: disable buttons + spinner on clicked button during API call
- Error state: toast/inline error, re-enable buttons, roll back optimistic state

#### `web/src/components/mail/mail.tsx`

- Remove `SCHEDULED_BOOKINGS` from bucket types and feed ordering
- Update `buckets` object: rename `BOOKED_BY_AI` to `BOOKINGS`
- Update counts: single `bookings` count replaces separate `booked` and `scheduled` counts
- Optimistic update handler: no changes needed (already handles `bookingStatus`)

#### `web/src/components/ui/calendar-with-event-slots.tsx`

- Accept all booking states (not just unconfirmed)
- Visual distinction: outline dot for unconfirmed, filled muted-green for confirmed
- Add responsive collapse: compact strip on mobile (< 640px)

#### Tests

- `web/src/lib/__tests__/mail-sections.test.ts`: Update to use `BOOKINGS` key. Confirmed calls map to `BOOKINGS` not `SCHEDULED_BOOKINGS`. Remove `SCHEDULED_BOOKINGS` expectations.
- `web/src/components/mail/__tests__/mail-list.test.tsx`: Remove scheduled tab tests. Add lifecycle ordering tests (unconfirmed sorts before confirmed). Update section label/color tests. Add card content hierarchy test (appointment time right-aligned).

### Out of Scope

- Dispatcher calendar/schedule view (future consideration)
- Automated confirmation reminders
- Booking time conflict detection
- Reschedule as a separate UI action (data model supports it, UI defers it)
- Date picker for rescheduling (CallLock is the activity feed, not the scheduling system)
