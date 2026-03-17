# Wire Support App to AI Agent via Supabase

**Date:** 2026-03-04
**Status:** Approved

## Problem

The support app (hong-kong-v1) displays static mock emails. It needs to show real missed-call data captured by the CallLock AI agent (Retell AI + V2 backend), which already writes enriched call data to Supabase.

## Decision: Direct Supabase Read (Approach A)

The support app reads directly from the existing Supabase instance — the same tables the V2 backend already writes to (`call_sessions`, `bookings`, `emergency_alerts`). No new webhook endpoints, no data duplication, no V2 backend changes.

```
V2 Backend (Render) → writes → Supabase
Support App (Next.js) → reads + realtime subscription → Supabase
```

## Architecture

### Data Source
- Same Supabase instance as V2 backend (`xboybmqtwsxmdokgzclk.supabase.co`)
- Read from `call_sessions` (conversation_state JSONB), `bookings`, `emergency_alerts`
- Supabase Realtime subscription on `call_sessions` INSERT for live push

### Views
- **Calls tab:** One card per call. Shows customer name/phone, problem summary, urgency badge, booking status, relative time.
- **Jobs tab:** Groups calls by customer phone. Shows customer profile, call count, latest status, revenue tier.

### Detail Panel
- **Call view:** Customer info, problem details, equipment info, urgency, booking status, full transcript.
- **Job view:** Customer profile, booking card, timeline of all calls.

## Data Model

```typescript
type Call = {
  id: string
  customerName: string
  customerPhone: string
  serviceAddress: string
  problemDescription: string
  urgency: "Emergency" | "Urgent" | "Routine" | "Estimate"
  equipmentType: string
  equipmentAge: string
  appointmentBooked: boolean
  appointmentDateTime: string
  endCallReason: string
  transcript: { role: string; content: string }[]
  tags: Record<string, string[]>
  revenueTier: string
  read: boolean          // localStorage, not DB
  createdAt: string
}

type Job = {
  customerPhone: string
  customerName: string
  serviceAddress: string
  calls: Call[]
  latestCall: Call
  booking: Booking | null
  hasEmergency: boolean
}
```

### Source Mapping
- `Call` fields extracted from `call_sessions.conversation_state` JSONB
- `Job` is a client-side groupBy on `Call[]` by `customerPhone`
- `Booking` from `bookings` table, joined by phone
- Read state tracked in localStorage (Set of call IDs)

## Real-time

```typescript
supabase
  .channel('calls')
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'call_sessions'
  }, callback)
  .subscribe()
```

Requires enabling Realtime replication on `call_sessions` table (one-time Supabase dashboard toggle).

## Component Changes

| Current | Becomes | Change |
|---|---|---|
| `page.tsx` | `page.tsx` | Fetch from Supabase instead of static import |
| `mail.tsx` | `mail.tsx` | Add sidebar nav (Calls/Jobs), wire realtime hook |
| `mail-list.tsx` | `call-list.tsx` | Render Call[] or Job[], urgency badges |
| `mail-display.tsx` | `call-display.tsx` | Customer info, problem details, transcript |
| `data/mails.ts` | (deleted) | No longer needed |

### New Files
- `lib/supabase.ts` — Supabase client (server + browser)
- `hooks/use-realtime-calls.ts` — Realtime subscription
- `hooks/use-read-state.ts` — localStorage read tracking
- `lib/transforms.ts` — conversation_state JSONB to Call mapping
- `types/call.ts` — Call, Job, Booking type definitions

## Environment

```
NEXT_PUBLIC_SUPABASE_URL=https://xboybmqtwsxmdokgzclk.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<from V2 backend env>
```

### Supabase Setup (one-time)
1. Enable Realtime on `call_sessions` table
2. Ensure anon role can SELECT from `call_sessions`, `bookings`, `emergency_alerts`

## Constraints
- View-only (no actions yet)
- No auth (single contractor, private app)
- No V2 backend changes
- Replaces existing dashboard at app.calllock.co
