# CallLock App Migration Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the CallLock App from hong-kong-v1 into rabat's `web/` directory, swapping the data layer from `call_sessions` to `call_records`. Auth (Task 10) requires a separate planning session.

**Architecture:** First patch the backend to persist all fields the app needs (equipment, booking, callback, end_call_reason, recording URL). Then copy the Next.js app into `web/`, rewrite the data layer (types, transforms, queries, realtime subscription) to read from `call_records` instead of `call_sessions`, update metadata/naming, and add deployment config. UI components stay unchanged.

**Tech Stack:** Next.js 16, React 19, shadcn/ui, Supabase JS, Tailwind CSS 4, Vitest

**Pre-requisite (DONE):** Backend fixes to pipeline, repository, and post_call_router have already been applied. See Task 0.

---

### Task 0: Backend data layer fixes (DONE)

These changes ensure `call_records` contains all data the app needs.

**Files already modified:**
- `harness/src/voice/extraction/pipeline.py` — Promote `equipment_type`, `equipment_brand`, `equipment_age`, `appointment_booked`, `callback_type` from `state` to `result` so they persist in `extracted_fields`
- `harness/src/db/supabase_repository.py` — `update_call_record_extraction` now accepts and writes `end_call_reason`, `booking_id`, `callback_scheduled`, `call_duration_seconds`, `call_recording_url`
- `harness/src/db/local_repository.py` — Mirror of above for local dev
- `harness/src/db/repository.py` — Facade updated to pass new kwargs
- `harness/src/voice/post_call_router.py` — Passes all 5 values into `update_call_record_extraction`

**Tests:** 249 voice tests pass after these changes.

---

### Task 0.5: SQL migrations (RLS bypass + index)

**Files:**
- Create: `supabase/migrations/049_app_temp_rls_bypass.sql`

- [ ] **Step 1: Create the migration file**

Create `supabase/migrations/049_app_temp_rls_bypass.sql`:

```sql
-- Temporary RLS bypass: allow anon key to read all call_records.
-- REMOVE THIS POLICY when contractor auth ships.
-- See: docs/superpowers/plans/2026-03-17-calllock-app-migration.md
CREATE POLICY call_records_anon_read ON public.call_records
  FOR SELECT TO anon USING (true);

-- Index for the app's default query: ORDER BY created_at DESC LIMIT 100
CREATE INDEX idx_call_records_created ON public.call_records(created_at DESC);
```

- [ ] **Step 2: Commit**

```bash
git add supabase/migrations/049_app_temp_rls_bypass.sql
git commit -m "infra: temp RLS bypass for anon reads + created_at index for app query"
```

---

## File Structure

```
web/                              # NEW — entire directory
├── package.json                  # Copied, renamed to "calllock-app"
├── next.config.ts                # Copied as-is
├── tsconfig.json                 # Copied as-is
├── postcss.config.mjs            # Copied as-is
├── components.json               # Copied as-is
├── .env.local                    # Copied as-is (gitignored)
├── src/
│   ├── app/
│   │   ├── layout.tsx            # MODIFY — update metadata title/description
│   │   ├── page.tsx              # MODIFY — query call_records instead of call_sessions
│   │   └── globals.css           # Copied as-is
│   ├── components/
│   │   ├── mail/
│   │   │   ├── mail.tsx          # Copied as-is (no data layer changes)
│   │   │   ├── mail-list.tsx     # Copied as-is
│   │   │   ├── mail-display.tsx  # MODIFY — transcript fetch uses call_records
│   │   │   └── nav.tsx           # Copied as-is
│   │   └── ui/                   # Copied as-is (12 shadcn components)
│   ├── hooks/
│   │   ├── use-realtime-calls.ts # MODIFY — subscribe to call_records table
│   │   └── use-read-state.ts     # Copied as-is
│   ├── lib/
│   │   ├── supabase.ts           # Copied as-is
│   │   ├── transforms.ts         # REWRITE — map CallRecordRow → Call (flat columns)
│   │   └── utils.ts              # Copied as-is
│   └── types/
│       └── call.ts               # MODIFY — replace CallSessionRow with CallRecordRow
render.yaml                       # MODIFY — add 4th service for calllock-app
```

**Key insight:** Only 5 files have meaningful changes. Everything else is a straight copy. The UI components (`mail.tsx`, `mail-list.tsx`, `nav.tsx`, all `ui/` components) are untouched because they consume the `Call` interface, which stays the same.

---

### Task 1: Copy hong-kong-v1 into web/

**Files:**
- Create: `web/` (entire directory tree)

- [ ] **Step 1: Copy the app**

```bash
cp -r /Users/rashidbaset/conductor/workspaces/calllock-app/hong-kong-v1 web
```

- [ ] **Step 2: Clean copied artifacts**

```bash
rm -rf web/.git web/.next web/node_modules
```

- [ ] **Step 3: Rename package**

In `web/package.json`, change `"name": "mail-scaffold"` to `"name": "calllock-app"`.

- [ ] **Step 4: Add .next to root .gitignore**

Append `.next/` to the root `.gitignore` so Next.js build output doesn't get committed.

- [ ] **Step 5: Verify vitest config exists with path aliases**

Check if `web/vitest.config.ts` exists. If not, create it:

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

This ensures `@/lib/transforms` imports resolve in tests.

- [ ] **Step 6: Verify the copy builds**

```bash
cd web && npm install && npm run build
```

Expected: Build succeeds (still pointing at old table — that's fine, we're verifying the copy is clean).

- [ ] **Step 5: Commit**

```bash
git add web/
git commit -m "chore: copy hong-kong-v1 into web/ as calllock-app scaffold"
```

---

### Task 2: Rewrite types (CallSessionRow → CallRecordRow)

**Files:**
- Modify: `web/src/types/call.ts`

- [ ] **Step 1: Replace CallSessionRow with CallRecordRow**

Replace the `CallSessionRow` interface with the new one that matches the `call_records` schema:

```typescript
// Raw Supabase row shape — maps to call_records table
export interface CallRecordRow {
  id: string
  tenant_id: string
  call_id: string
  retell_call_id: string
  phone_number: string | null
  transcript: string | null
  raw_retell_payload: Record<string, unknown>
  extracted_fields: Record<string, unknown>
  extraction_status: string
  quality_score: number | null
  tags: string[]
  route: string | null
  urgency_tier: string | null
  caller_type: string | null
  primary_intent: string | null
  revenue_tier: string | null
  booking_id: string | null
  callback_scheduled: boolean
  call_duration_seconds: number | null
  end_call_reason: string | null
  call_recording_url: string | null
  synced_to_app: boolean
  created_at: string
  updated_at: string
}
```

Keep `Call`, `UrgencyTier`, `EndCallReason`, `HVACIssueType`, and `TranscriptEntry` unchanged — these are the app's internal types and the UI depends on them.

Also add a partial row type for the list query (which intentionally omits transcript, raw_retell_payload, and other heavy columns):

```typescript
// Partial row shape for list queries that exclude heavy columns
export type CallRecordListRow = Pick<CallRecordRow,
  | "id" | "tenant_id" | "call_id" | "retell_call_id"
  | "phone_number" | "extracted_fields" | "extraction_status"
  | "urgency_tier" | "end_call_reason" | "callback_scheduled"
  | "booking_id" | "synced_to_app" | "created_at" | "updated_at"
>
```

- [ ] **Step 2: Verify types compile**

```bash
cd web && npx tsc --noEmit
```

Expected: Type errors in `transforms.ts` and `page.tsx` (they still reference `CallSessionRow`). That's expected — we fix those next.

- [ ] **Step 3: Commit**

```bash
git add web/src/types/call.ts
git commit -m "feat(web): replace CallSessionRow with CallRecordRow for call_records table"
```

---

### Task 3: Rewrite transforms (flat columns instead of nested JSONB)

**Files:**
- Modify: `web/src/lib/transforms.ts`

The old transform digs into `conversation_state.customerName`, `conversation_state.urgencyTier`, etc. The new `call_records` table has flat columns + an `extracted_fields` JSONB for the rich extraction data. The transform gets much simpler.

- [ ] **Step 1: Write the failing test**

Create `web/src/__tests__/transforms.test.ts`:

```typescript
import { describe, it, expect } from "vitest"
import { transformCallRecord, parseTranscript } from "@/lib/transforms"
import type { CallRecordRow } from "@/types/call"

const baseRow: CallRecordRow = {
  id: "uuid-1",
  tenant_id: "tenant-1",
  call_id: "call-1",
  retell_call_id: "retell-1",
  phone_number: "+15551234567",
  transcript: "Agent: Hello. User: My AC is broken.",
  raw_retell_payload: {},
  extracted_fields: {
    customer_name: "Jane Doe",
    service_address: "123 Main St",
    problem_description: "AC not cooling",
    hvac_issue_type: "No Cool",
    equipment_type: "Central AC",
    equipment_brand: "Carrier",
    equipment_age: "8 years",
    appointment_booked: true,
    appointment_date_time: "2026-03-20T14:00:00Z",
    safety_emergency: false,
    urgent_escalation: false,
    callback_type: null,
  },
  extraction_status: "complete",
  quality_score: 85,
  tags: ["no-cool", "residential"],
  route: "legitimate",
  urgency_tier: "urgent",
  caller_type: "homeowner",
  primary_intent: "repair",
  revenue_tier: "service_call",
  booking_id: "booking-abc",
  callback_scheduled: false,
  call_duration_seconds: 180,
  end_call_reason: "completed",
  call_recording_url: "https://example.com/recording.wav",
  synced_to_app: false,
  created_at: "2026-03-17T10:00:00Z",
  updated_at: "2026-03-17T10:00:05Z",
}

describe("transformCallRecord", () => {
  it("maps flat columns and extracted_fields to Call", () => {
    const call = transformCallRecord(baseRow, new Set())
    expect(call.id).toBe("call-1")
    expect(call.customerName).toBe("Jane Doe")
    expect(call.customerPhone).toBe("+15551234567")
    expect(call.serviceAddress).toBe("123 Main St")
    expect(call.problemDescription).toBe("AC not cooling")
    expect(call.urgency).toBe("Urgent")
    expect(call.hvacIssueType).toBe("No Cool")
    expect(call.equipmentType).toBe("Central AC")
    expect(call.equipmentBrand).toBe("Carrier")
    expect(call.equipmentAge).toBe("8 years")
    expect(call.appointmentBooked).toBe(true)
    expect(call.appointmentDateTime).toBe("2026-03-20T14:00:00Z")
    expect(call.endCallReason).toBe("completed")
    expect(call.isSafetyEmergency).toBe(false)
    expect(call.isUrgentEscalation).toBe(false)
    expect(call.read).toBe(false)
    expect(call.createdAt).toBe("2026-03-17T10:00:00Z")
  })

  it("handles missing extracted_fields gracefully", () => {
    const row = { ...baseRow, extracted_fields: {}, urgency_tier: null }
    const call = transformCallRecord(row, new Set())
    expect(call.customerName).toBe("Unknown Caller")
    expect(call.urgency).toBe("Routine")
    expect(call.hvacIssueType).toBeNull()
    expect(call.appointmentBooked).toBe(false)
  })

  it("marks call as read when id is in readIds set", () => {
    const call = transformCallRecord(baseRow, new Set(["call-1"]))
    expect(call.read).toBe(true)
  })
})

describe("mapUrgency", () => {
  // mapUrgency is not exported directly — test via transformCallRecord
  it("maps lowercase urgency_tier to title case UrgencyTier", () => {
    const cases: [string, string][] = [
      ["emergency", "LifeSafety"],
      ["urgent", "Urgent"],
      ["routine", "Routine"],
      ["estimate", "Estimate"],
    ]
    for (const [input, expected] of cases) {
      const row = { ...baseRow, urgency_tier: input }
      const call = transformCallRecord(row, new Set())
      expect(call.urgency).toBe(expected)
    }
  })

  it("falls back to Routine for unknown urgency values", () => {
    const row = { ...baseRow, urgency_tier: "banana" }
    const call = transformCallRecord(row, new Set())
    expect(call.urgency).toBe("Routine")
  })

  it("falls back to Routine for null urgency", () => {
    const row = { ...baseRow, urgency_tier: null }
    const call = transformCallRecord(row, new Set())
    expect(call.urgency).toBe("Routine")
  })
})

describe("parseTranscript", () => {
  it("parses Agent: and User: prefixed lines", () => {
    const raw = "Agent: Hello, how can I help?\nUser: My AC is broken."
    const result = parseTranscript(raw)
    expect(result).toEqual([
      { role: "agent", content: "Hello, how can I help?" },
      { role: "user", content: "My AC is broken." },
    ])
  })

  it("skips lines without recognized prefixes", () => {
    const raw = "Agent: Hi\nSystem: call started\nUser: Hello"
    const result = parseTranscript(raw)
    expect(result).toEqual([
      { role: "agent", content: "Hi" },
      { role: "user", content: "Hello" },
    ])
  })

  it("handles empty string", () => {
    expect(parseTranscript("")).toEqual([])
  })

  it("handles string with only whitespace lines", () => {
    expect(parseTranscript("\n\n\n")).toEqual([])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd web && npx vitest run src/__tests__/transforms.test.ts
```

Expected: FAIL — `transformCallRecord` does not exist yet.

- [ ] **Step 3: Rewrite transforms.ts**

Replace the contents of `web/src/lib/transforms.ts` with:

```typescript
import type { Call, CallRecordRow, CallRecordListRow, TranscriptEntry, UrgencyTier, HVACIssueType, EndCallReason } from "@/types/call"

function str(val: unknown, fallback = ""): string {
  return typeof val === "string" ? val : fallback
}

function bool(val: unknown, fallback = false): boolean {
  return typeof val === "boolean" ? val : fallback
}

// Pipeline stores urgency_tier as lowercase ("routine"), UI expects title case ("Routine")
const URGENCY_MAP: Record<string, UrgencyTier> = {
  emergency: "LifeSafety",
  urgent: "Urgent",
  routine: "Routine",
  estimate: "Estimate",
}

function mapUrgency(tier: string | null): UrgencyTier {
  if (!tier) return "Routine"
  return URGENCY_MAP[tier.toLowerCase()] ?? "Routine"
}

export function transformCallRecord(row: CallRecordRow | CallRecordListRow, readIds: Set<string>): Call {
  const ef = row.extracted_fields

  return {
    id: row.call_id,
    customerName: str(ef.customer_name, "Unknown Caller"),
    customerPhone: row.phone_number ?? "",
    serviceAddress: str(ef.service_address),
    problemDescription: str(ef.problem_description),
    urgency: mapUrgency(row.urgency_tier),
    hvacIssueType: (str(ef.hvac_issue_type) as HVACIssueType) || null,
    equipmentType: str(ef.equipment_type),
    equipmentBrand: str(ef.equipment_brand),
    equipmentAge: str(ef.equipment_age),
    appointmentBooked: bool(ef.appointment_booked),
    appointmentDateTime: str(ef.appointment_date_time) || null,
    endCallReason: (row.end_call_reason as EndCallReason) ?? null,
    isSafetyEmergency: bool(ef.safety_emergency),
    isUrgentEscalation: bool(ef.urgent_escalation),
    transcript: [],
    callbackType: str(ef.callback_type) || null,
    read: readIds.has(row.call_id),
    createdAt: row.created_at,
  }
}

export function parseTranscript(raw: string): TranscriptEntry[] {
  const lines = raw.split("\n").filter(Boolean)
  const entries: TranscriptEntry[] = []
  for (const line of lines) {
    if (line.startsWith("Agent:")) {
      entries.push({ role: "agent", content: line.slice(6).trim() })
    } else if (line.startsWith("User:")) {
      entries.push({ role: "user", content: line.slice(5).trim() })
    }
  }
  return entries
}
```

**Key changes from old transform:**
- Reads flat columns (`row.urgency_tier`, `row.phone_number`, `row.end_call_reason`) directly
- Falls back to `extracted_fields` JSONB for rich fields (`customer_name`, `service_address`, etc.)
- No more transcript parsing — transcript is now a plain text column, loaded separately
- No more `retell_data` drilling

- [ ] **Step 4: Run test to verify it passes**

```bash
cd web && npx vitest run src/__tests__/transforms.test.ts
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/transforms.ts web/src/__tests__/transforms.test.ts
git commit -m "feat(web): rewrite transforms for call_records flat schema"
```

---

### Task 4: Update page.tsx server query

**Files:**
- Modify: `web/src/app/page.tsx`

- [ ] **Step 1: Swap query to call_records**

Replace the contents of `web/src/app/page.tsx`:

```tsx
import { createServerClient } from "@/lib/supabase"
import { transformCallRecord } from "@/lib/transforms"
import { Mail } from "@/components/mail/mail"
import type { Call, CallRecordListRow } from "@/types/call"

export const dynamic = "force-dynamic"

export default async function CallsPage() {
  let calls: Call[] = []

  try {
    const supabase = createServerClient()

    const { data, error } = await supabase
      .from("call_records")
      .select("id, tenant_id, call_id, retell_call_id, phone_number, extracted_fields, extraction_status, urgency_tier, end_call_reason, callback_scheduled, booking_id, synced_to_app, created_at, updated_at")
      .order("created_at", { ascending: false })
      .limit(100)

    if (!error && data) {
      const rows = data as CallRecordListRow[]
      const emptyReadIds = new Set<string>()
      calls = rows.map((row) => transformCallRecord(row, emptyReadIds))
    }
  } catch {
    // Supabase unreachable — render empty state
  }

  return (
    <div className="flex h-full flex-col">
      <Mail initialCalls={calls} />
    </div>
  )
}
```

**Key changes:**
- Table: `call_sessions` → `call_records`
- Select: flat columns instead of `conversation_state` JSONB blob
- Excludes `transcript` and `raw_retell_payload` from list query (still lazy-loaded on detail view)
- Import: `transformCallSession` → `transformCallRecord`

- [ ] **Step 2: Verify types compile**

```bash
cd web && npx tsc --noEmit
```

Expected: Remaining errors only in `use-realtime-calls.ts` and `mail-display.tsx` (fixed in next tasks).

- [ ] **Step 3: Commit**

```bash
git add web/src/app/page.tsx
git commit -m "feat(web): query call_records table in server page"
```

---

### Task 5: Update realtime subscription

**Files:**
- Modify: `web/src/hooks/use-realtime-calls.ts`

- [ ] **Step 1: Swap to call_records table**

Replace the contents of `web/src/hooks/use-realtime-calls.ts`:

```typescript
"use client"

import { useState, useEffect, useRef } from "react"
import { createBrowserClient } from "@/lib/supabase"
import { transformCallRecord } from "@/lib/transforms"
import type { Call, CallRecordRow } from "@/types/call"

export function useRealtimeCalls(
  initialCalls: Call[],
  readIds: Set<string>
) {
  const [calls, setCalls] = useState<Call[]>(initialCalls)
  const readIdsRef = useRef(readIds)
  readIdsRef.current = readIds

  useEffect(() => {
    setCalls(initialCalls)
  }, [initialCalls])

  // Subscribe to new call_records inserts
  useEffect(() => {
    const supabase = createBrowserClient()

    const channel = supabase
      .channel("call_records_changes")
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "call_records",
        },
        (payload) => {
          const row = payload.new as CallRecordRow
          const call = transformCallRecord(row, readIdsRef.current)
          setCalls((prev) => [call, ...prev])
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [])

  useEffect(() => {
    setCalls((prev) =>
      prev.map((c) => ({ ...c, read: readIds.has(c.id) }))
    )
  }, [readIds])

  return calls
}
```

**Changes:** Channel name `call_sessions_changes` → `call_records_changes`, table `call_sessions` → `call_records`, import `transformCallSession` → `transformCallRecord`.

- [ ] **Step 2: Commit**

```bash
git add web/src/hooks/use-realtime-calls.ts
git commit -m "feat(web): subscribe to call_records realtime channel"
```

---

### Task 6: Update mail-display transcript fetch

**Files:**
- Modify: `web/src/components/mail/mail-display.tsx`

The old code fetched `retell_data` from `call_sessions` and drilled into `retell_data.call.transcript_object`. The new `call_records` table has `transcript` as a top-level text column. The transcript is plain text (not structured JSON), so we display it differently.

- [ ] **Step 1: Rewrite the transcript fetch effect**

In `web/src/components/mail/mail-display.tsx`, replace the `useEffect` block (lines 24-85) that fetches the transcript:

```typescript
  // Lazy-load transcript when a call is selected
  useEffect(() => {
    if (!call) {
      setTranscript([])
      return
    }

    if (call.transcript.length > 0) {
      setTranscript(call.transcript)
      return
    }

    let cancelled = false
    setLoadingTranscript(true)

    const supabase = createBrowserClient()
    const fetchTranscript = async () => {
      try {
        const { data } = await supabase
          .from("call_records")
          .select("transcript")
          .eq("call_id", call.id)
          .single()

        if (cancelled) return
        setLoadingTranscript(false)

        if (!data?.transcript) {
          setTranscript([])
          return
        }

        // parseTranscript is imported from @/lib/transforms
        setTranscript(parseTranscript(data.transcript as string))
      } catch {
        if (!cancelled) {
          setLoadingTranscript(false)
          setTranscript([])
        }
      }
    }
    fetchTranscript()

    return () => {
      cancelled = true
    }
  }, [call?.id, call?.transcript])
```

Also update imports at top of file: add `import { parseTranscript } from "@/lib/transforms"` and remove the `Record<string, unknown>` usage since we no longer parse nested JSONB.

- [ ] **Step 2: Verify full build**

```bash
cd web && npx tsc --noEmit && npm run build
```

Expected: Zero type errors, build succeeds.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/mail/mail-display.tsx
git commit -m "feat(web): fetch transcript from call_records text column"
```

---

### Task 7: Update metadata and layout

**Files:**
- Modify: `web/src/app/layout.tsx`

- [ ] **Step 1: Update metadata**

In `web/src/app/layout.tsx`, replace the metadata:

```typescript
export const metadata: Metadata = {
  title: "CallLock",
  description: "CallLock — AI-powered call management for contractors",
};
```

- [ ] **Step 2: Commit**

```bash
git add web/src/app/layout.tsx
git commit -m "chore(web): update metadata to CallLock branding"
```

---

### Task 8: Add web service to render.yaml

**Files:**
- Modify: `render.yaml`

- [ ] **Step 1: Add calllock-app service**

Append the following service before the redis entry in `render.yaml`:

```yaml
  - type: web
    name: calllock-app
    runtime: node
    rootDir: web
    buildCommand: npm install && npm run build
    startCommand: npm start
    healthCheckPath: /
    envVars:
      - key: NEXT_PUBLIC_SUPABASE_URL
        sync: false
      - key: NEXT_PUBLIC_SUPABASE_ANON_KEY
        sync: false
```

- [ ] **Step 2: Commit**

```bash
git add render.yaml
git commit -m "infra: add calllock-app web service to render.yaml"
```

---

### Task 9: Final verification

- [ ] **Step 1: Run all tests**

```bash
cd web && npm test
```

Expected: All tests pass (including the new transforms test).

- [ ] **Step 2: Run full build**

```bash
cd web && npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 3: Run dev server and smoke test**

```bash
cd web && npm run dev
```

Open `http://localhost:3000`. Verify:
- Page loads without errors
- If Supabase has call_records data, calls appear in the list
- If no data, empty state renders cleanly
- Selecting a call loads the detail view

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: migrate CallLock App into rabat monorepo

Moves hong-kong-v1 into web/, swaps data layer from call_sessions
to call_records table, simplifies transforms for flat column schema,
and adds deployment config to render.yaml."
```

---

## Field Mapping Reference

How `call_records` columns map to the `Call` interface:

| Call field | Old source (call_sessions) | New source (call_records) |
|---|---|---|
| `id` | `row.call_id` | `row.call_id` |
| `customerName` | `conversation_state.customerName` | `extracted_fields.customer_name` |
| `customerPhone` | `conversation_state.customerPhone` | `row.phone_number` |
| `serviceAddress` | `conversation_state.serviceAddress` | `extracted_fields.service_address` |
| `problemDescription` | `conversation_state.problemDescription` | `extracted_fields.problem_description` |
| `urgency` | `conversation_state.urgencyTier` | `row.urgency_tier` |
| `hvacIssueType` | `conversation_state.hvacIssueType` | `extracted_fields.hvac_issue_type` |
| `equipmentType` | `conversation_state.equipmentType` | `extracted_fields.equipment_type` |
| `equipmentBrand` | `conversation_state.equipmentBrand` | `extracted_fields.equipment_brand` |
| `equipmentAge` | `conversation_state.equipmentAge` | `extracted_fields.equipment_age` |
| `appointmentBooked` | `conversation_state.appointmentBooked` | `extracted_fields.appointment_booked` |
| `appointmentDateTime` | `conversation_state.appointmentDateTime` | `extracted_fields.appointment_date_time` |
| `endCallReason` | `conversation_state.endCallReason` | `row.end_call_reason` |
| `isSafetyEmergency` | `conversation_state.isSafetyEmergency` | `extracted_fields.safety_emergency` |
| `isUrgentEscalation` | `conversation_state.isUrgentEscalation` | `extracted_fields.urgent_escalation` |
| `transcript` | `retell_data.call.transcript_object` (nested JSON) | `row.transcript` (plain text, lazy) |
| `callbackType` | `conversation_state.callbackType` | `extracted_fields.callback_type` |
| `createdAt` | `row.created_at` | `row.created_at` |

---

### Task 10: Contractor authentication (separate planning session)

Auth requires its own brainstorming session to decide:
- **Auth provider:** Supabase Auth (built-in, free) vs Clerk (better UX, paid) vs custom JWT
- **Tenant context propagation:** How the JWT carries `tenant_id` so RLS works
- **Middleware design:** Next.js middleware vs server component auth checks
- **Session management:** Cookie-based vs token-based
- **Onboarding flow:** How contractors get their first login

**This task should NOT be implemented from this plan.** Start a new brainstorming session, produce a spec, then write a dedicated auth plan.

When auth ships:
1. Remove the temp RLS bypass policy (`DROP POLICY call_records_anon_read ON call_records`)
2. Update `createServerClient()` to use the authenticated user's JWT
3. Update `createBrowserClient()` to use the authenticated session
4. Add login/logout UI

---

## Known limitations (follow-up work)

1. **RLS blocks reads with anon key.** The `call_records` table has RLS: `tenant_id = current_tenant_id()`. The app uses Supabase anon key with no tenant context, so queries will return zero rows in production. **Fix:** Either add contractor auth (sets tenant context via JWT) or create an RLS policy for the anon role that scopes reads to a specific tenant. This is intentionally deferred — auth is a separate workstream.

2. **`equipment_brand` not extracted.** The extraction pipeline reads `equipment_type` and `equipment_age` from Retell's `dynamic_variables`, but `equipment_brand` is not currently set by the voice agent. It will always be empty until the Retell LLM prompt is updated to populate it.

3. **`appointment_date_time` not extracted.** The pipeline tracks `appointment_booked` (boolean) but does not extract the specific date/time. The field will be null until the extraction pipeline adds a date parser.
