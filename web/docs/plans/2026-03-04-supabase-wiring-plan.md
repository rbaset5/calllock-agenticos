# Wire Support App to AI Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace static mock emails with live call data from Supabase, with real-time updates when new calls arrive.

**Architecture:** The support app reads directly from the same Supabase instance the V2 backend writes to. Supabase Realtime subscriptions push new calls instantly. No V2 backend changes needed.

**Tech Stack:** Next.js 16 (App Router), Supabase JS client, Supabase Realtime, shadcn/ui, Vitest, TypeScript

**Scope:** Calls tab only. Jobs tab, search wiring, and transcript error states are deferred (see TODOS.md).

**Review decisions applied:**
- 1A: `conversation_state` typed as `Record<string, unknown>`, defensive extraction in transforms
- 2A: SELECT-only RLS policy (documented, not disabled)
- 3A: try-catch in page.tsx with empty state fallback
- 4B: No realtime error handling for v1
- 5A: Delete `use-mail.ts`, local state in `mail.tsx`
- 6B: Keep `lib/transforms.ts` as separate file
- 7A: Full rewrite of `mail-display.tsx` body, keep filename
- 8A: Extract `getUrgencyVariant` to `lib/utils.ts`
- 9A: Add vitest + unit tests for transforms and utility
- 10A: Select only needed columns for list; lazy-load `retell_data` on detail select
- 11B: Keep limit(100), defer pagination
- 12B: No realtime array cap

```
┌─────────────────────────────────────────────────────────┐
│ DATA FLOW                                               │
│                                                         │
│  Supabase (call_sessions table)                         │
│       │                                                 │
│       ├── server fetch: SELECT call_id,                 │
│       │   conversation_state, created_at                │
│       │   (page.tsx, lightweight — no retell_data)      │
│       │                                                 │
│       ├── realtime subscription: INSERT events          │
│       │   (use-realtime-calls.ts)                       │
│       │                                                 │
│       └── detail fetch: SELECT retell_data              │
│           WHERE call_id = selected                      │
│           (mail-display.tsx, on-demand)                  │
│              │                                          │
│              ▼                                          │
│  transforms.ts: Record<string,unknown> → Call type      │
│  (defensive extraction with fallbacks)                  │
│              │                                          │
│              ▼                                          │
│  mail.tsx → mail-list.tsx → mail-display.tsx             │
│  (modified in place, same filenames)                    │
└─────────────────────────────────────────────────────────┘
```

---

### Task 1: Install Dependencies and Create Environment Config

**Files:**
- Modify: `package.json`
- Create: `.env.local`
- Modify: `.gitignore`

**Step 1: Install Supabase client and vitest**

Run: `npm install @supabase/supabase-js`
Run: `npm install -D vitest`

**Step 2: Create `.env.local`**

```
NEXT_PUBLIC_SUPABASE_URL=https://xboybmqtwsxmdokgzclk.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=PLACEHOLDER_REPLACE_WITH_REAL_KEY
```

**Step 3: Verify `.gitignore` includes `.env.local`**

Check that `.env.local` is in `.gitignore`. If not, add it.

**Step 4: Add vitest config and test script**

Add to `package.json` scripts: `"test": "vitest run", "test:watch": "vitest"`

Create `vitest.config.ts`:

```typescript
import { defineConfig } from "vitest/config"
import path from "path"

export default defineConfig({
  test: {
    environment: "node",
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
```

**Step 5: Commit**

```bash
git add package.json package-lock.json .gitignore vitest.config.ts
git commit -m "chore: add supabase, vitest dependencies and env config"
```

---

### Task 2: Create Type Definitions

**Files:**
- Create: `src/types/call.ts`

**Step 1: Create the Call type and raw row shape**

Scope reduced: no Job, Booking, or emergency alert types (deferred to TODOS.md).

`conversation_state` is typed as `Record<string, unknown>` per review decision 1A — we extract fields defensively in transforms.

```typescript
// Types for CallLock support app
// Maps to Supabase call_sessions table

export type UrgencyTier = "LifeSafety" | "Urgent" | "Routine" | "Estimate"

export type EndCallReason =
  | "wrong_number"
  | "callback_later"
  | "safety_emergency"
  | "urgent_escalation"
  | "out_of_area"
  | "waitlist_added"
  | "completed"
  | "customer_hangup"
  | "sales_lead"
  | "cancelled"
  | "rescheduled"
  | "booking_failed"

export type HVACIssueType =
  | "Cooling"
  | "Heating"
  | "Maintenance"
  | "Leaking"
  | "No Cool"
  | "No Heat"
  | "Noisy System"
  | "Odor"
  | "Not Running"
  | "Thermostat"

export interface TranscriptEntry {
  role: "agent" | "user"
  content: string
}

export interface Call {
  id: string
  customerName: string
  customerPhone: string
  serviceAddress: string
  problemDescription: string
  urgency: UrgencyTier
  hvacIssueType: HVACIssueType | null
  equipmentType: string
  equipmentBrand: string
  equipmentAge: string
  appointmentBooked: boolean
  appointmentDateTime: string | null
  endCallReason: EndCallReason | null
  isSafetyEmergency: boolean
  isUrgentEscalation: boolean
  transcript: TranscriptEntry[]
  callbackType: string | null
  read: boolean
  createdAt: string
}

// Raw Supabase row shape
// conversation_state is Record<string, unknown> — we don't own this schema.
// The V2 backend writes ConversationState JSONB; we extract defensively in transforms.ts.
export interface CallSessionRow {
  call_id: string
  conversation_state: Record<string, unknown>
  retell_data?: Record<string, unknown>
  synced_to_dashboard: boolean
  created_at: string
}
```

**Step 2: Commit**

```bash
git add src/types/call.ts
git commit -m "feat: add Call type definitions with defensive raw row shape"
```

---

### Task 3: Create Supabase Client

**Files:**
- Create: `src/lib/supabase.ts`

**Step 1: Create server and browser Supabase clients**

```typescript
import { createClient } from "@supabase/supabase-js"

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export function createBrowserClient() {
  return createClient(supabaseUrl, supabaseAnonKey)
}

export function createServerClient() {
  return createClient(supabaseUrl, supabaseAnonKey)
}
```

**Step 2: Commit**

```bash
git add src/lib/supabase.ts
git commit -m "feat: add Supabase client factory"
```

---

### Task 4: Create Transform Layer and Utility

**Files:**
- Create: `src/lib/transforms.ts`
- Modify: `src/lib/utils.ts`

**Step 1: Write the defensive transform function**

All field access uses optional chaining and fallback values. This is the only file that knows the Supabase JSONB shape.

```typescript
import type { Call, CallSessionRow, TranscriptEntry, UrgencyTier, HVACIssueType, EndCallReason } from "@/types/call"

// Helper to safely extract a string from unknown JSONB
function str(val: unknown, fallback = ""): string {
  return typeof val === "string" ? val : fallback
}

function bool(val: unknown, fallback = false): boolean {
  return typeof val === "boolean" ? val : fallback
}

export function transformCallSession(row: CallSessionRow, readIds: Set<string>): Call {
  const cs = row.conversation_state

  // Extract transcript from retell_data if present
  let transcript: TranscriptEntry[] = []
  if (row.retell_data && typeof row.retell_data === "object") {
    const call = (row.retell_data as Record<string, unknown>).call
    if (call && typeof call === "object") {
      const transcriptObj = (call as Record<string, unknown>).transcript_object
      if (Array.isArray(transcriptObj)) {
        transcript = transcriptObj.filter(
          (t): t is TranscriptEntry =>
            typeof t === "object" &&
            t !== null &&
            (t.role === "agent" || t.role === "user") &&
            typeof t.content === "string"
        )
      }
    }
  }

  return {
    id: row.call_id,
    customerName: str(cs.customerName, "Unknown Caller"),
    customerPhone: str(cs.customerPhone),
    serviceAddress: str(cs.serviceAddress),
    problemDescription: str(cs.problemDescription),
    urgency: (str(cs.urgencyTier, "Routine") as UrgencyTier),
    hvacIssueType: (str(cs.hvacIssueType) as HVACIssueType) || null,
    equipmentType: str(cs.equipmentType),
    equipmentBrand: str(cs.equipmentBrand),
    equipmentAge: str(cs.equipmentAge),
    appointmentBooked: bool(cs.appointmentBooked),
    appointmentDateTime: str(cs.appointmentDateTime) || null,
    endCallReason: (str(cs.endCallReason) as EndCallReason) || null,
    isSafetyEmergency: bool(cs.isSafetyEmergency),
    isUrgentEscalation: bool(cs.isUrgentEscalation),
    transcript,
    callbackType: str(cs.callbackType) || null,
    read: readIds.has(row.call_id),
    createdAt: row.created_at,
  }
}
```

**Step 2: Add `getUrgencyVariant` to `src/lib/utils.ts`**

Append to the existing file (which already has `cn`):

```typescript
import type { UrgencyTier } from "@/types/call"

export function getUrgencyVariant(
  urgency: UrgencyTier | string
): "destructive" | "outline" | "secondary" | "default" {
  switch (urgency) {
    case "LifeSafety":
    case "Urgent":
      return "destructive"
    case "Estimate":
      return "outline"
    default:
      return "secondary"
  }
}
```

**Step 3: Commit**

```bash
git add src/lib/transforms.ts src/lib/utils.ts
git commit -m "feat: add defensive JSONB transform and urgency badge utility"
```

---

### Task 5: Write Tests for Transform and Utility

**Files:**
- Create: `src/lib/__tests__/transforms.test.ts`
- Create: `src/lib/__tests__/utils.test.ts`

**Step 1: Write transform tests**

```typescript
import { describe, it, expect } from "vitest"
import { transformCallSession } from "../transforms"
import type { CallSessionRow } from "@/types/call"

describe("transformCallSession", () => {
  const emptyReadIds = new Set<string>()

  it("extracts all fields from a complete conversation_state", () => {
    const row: CallSessionRow = {
      call_id: "call_123",
      conversation_state: {
        callId: "call_123",
        customerName: "Janice",
        customerPhone: "+15125551234",
        serviceAddress: "1211 Squawk Street",
        problemDescription: "AC blowing warm air",
        urgencyTier: "Urgent",
        hvacIssueType: "Cooling",
        equipmentType: "AC unit",
        equipmentBrand: "Carrier",
        equipmentAge: "10 years",
        appointmentBooked: true,
        appointmentDateTime: "2026-03-10T08:00:00",
        endCallReason: "completed",
        isSafetyEmergency: false,
        isUrgentEscalation: true,
        callbackType: "service",
      },
      retell_data: {
        call: {
          transcript_object: [
            { role: "agent", content: "Thanks for calling ACE Cooling" },
            { role: "user", content: "My AC is blowing warm air" },
          ],
        },
      },
      synced_to_dashboard: true,
      created_at: "2026-03-05T10:00:00Z",
    }

    const call = transformCallSession(row, emptyReadIds)

    expect(call.id).toBe("call_123")
    expect(call.customerName).toBe("Janice")
    expect(call.customerPhone).toBe("+15125551234")
    expect(call.serviceAddress).toBe("1211 Squawk Street")
    expect(call.problemDescription).toBe("AC blowing warm air")
    expect(call.urgency).toBe("Urgent")
    expect(call.hvacIssueType).toBe("Cooling")
    expect(call.equipmentType).toBe("AC unit")
    expect(call.equipmentBrand).toBe("Carrier")
    expect(call.equipmentAge).toBe("10 years")
    expect(call.appointmentBooked).toBe(true)
    expect(call.appointmentDateTime).toBe("2026-03-10T08:00:00")
    expect(call.endCallReason).toBe("completed")
    expect(call.isSafetyEmergency).toBe(false)
    expect(call.isUrgentEscalation).toBe(true)
    expect(call.transcript).toHaveLength(2)
    expect(call.transcript[0].role).toBe("agent")
    expect(call.callbackType).toBe("service")
    expect(call.read).toBe(false)
    expect(call.createdAt).toBe("2026-03-05T10:00:00Z")
  })

  it("handles missing fields with safe defaults", () => {
    const row: CallSessionRow = {
      call_id: "call_empty",
      conversation_state: {},
      synced_to_dashboard: false,
      created_at: "2026-03-05T10:00:00Z",
    }

    const call = transformCallSession(row, emptyReadIds)

    expect(call.id).toBe("call_empty")
    expect(call.customerName).toBe("Unknown Caller")
    expect(call.customerPhone).toBe("")
    expect(call.problemDescription).toBe("")
    expect(call.urgency).toBe("Routine")
    expect(call.hvacIssueType).toBeNull()
    expect(call.appointmentBooked).toBe(false)
    expect(call.appointmentDateTime).toBeNull()
    expect(call.endCallReason).toBeNull()
    expect(call.isSafetyEmergency).toBe(false)
    expect(call.isUrgentEscalation).toBe(false)
    expect(call.transcript).toHaveLength(0)
    expect(call.callbackType).toBeNull()
  })

  it("respects readIds set", () => {
    const row: CallSessionRow = {
      call_id: "call_read",
      conversation_state: {},
      synced_to_dashboard: false,
      created_at: "2026-03-05T10:00:00Z",
    }

    const readIds = new Set(["call_read"])
    const call = transformCallSession(row, readIds)

    expect(call.read).toBe(true)
  })

  it("filters invalid transcript entries", () => {
    const row: CallSessionRow = {
      call_id: "call_bad_transcript",
      conversation_state: {},
      retell_data: {
        call: {
          transcript_object: [
            { role: "agent", content: "Hello" },
            { role: "tool_call_invocation", name: "lookup_caller" },
            null,
            { role: "user", content: "Hi" },
            { role: "user" }, // missing content
          ],
        },
      },
      synced_to_dashboard: false,
      created_at: "2026-03-05T10:00:00Z",
    }

    const call = transformCallSession(row, emptyReadIds)

    expect(call.transcript).toHaveLength(2)
    expect(call.transcript[0].content).toBe("Hello")
    expect(call.transcript[1].content).toBe("Hi")
  })
})
```

**Step 2: Write utility tests**

```typescript
import { describe, it, expect } from "vitest"
import { getUrgencyVariant } from "../utils"

describe("getUrgencyVariant", () => {
  it("returns destructive for LifeSafety", () => {
    expect(getUrgencyVariant("LifeSafety")).toBe("destructive")
  })

  it("returns destructive for Urgent", () => {
    expect(getUrgencyVariant("Urgent")).toBe("destructive")
  })

  it("returns outline for Estimate", () => {
    expect(getUrgencyVariant("Estimate")).toBe("outline")
  })

  it("returns secondary for Routine", () => {
    expect(getUrgencyVariant("Routine")).toBe("secondary")
  })

  it("returns secondary for unknown values", () => {
    expect(getUrgencyVariant("something_else")).toBe("secondary")
  })
})
```

**Step 3: Run tests to verify they pass**

Run: `npm test`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add src/lib/__tests__/
git commit -m "test: add unit tests for transformCallSession and getUrgencyVariant"
```

---

### Task 6: Create Read State Hook

**Files:**
- Create: `src/hooks/use-read-state.ts`

**Step 1: Write localStorage-based read tracking hook**

```typescript
"use client"

import { useState, useCallback, useEffect } from "react"

const STORAGE_KEY = "calllock-read-calls"

function loadReadIds(): Set<string> {
  if (typeof window === "undefined") return new Set()
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return new Set(stored ? JSON.parse(stored) : [])
  } catch {
    return new Set()
  }
}

export function useReadState() {
  const [readIds, setReadIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    setReadIds(loadReadIds())
  }, [])

  const markAsRead = useCallback((id: string) => {
    setReadIds((prev) => {
      const next = new Set(prev)
      next.add(id)
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify([...next]))
      } catch {
        // localStorage full or unavailable — read state is best-effort
      }
      return next
    })
  }, [])

  return { readIds, markAsRead }
}
```

**Step 2: Commit**

```bash
git add src/hooks/use-read-state.ts
git commit -m "feat: add localStorage-based read state hook"
```

---

### Task 7: Create Realtime Calls Hook

**Files:**
- Create: `src/hooks/use-realtime-calls.ts`

**Step 1: Write the Supabase Realtime subscription hook**

No error handling per review decision 4B — realtime is best-effort, base load works without it.

```typescript
"use client"

import { useState, useEffect, useRef } from "react"
import { createBrowserClient } from "@/lib/supabase"
import { transformCallSession } from "@/lib/transforms"
import type { Call, CallSessionRow } from "@/types/call"

export function useRealtimeCalls(
  initialCalls: Call[],
  readIds: Set<string>
) {
  const [calls, setCalls] = useState<Call[]>(initialCalls)
  const readIdsRef = useRef(readIds)
  readIdsRef.current = readIds

  // Sync initialCalls on first render (server → client handoff)
  useEffect(() => {
    setCalls(initialCalls)
  }, [initialCalls])

  // Subscribe to new call_sessions inserts
  useEffect(() => {
    const supabase = createBrowserClient()

    const channel = supabase
      .channel("call_sessions_changes")
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "call_sessions",
        },
        (payload) => {
          const row = payload.new as CallSessionRow
          const call = transformCallSession(row, readIdsRef.current)
          setCalls((prev) => [call, ...prev])
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [])

  // Update read status when readIds changes
  useEffect(() => {
    setCalls((prev) =>
      prev.map((c) => ({ ...c, read: readIds.has(c.id) }))
    )
  }, [readIds])

  return calls
}
```

**Step 2: Commit**

```bash
git add src/hooks/use-realtime-calls.ts
git commit -m "feat: add Supabase Realtime subscription hook for live calls"
```

---

### Task 8: Modify mail-list.tsx In Place

**Files:**
- Modify: `src/components/mail/mail-list.tsx`

**Step 1: Rewrite to render Call[] with urgency badges**

Full rewrite of the component body. Keep the filename. Import `Call` instead of `Mail`, render call-specific fields.

```typescript
"use client"

import { formatDistanceToNow } from "date-fns"
import { cn } from "@/lib/utils"
import { getUrgencyVariant } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { Call } from "@/types/call"

interface MailListProps {
  items: Call[]
  selected: string | null
  onSelect: (id: string) => void
}

export function MailList({ items, selected, onSelect }: MailListProps) {
  return (
    <ScrollArea className="h-screen">
      <div className="flex flex-col gap-2 p-4 pt-0">
        {items.map((item) => (
          <button
            key={item.id}
            className={cn(
              "flex flex-col items-start gap-2 rounded-lg border p-3 text-left text-sm transition-all hover:bg-accent",
              selected === item.id && "bg-muted"
            )}
            onClick={() => onSelect(item.id)}
          >
            <div className="flex w-full flex-col gap-1">
              <div className="flex items-center">
                <div className="flex items-center gap-2">
                  <div className="font-semibold">
                    {item.customerName || item.customerPhone || "Unknown"}
                  </div>
                  {!item.read && (
                    <span className="flex h-2 w-2 rounded-full bg-blue-600" />
                  )}
                </div>
                <div
                  className={cn(
                    "ml-auto text-xs",
                    selected === item.id
                      ? "text-foreground"
                      : "text-muted-foreground"
                  )}
                >
                  {formatDistanceToNow(new Date(item.createdAt), {
                    addSuffix: true,
                  })}
                </div>
              </div>
              <div className="text-xs font-medium">
                {item.problemDescription
                  ? item.problemDescription.substring(0, 80)
                  : item.hvacIssueType || "Missed call"}
              </div>
            </div>
            {item.customerPhone && (
              <div className="text-xs text-muted-foreground">
                {item.customerPhone}
              </div>
            )}
            <div className="flex items-center gap-2">
              <Badge variant={getUrgencyVariant(item.urgency)}>
                {item.urgency}
              </Badge>
              {item.appointmentBooked && (
                <Badge variant="outline">Booked</Badge>
              )}
              {item.isSafetyEmergency && (
                <Badge variant="destructive">Safety</Badge>
              )}
              {item.endCallReason === "callback_later" && (
                <Badge variant="secondary">Callback</Badge>
              )}
            </div>
          </button>
        ))}
      </div>
    </ScrollArea>
  )
}
```

**Step 2: Commit**

```bash
git add src/components/mail/mail-list.tsx
git commit -m "feat: rewrite mail-list to render Call cards with urgency badges"
```

---

### Task 9: Modify mail-display.tsx In Place

**Files:**
- Modify: `src/components/mail/mail-display.tsx`

Full rewrite of the component body (review decision 7A). Removes email toolbar, reply textarea. Adds: customer info header, problem details, equipment section, booking status, transcript display.

Includes lazy-load of `retell_data` for transcript (review decision 10A). When a call is selected, fetches the full row if transcript is empty.

**Step 1: Rewrite mail-display.tsx**

```typescript
"use client"

import { useEffect, useState } from "react"
import { format } from "date-fns"
import { Phone, MapPin, Wrench, Clock, AlertTriangle, Calendar } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import { getUrgencyVariant } from "@/lib/utils"
import { createBrowserClient } from "@/lib/supabase"
import type { Call, TranscriptEntry, CallSessionRow } from "@/types/call"
import { cn } from "@/lib/utils"

interface MailDisplayProps {
  call: Call | null
}

export function MailDisplay({ call }: MailDisplayProps) {
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [loadingTranscript, setLoadingTranscript] = useState(false)

  // Lazy-load transcript when a call is selected (review decision 10A)
  useEffect(() => {
    if (!call) {
      setTranscript([])
      return
    }

    // If transcript was already in the initial data, use it
    if (call.transcript.length > 0) {
      setTranscript(call.transcript)
      return
    }

    // Otherwise fetch retell_data for this call
    let cancelled = false
    setLoadingTranscript(true)

    const supabase = createBrowserClient()
    supabase
      .from("call_sessions")
      .select("retell_data")
      .eq("call_id", call.id)
      .single()
      .then(({ data }) => {
        if (cancelled) return
        setLoadingTranscript(false)

        if (!data?.retell_data) {
          setTranscript([])
          return
        }

        const retell = data.retell_data as Record<string, unknown>
        const callData = retell.call as Record<string, unknown> | undefined
        const transcriptObj = callData?.transcript_object
        if (Array.isArray(transcriptObj)) {
          setTranscript(
            transcriptObj.filter(
              (t): t is TranscriptEntry =>
                typeof t === "object" &&
                t !== null &&
                (t.role === "agent" || t.role === "user") &&
                typeof t.content === "string"
            )
          )
        } else {
          setTranscript([])
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadingTranscript(false)
          setTranscript([])
        }
      })

    return () => {
      cancelled = true
    }
  }, [call?.id, call?.transcript])

  if (!call) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center text-muted-foreground">
        <p className="text-sm">Select a call to view details</p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-start p-4">
        <div className="flex items-start gap-4 text-sm">
          <Avatar>
            <AvatarFallback>
              {(call.customerName || "?")
                .split(" ")
                .map((w) => w[0])
                .join("")
                .substring(0, 2)
                .toUpperCase()}
            </AvatarFallback>
          </Avatar>
          <div className="grid gap-1">
            <div className="font-semibold">
              {call.customerName || "Unknown Caller"}
            </div>
            {call.customerPhone && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Phone className="h-3 w-3" />
                {call.customerPhone}
              </div>
            )}
            {call.serviceAddress && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <MapPin className="h-3 w-3" />
                {call.serviceAddress}
              </div>
            )}
          </div>
        </div>
        <div className="ml-auto flex flex-col items-end gap-1">
          <div className="text-xs text-muted-foreground">
            {format(new Date(call.createdAt), "PPpp")}
          </div>
          <div className="flex gap-1">
            <Badge variant={getUrgencyVariant(call.urgency)}>
              {call.urgency}
            </Badge>
            {call.appointmentBooked && (
              <Badge variant="outline">Booked</Badge>
            )}
          </div>
        </div>
      </div>

      <Separator />

      <ScrollArea className="flex-1">
        <div className="space-y-4 p-4">
          {/* Problem Description */}
          {call.problemDescription && (
            <section>
              <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
                Problem
              </h3>
              <p className="text-sm">{call.problemDescription}</p>
              {call.hvacIssueType && (
                <Badge variant="outline" className="mt-1">
                  {call.hvacIssueType}
                </Badge>
              )}
            </section>
          )}

          {/* Equipment Details */}
          {(call.equipmentType || call.equipmentBrand || call.equipmentAge) && (
            <section>
              <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
                Equipment
              </h3>
              <div className="flex flex-wrap gap-2 text-sm">
                {call.equipmentType && (
                  <div className="flex items-center gap-1">
                    <Wrench className="h-3 w-3 text-muted-foreground" />
                    {call.equipmentType}
                  </div>
                )}
                {call.equipmentBrand && (
                  <span className="text-muted-foreground">
                    · {call.equipmentBrand}
                  </span>
                )}
                {call.equipmentAge && (
                  <div className="flex items-center gap-1">
                    <Clock className="h-3 w-3 text-muted-foreground" />
                    {call.equipmentAge}
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Booking Details */}
          {call.appointmentBooked && call.appointmentDateTime && (
            <section>
              <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
                Appointment
              </h3>
              <div className="flex items-center gap-2 text-sm">
                <Calendar className="h-3 w-3 text-muted-foreground" />
                {format(new Date(call.appointmentDateTime), "PPpp")}
              </div>
            </section>
          )}

          {/* Safety Warning */}
          {call.isSafetyEmergency && (
            <section className="rounded-md border border-destructive/50 bg-destructive/10 p-3">
              <div className="flex items-center gap-2 text-sm font-medium text-destructive">
                <AlertTriangle className="h-4 w-4" />
                Safety Emergency Detected
              </div>
            </section>
          )}

          {/* Transcript */}
          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
              Transcript
            </h3>
            {loadingTranscript ? (
              <p className="text-xs text-muted-foreground">Loading transcript...</p>
            ) : transcript.length > 0 ? (
              <div className="space-y-2">
                {transcript.map((entry, i) => (
                  <div
                    key={i}
                    className={cn(
                      "rounded-lg px-3 py-2 text-sm",
                      entry.role === "agent" ? "bg-muted" : "bg-primary/5"
                    )}
                  >
                    <span className="text-xs font-medium text-muted-foreground">
                      {entry.role === "agent" ? "AI Agent" : "Customer"}
                    </span>
                    <p className="mt-0.5">{entry.content}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">No transcript available</p>
            )}
          </section>

          {/* Call Outcome */}
          {call.endCallReason && (
            <section>
              <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
                Call Outcome
              </h3>
              <Badge variant="secondary">
                {call.endCallReason.replace(/_/g, " ")}
              </Badge>
            </section>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add src/components/mail/mail-display.tsx
git commit -m "feat: rewrite mail-display for call details with lazy transcript loading"
```

---

### Task 10: Modify mail.tsx In Place

**Files:**
- Modify: `src/components/mail/mail.tsx`

Removes dependency on `use-mail.ts` (review decision 5A). Uses local state for selection. Wires up realtime and read-state hooks. Keeps same layout structure.

**Step 1: Rewrite mail.tsx**

```typescript
"use client"

import * as React from "react"
import { ChevronLeft, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import type { Call } from "@/types/call"
import { useRealtimeCalls } from "@/hooks/use-realtime-calls"
import { useReadState } from "@/hooks/use-read-state"
import { MailList } from "./mail-list"
import { MailDisplay } from "./mail-display"

interface MailProps {
  initialCalls: Call[]
}

export function Mail({ initialCalls }: MailProps) {
  const [filter, setFilter] = React.useState<"all" | "unread">("all")
  const [mobileView, setMobileView] = React.useState<"list" | "detail">("list")
  const [selectedId, setSelectedId] = React.useState<string | null>(
    initialCalls[0]?.id ?? null
  )

  const { readIds, markAsRead } = useReadState()
  const calls = useRealtimeCalls(initialCalls, readIds)

  const filteredCalls = filter === "unread" ? calls.filter((c) => !c.read) : calls
  const selectedCall = calls.find((c) => c.id === selectedId) ?? null

  const handleSelect = (id: string) => {
    setSelectedId(id)
    markAsRead(id)
    setMobileView("detail")
  }

  return (
    <TooltipProvider delayDuration={0}>
      {/* Mobile layout */}
      <div className="flex h-full flex-col md:hidden">
        {mobileView === "list" ? (
          <Tabs defaultValue="all">
            <div className="flex h-[52px] items-center px-4">
              <h1 className="text-lg font-semibold">Calls</h1>
              <TabsList className="ml-auto">
                <TabsTrigger
                  value="all"
                  className="text-zinc-600 dark:text-zinc-200"
                  onClick={() => setFilter("all")}
                >
                  All
                </TabsTrigger>
                <TabsTrigger
                  value="unread"
                  className="text-zinc-600 dark:text-zinc-200"
                  onClick={() => setFilter("unread")}
                >
                  Unread
                </TabsTrigger>
              </TabsList>
            </div>
            <Separator />
            <div className="bg-background/95 p-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
              <form>
                <div className="relative">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input placeholder="Search" className="pl-8" />
                </div>
              </form>
            </div>
            <TabsContent value="all" className="m-0">
              <MailList
                items={filteredCalls}
                selected={selectedId}
                onSelect={handleSelect}
              />
            </TabsContent>
            <TabsContent value="unread" className="m-0">
              <MailList
                items={filteredCalls}
                selected={selectedId}
                onSelect={handleSelect}
              />
            </TabsContent>
          </Tabs>
        ) : (
          <div className="flex h-full flex-col">
            <div className="flex h-[52px] items-center gap-2 px-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setMobileView("list")}
              >
                <ChevronLeft className="h-4 w-4" />
                <span className="sr-only">Back</span>
              </Button>
              <div className="text-sm font-medium">Call Details</div>
            </div>
            <Separator />
            <div className="min-h-0 flex-1">
              <MailDisplay call={selectedCall} />
            </div>
          </div>
        )}
      </div>

      {/* Desktop layout */}
      <ResizablePanelGroup
        orientation="horizontal"
        className="hidden h-full max-h-screen items-stretch md:flex"
      >
        <ResizablePanel id="mail-list" defaultSize={40} minSize={30}>
          <Tabs defaultValue="all">
            <div className="flex h-[52px] items-center px-4">
              <h1 className="text-xl font-bold">Calls</h1>
              <TabsList className="ml-auto">
                <TabsTrigger
                  value="all"
                  className="text-zinc-600 dark:text-zinc-200"
                  onClick={() => setFilter("all")}
                >
                  All
                </TabsTrigger>
                <TabsTrigger
                  value="unread"
                  className="text-zinc-600 dark:text-zinc-200"
                  onClick={() => setFilter("unread")}
                >
                  Unread
                </TabsTrigger>
              </TabsList>
            </div>
            <Separator />
            <div className="bg-background/95 p-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
              <form>
                <div className="relative">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input placeholder="Search" className="pl-8" />
                </div>
              </form>
            </div>
            <TabsContent value="all" className="m-0">
              <MailList
                items={filteredCalls}
                selected={selectedId}
                onSelect={handleSelect}
              />
            </TabsContent>
            <TabsContent value="unread" className="m-0">
              <MailList
                items={filteredCalls}
                selected={selectedId}
                onSelect={handleSelect}
              />
            </TabsContent>
          </Tabs>
        </ResizablePanel>

        <ResizableHandle withHandle />

        <ResizablePanel id="mail-display" defaultSize={60} minSize={30}>
          <MailDisplay call={selectedCall} />
        </ResizablePanel>
      </ResizablePanelGroup>
    </TooltipProvider>
  )
}
```

**Step 2: Commit**

```bash
git add src/components/mail/mail.tsx
git commit -m "feat: wire mail container to Supabase calls with realtime and read state"
```

---

### Task 11: Update page.tsx to Fetch from Supabase

**Files:**
- Modify: `src/app/page.tsx`

Replace static import with Supabase server-side fetch. Select only needed columns (review decision 10A). Wrap in try-catch (review decision 3A).

**Step 1: Rewrite page.tsx**

```typescript
import { createServerClient } from "@/lib/supabase"
import { transformCallSession } from "@/lib/transforms"
import { Mail } from "@/components/mail/mail"
import type { CallSessionRow } from "@/types/call"

export const dynamic = "force-dynamic"

export default async function CallsPage() {
  let calls = []

  try {
    const supabase = createServerClient()

    // Select only needed columns — retell_data is lazy-loaded on detail view
    const { data, error } = await supabase
      .from("call_sessions")
      .select("call_id, conversation_state, created_at, synced_to_dashboard")
      .order("created_at", { ascending: false })
      .limit(100)

    if (!error && data) {
      const rows = data as CallSessionRow[]
      const emptyReadIds = new Set<string>()
      calls = rows.map((row) => transformCallSession(row, emptyReadIds))
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

**Step 2: Commit**

```bash
git add src/app/page.tsx
git commit -m "feat: fetch calls from Supabase with column selection and error fallback"
```

---

### Task 12: Clean Up Old Files

**Files:**
- Delete: `src/data/mails.ts`
- Delete: `src/hooks/use-mail.ts`

**Step 1: Remove static data and unused hook**

```bash
rm src/data/mails.ts
rm src/hooks/use-mail.ts
```

**Step 2: Run build to verify no broken imports**

Run: `npm run build`
Expected: Build succeeds. No references to deleted files remain.

**Step 3: Run tests**

Run: `npm test`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove static mail data and unused useMail hook"
```

---

### Task 13: Supabase Setup (Manual, One-Time)

These steps happen in the Supabase dashboard, not in code.

**Step 1: Add real Supabase anon key to `.env.local`**

Get `SUPABASE_ANON_KEY` from the V2 backend environment (Render dashboard or the V2 `.env` file).

Replace `PLACEHOLDER_REPLACE_WITH_REAL_KEY` in `.env.local`.

**Step 2: Enable Realtime on `call_sessions` table**

In Supabase dashboard:
- Go to Database → Replication
- Enable replication for `call_sessions` table

**Step 3: Add SELECT-only RLS policy (review decision 2A)**

Run in Supabase SQL editor:

```sql
-- Allow anon role to read call_sessions (support app has no auth)
CREATE POLICY "anon_read_call_sessions"
  ON call_sessions
  FOR SELECT
  TO anon
  USING (true);

-- Also allow reading retell_data for transcript lazy-load
-- (same table, same policy covers it)
```

**Step 4: Verify in browser**

Run: `npm run dev`
Open `http://localhost:3000`.

Expected:
- Calls list shows real calls from Supabase (or empty state if no calls yet)
- Clicking a call shows detail panel with customer info and lazy-loaded transcript
- No console errors

**Step 5: Test Realtime (optional)**

Insert a row in Supabase dashboard SQL editor or trigger a test call. The new call should appear at the top of the list without page refresh.
