# Seed Data / Demo Mode Design

**Date:** 2026-03-05
**Status:** Approved

## Goal

Add a demo mode triggered via `?demo=true` URL param that swaps in rich static seed data instead of fetching from Supabase. Intended for stakeholder demos and internal testing.

## Approach: Static JSON File + Conditional Branch (Option A)

Chosen for simplicity — no extra abstraction, easy to share a link, fully typed.

---

## Components

### 1. `src/data/seed-calls.ts`

Exports `SEED_CALLS: Call[]` — 30+ realistic entries covering:

- All 4 urgency tiers: `LifeSafety`, `Urgent`, `Routine`, `Estimate`
- All 10 `HVACIssueType` values
- All 12 `EndCallReason` values (distributed across calls)
- Mix of: booked appointments, safety emergencies, urgent escalations, unread/read states
- Each call has a 2–4 exchange `transcript` (agent/user turns)
- Realistic names, Phoenix/Scottsdale addresses, equipment brands (Carrier, Trane, Lennox)
- `createdAt` timestamps spread over the past 7 days

### 2. `src/app/page.tsx` — Demo Branch

```ts
if (searchParams?.demo === "true") {
  return <Mail calls={SEED_CALLS} isDemo={true} />
}
// else fetch from Supabase as before
```

No other page logic changes. The server component already receives `searchParams` in Next.js App Router.

### 3. `src/components/mail/mail.tsx` — Disable Realtime in Demo

- Accept `isDemo?: boolean` prop
- Pass to `useRealtimeCalls` hook
- Hook skips Supabase subscription when `isDemo === true`

### 4. Demo Banner

Rendered inside `mail.tsx` when `isDemo` is true:

```
"Demo mode — showing sample HVAC calls"
```

Small, non-dismissible top bar. Clearly communicates context to stakeholders.

---

## What Changes

| File | Change |
|---|---|
| `src/data/seed-calls.ts` | New — exports `SEED_CALLS: Call[]` |
| `src/app/page.tsx` | Add `?demo=true` branch |
| `src/components/mail/mail.tsx` | Accept `isDemo` prop, show banner |
| `src/hooks/use-realtime-calls.ts` | Skip subscription when `isDemo` |

## What Does Not Change

- Supabase schema, transforms, or types
- Existing production fetch path
- Any auth or middleware logic
