# Unified Bookings Section

**Date**: 2026-03-28
**Status**: Approved
**Branch**: `founder/wire-llm-todos`

## Summary

Merge "Booked by AI" and "Scheduled Bookings" into a single "Bookings" section at the top of the Active tab. Remove the dedicated Scheduled Bookings tab. Show the full booking lifecycle (AI booked → operator confirmed) with visual states and sort priority within one unified green-themed section.

## Motivation

The two-step booking flow (AI books → operator confirms) reduces no-show rates by giving the customer a human touchpoint. Currently this lifecycle is split across two UI locations — unconfirmed in the Active tab, confirmed in a separate Scheduled Bookings tab. Merging them into one section makes the lifecycle visible at a glance and simplifies navigation from 3 tabs to 2.

## Design

### Tab Structure

Remove the "Scheduled Bookings" tab. Two tabs remain:

- **Timeline** — chronological call feed
- **Active** — prioritized sections (Bookings → New Leads → Escalated → Follow-ups → Other)

### Section: "Bookings"

**Position**: Top of Active tab (position 1, before New Leads).
**Color**: Green (`cl-success`) — header, badges, calendar accents.
**Header**: `Bookings ({count})` where count includes all non-cancelled bookings.

### Lifecycle States

| State | `bookingStatus` value | Card indicator | Sort priority |
|-------|----------------------|----------------|---------------|
| Needs confirmation | `null` | Pulsing green dot + "Needs confirmation" tag | 1 (top) |
| Confirmed | `"confirmed"` | Green checkmark + "Confirmed" + timestamp | 2 |
| Rescheduled | `"rescheduled"` | Amber arrow + "Rescheduled" + timestamp | 3 |
| Cancelled | `"cancelled"` | Card moves to Other AI Handled | N/A |

Within each priority group, sort newest first.

### Calendar Widget

The existing `CalendarWithEventSlots` component at the top of the Bookings section shows all bookings (unconfirmed + confirmed + rescheduled). Visual distinction:

- Unconfirmed: outline/hollow dot on the calendar
- Confirmed: filled green dot
- Rescheduled: filled amber dot

### Operator Confirmation UI (Detail Panel)

When viewing an unconfirmed booking (`bookingStatus === null`) in the detail panel:

1. **Action buttons**: Confirm | Reschedule | Cancel (row of 3 buttons)
2. **Notes field**: Collapsible text area below buttons. Placeholder: "Gate code, special instructions...". Expands on click/focus.
3. **On action**: Optimistic UI update via existing `PATCH /api/calls/[callId]/booking-status` endpoint. Card moves to the appropriate lifecycle state. Notes saved in `booking_notes` column.

When viewing a confirmed/rescheduled booking:

- Status badge replaces buttons (green "Confirmed" or amber "Rescheduled" with timestamp)
- Notes displayed read-only if present
- Option to change status (smaller secondary buttons: "Reschedule" / "Cancel")

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
- `getDisplaySection`: confirmed and rescheduled bookings return `BOOKINGS` (not a separate section). Cancelled bookings return `OTHER_AI_HANDLED`.
- `partitionMailSections`: Remove `scheduled` array. All booked calls go to `bookings` array.
- `orderCallsForMail`: Remove `SCHEDULED_BOOKINGS` from the feed order.

#### `web/src/components/mail/mail-list.tsx`

- Remove `SCHEDULED_BOOKINGS` from `CardSection` type
- Remove third tab ("Scheduled Bookings") from tab bar
- Update Bookings section rendering: sort unconfirmed first, then confirmed, then rescheduled (within each group, newest first)
- Update card rendering: show lifecycle state indicator (pulsing dot / checkmark / amber arrow)
- Remove `scheduledCount` and associated tab badge logic
- Section label: `"Bookings"`, color: `"text-cl-success"`

#### `web/src/components/mail/mail-display.tsx`

- Consolidate booking confirmation UI for unconfirmed state: 3 action buttons + collapsible notes field
- For confirmed/rescheduled state: status badge + read-only notes + secondary action buttons
- Remove separate `isScheduled` / `isBookedUnconfirmed` branching — replace with single `isBooking` check with sub-states

#### `web/src/components/mail/mail.tsx`

- Remove `SCHEDULED_BOOKINGS` from bucket types and feed ordering
- Update `buckets` object: rename `BOOKED_BY_AI` to `BOOKINGS`
- Update counts: single `bookings` count replaces separate `booked` and `scheduled` counts
- Optimistic update handler: no changes needed (already handles `bookingStatus`)

#### `web/src/components/ui/calendar-with-event-slots.tsx`

- Accept all booking states (not just unconfirmed)
- Visual distinction: outline dot for unconfirmed, filled green for confirmed, filled amber for rescheduled

#### Tests

- `web/src/lib/__tests__/mail-sections.test.ts`: Update to use `BOOKINGS` key. Confirmed/rescheduled calls map to `BOOKINGS` not `SCHEDULED_BOOKINGS`. Remove `SCHEDULED_BOOKINGS` expectations.
- `web/src/components/mail/__tests__/mail-list.test.tsx`: Remove scheduled tab tests. Add lifecycle ordering tests (unconfirmed sorts before confirmed). Update section label/color tests.

### Out of Scope

- Dispatcher calendar/schedule view (future consideration)
- Automated confirmation reminders
- Booking time conflict detection
