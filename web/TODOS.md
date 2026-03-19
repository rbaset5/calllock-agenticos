# Deferred Work

Items considered during the Supabase wiring design review and explicitly deferred.

## 1. Jobs Tab (Group Calls by Customer Phone)

**What:** Add a "Jobs" view that groups calls by customer phone number, showing booking status and a timeline of all calls from each customer.

**Why:** Contractors think in terms of jobs (one customer, one problem), not individual calls. A customer may call 3 times about the same AC issue — the Jobs tab collapses these into one card with full context. This was part of the original approved design but deferred to reduce scope for the initial wiring.

**Context:** The types file (`src/types/call.ts`) and transforms file (`src/lib/transforms.ts`) are structured to support this. To implement:
- Add `Job`, `Booking` types to `types/call.ts`
- Add `groupCallsIntoJobs()` and `transformBooking()` to `transforms.ts`
- Query `bookings` and `emergency_alerts` tables in `page.tsx`
- Add a Calls/Jobs toggle in `mail.tsx` (use `Phone` and `Briefcase` icons from lucide)
- Add `JobList` and `JobDisplay` components (or extend existing list/display with a `view` prop)
- The original design doc (`docs/plans/2026-03-04-supabase-wiring-design.md`) has the full spec for Jobs tab card mapping and detail panel.

**Depends on:** Supabase wiring (must be complete and working first).

## 2. Lazy-Load Transcript Error/Loading State

**Status:** Implemented 2026-03-19 in `src/components/mail/mail-display.tsx`.

**What:** Add a loading spinner and "Transcript unavailable" fallback for the detail panel's transcript section.

**Why:** The implementation lazy-loads `retell_data` (which contains the transcript) only when a call is selected — it's not fetched in the initial list load (performance optimization from review Issue 10A). If this secondary fetch fails (Supabase timeout, missing data), the transcript section would silently show nothing. A loading state makes the fetch visible; an error fallback makes failures explicit.

**Context:** The lazy-load happens in `mail-display.tsx` when `selectedCallId` changes. The fetch calls `supabase.from("call_sessions").select("retell_data").eq("call_id", id)`. Add:
- A `loading` state while fetch is in-flight (show a spinner or skeleton)
- A `catch` handler that sets an error state (show "Transcript unavailable — try refreshing")
- Both states render inside the transcript `<section>` in `mail-display.tsx`

**Depends on:** Supabase wiring complete.

## 3. Search Wiring

**Status:** Implemented 2026-03-19 in `src/components/mail/mail.tsx`, `src/components/mail/mail-list.tsx`, and `src/hooks/use-realtime-calls.ts`.

**What:** Wire the existing search input placeholder to filter calls by customer name, phone number, or problem description.

**Why:** The search input already exists in `mail.tsx` (both mobile and desktop layouts) but does nothing. For a contractor with 50+ calls, finding a specific customer by name or phone is essential.

**Context:** This can be a pure client-side filter on the existing `calls` array — no new Supabase query needed since we already load up to 100 calls. Implementation:
- Add a `searchQuery` state in `mail.tsx`
- Wire the `<Input>` `onChange` to update it
- Filter `calls` array with a case-insensitive match against `customerName`, `customerPhone`, and `problemDescription`
- Pass filtered results to the list component
- Consider debouncing the filter (300ms) if the list is large

**Depends on:** Supabase wiring complete.
