# 3D Agent Office Dashboard

**Date:** 2026-03-15
**Status:** Draft
**Author:** Rashid Baset + Claude

## Overview

A 3D pixel-office-style dashboard that visualizes CallLock AgentOS worker agents in real-time. Inspired by Star-Office-UI (2D pixel art agent status board) and CrewHub (3D toon world with rooms), this system renders a low-poly toon 3D office building where each department occupies a room, agents are persistent characters, and LangGraph orchestration states map to physical zones within each room.

**Audience:** Internal -- engineering and product teams. Not tenant-facing.

**Primary surface:** Standalone web app (Next.js), with optional Electron wrap for always-on desktop window.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| 2D vs 3D | 3D (React Three Fiber) | 24 agents across 5 departments create visual density that 3D depth handles naturally. Droid CLI parallelizes the scaffolding effort, collapsing the build timeline to match 2D estimates. |
| Art style | Low-poly toon, flat-shaded | Cheap to render (~200-500 poly characters, ~1000-2000 poly rooms), no textures needed, charming aesthetic. Toon outline shader via Drei `<Outlines>`. |
| State source | Event-driven via Inngest | Agents emit Inngest events on state transitions. Dashboard subscribes via SSE. No polling, no agent-push. Leverages existing Inngest infrastructure. |
| Agent roster | Persistent characters from worker specs | Each worker type has a permanent character regardless of activity. 5 directors + 19 workers = 24 characters. |
| State model | LangGraph node mapping | 7 states: idle, context-assembly, policy-gate, execution, verification, persistence, error. Each maps to a furniture cluster (zone) within a room. |
| Density handling | 3D depth + camera fly-in | Orbital view shows all rooms; click a room to fly camera inside. No tabs or artificial pagination needed. |
| Build acceleration | Droid CLI | Room shells, agent models, animation controllers, and UI overlays are parallelizable across Droid agents. |

## Department Structure

### Product/Technology
Builds the product.

- **Director:** Head of Product (supervisor agent)
- **Workers:**
  - Engineering
  - Design
  - QA/Testing
  - Data/Analytics

### Marketing
Creates demand and brand awareness.

- **Director:** Head of Marketing (supervisor agent)
- **Workers:**
  - Growth/Performance Marketing
  - Content/SEO
  - Brand/Communications
  - Product Marketing

### Sales
Qualifies and closes leads that pass through Marketing.

- **Director:** Sales Director (supervisor agent)
- **Workers:**
  - SDR/Lead Qualifier
  - Account Executive
  - Demo/Closer

### Operations
Keeps the company running.

- **Director:** Operations Manager (supervisor agent)
- **Workers:**
  - Customer Support/Customer Success
  - Implementation/Onboarding
  - Process/Systems

### Finance/Legal
Protects and manages the business.

- **Director:** Finance Lead (supervisor agent)
- **Workers:**
  - Accounting
  - Legal/Compliance
  - Admin

## 3D Office Layout

### Floor Plan (Orbital View)

```
         ┌─────────┐                    ┌─────────┐
        /Product/ /│                   /Finance/ /│
       /  Tech  / / │                 / Legal  / / │
      ├─────────┤/  │               ├─────────┤/  │
      │ 👔 + 4  │   │               │ 👔 + 3  │   │
      │         │  /                │         │  /
      └────┬────┘ /                 └─────────┘ /
           │
      ┌────┴─────────────────────────────┐
     /          CENTRAL LOBBY           /│
    /   Memo Board · Quest Kiosk · Meeting Table  /│
   ├────────────────────────────────────┤ │
   │          GLASS-WALLED HALLWAYS     │/
   └────┬───────────────────────┬──────┘
        │                       │
   ┌────┴────┐            ┌────┴────┐         ┌─────────┐
  /Marketing//│          / Sales  / /│        /  Ops    / │
 /         / / │        /        / / │       /         / /│
├─────────┤/  │       ├─────────┤/  │      ├─────────┤/ │
│ 👔 + 4  │   │       │ 👔 + 3  │   │      │ 👔 + 3  │  │
│         │  /        │         │  /  ───► │         │ /
└─────────┘ /         └─────────┘ /        └─────────┘/
```

**Spatial relationships encode real handoff paths:**
- Marketing → Sales (hot lead handoff via lobby corridor)
- Sales → Operations (closed deal → onboarding via lobby corridor)
- Product/Tech ↔ all departments (feature work, bug fixes)
- Finance/Legal ↔ all departments (compliance checks, approvals)

### Camera System

- **Orbital view (default):** 45-degree isometric angle. All 5 rooms + lobby visible. User can orbit and zoom with mouse/trackpad.
- **Room fly-in:** Click a room to animate camera through the door into the interior. 7 LangGraph zones visible as furniture clusters. Back button or ESC flies camera out.
- **Meeting close-up:** When a meeting is active in the lobby, a "Join Meeting" button flies camera to a close-up of the conference table.

### Room Interiors (Fly-In View)

Each room contains 7 furniture zones mapped to LangGraph states:

| Zone | Furniture | Visual Treatment |
|---|---|---|
| Idle | Couch + coffee table | Agent sits, sips coffee |
| Context Assembly | Bookshelf + reading desk | Agent pulls books, reads documents |
| Policy Gate | Locked gate / checkpoint booth | Agent waits at barrier, yellow light pulses |
| Execution | Standing desk + monitors | Agent types actively, screen glows |
| Verification | Magnifying glass station / QA bench | Agent inspects with loupe |
| Persistence | Filing cabinet + vault door | Agent files papers into cabinet |
| Error | Sparking server rack, red lighting | Agent scratches head, smoke particles |

**Director's corner office:** Glass-walled area in each room's corner. Director sits at a larger desk. A colored light on the glass reflects department health:
- Green = all agents idle or working normally
- Yellow = policy gate quest pending
- Red = error state in department

### Hallway Handoff Animation

When `calllock/agent.handoff` fires:
1. Source agent stands up from their zone
2. Walks through glass-walled corridor into Central Lobby
3. Carries a glowing briefcase (representing context payload)
4. Walks through the corridor to the destination room
5. Destination agent receives the briefcase and walks to context-assembly zone

This makes cross-department bottlenecks visible -- a busy hallway means lots of work flowing between teams.

## Inngest Event Schema

### Core Events

```typescript
// Agent state transition
"calllock/agent.state.changed" -> {
  agent_id: string,           // worker spec id (e.g., "receptionist")
  tenant_id: string,          // for future multi-tenant filtering
  department: "product_tech" | "marketing" | "sales" | "operations" | "finance_legal",
  role: "director" | "worker",
  supervisor_id?: string,     // director's agent_id
  from_state: LangGraphState,
  to_state: LangGraphState,
  description: string,        // "Assembling context for call #4821"
  call_id?: string,
  timestamp: string
}

// Cross-department handoff
"calllock/agent.handoff" -> {
  from_agent: string,
  to_agent: string,
  from_department: string,
  to_department: string,
  call_id?: string,
  lead_id?: string,
  context_summary: string,
  timestamp: string
}

// Policy gate hit -- becomes a Quest
"calllock/policy.gate.pending" -> {
  quest_id: string,
  agent_id: string,
  department: string,
  call_id?: string,
  rule_violated: string,
  summary: string,
  options: string[],
  urgency: "low" | "medium" | "high",
  timestamp: string
}

// Policy gate resolved
"calllock/policy.gate.resolved" -> {
  quest_id: string,
  resolution: string,
  resolved_by: string,
  timestamp: string
}

// Daily memo generation (cron-triggered)
"calllock/memo.daily.generate" -> {
  date: string,
  tenant_id: string
}

// Meeting requested (Phase 2)
"calllock/meeting.requested" -> {
  meeting_id: string,
  type: "handoff" | "escalation" | "standup",
  attendees: { agent_id: string, department: string, role: string }[],
  trigger_event: string,
  timestamp: string
}
```

### LangGraph State Enum

```typescript
type LangGraphState =
  | "idle"
  | "context-assembly"
  | "policy-gate"
  | "execution"
  | "verification"
  | "persistence"
  | "error"
```

## Supabase Schema

### Phase 1 Tables

```sql
-- Current agent states (upserted on every transition)
CREATE TABLE agent_office_state (
  agent_id TEXT PRIMARY KEY,
  department TEXT NOT NULL,
  role TEXT NOT NULL,            -- "director" | "worker"
  supervisor_id TEXT,
  current_state TEXT NOT NULL,   -- LangGraph node name
  description TEXT,
  call_id TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Quest log (policy gate decisions)
CREATE TABLE quest_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id TEXT NOT NULL,
  department TEXT NOT NULL,
  call_id TEXT,
  rule_violated TEXT NOT NULL,
  summary TEXT NOT NULL,
  options JSONB NOT NULL,
  urgency TEXT NOT NULL DEFAULT 'medium',
  status TEXT NOT NULL DEFAULT 'pending',
  resolution TEXT,
  resolved_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);

-- Daily memos
CREATE TABLE daily_memo (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  memo_date DATE UNIQUE NOT NULL,
  content JSONB NOT NULL,
  generated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Phase 2 Tables

```sql
-- Meetings
CREATE TABLE meeting (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT NOT NULL,
  trigger_event TEXT,
  department TEXT,
  status TEXT NOT NULL DEFAULT 'in_progress',
  attendees JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- Meeting turns (round-robin transcript)
CREATE TABLE meeting_turn (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  meeting_id UUID NOT NULL REFERENCES meeting(id),
  agent_id TEXT NOT NULL,
  round INTEGER NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Meeting action items
CREATE TABLE meeting_action_item (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  meeting_id UUID NOT NULL REFERENCES meeting(id),
  assigned_to TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  due_by TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);
```

## Quest Log

Lives in the Central Lobby as a clickable kiosk. Also accessible as a persistent sidebar toggle (HTML overlay via Drei `<Html>`).

### Behavior
- `calllock/policy.gate.pending` events create quests
- Each quest displays: agent name, department, urgency, human-readable summary, and resolution options
- Clicking a resolution button fires `calllock/policy.gate.resolved` via Inngest
- The agent waiting in the policy-gate zone immediately walks to execution or back to idle
- Resolved quests roll into a collapsible "Resolved Today" section
- Orbital view shows quest count badges on affected rooms (director's glass aura turns yellow)

### Quest Display

```
┌─── QUEST LOG ──────────────────────────────────┐
│                                                  │
│  🔴 HIGH  "After-hours schedule change"         │
│     Agent: Receptionist (Product/Tech)           │
│     Call #4821 · 2 min ago                       │
│     [Approve] [Deny] [Escalate]                  │
│                                                  │
│  🟡 MED   "Lead score below threshold"          │
│     Agent: SDR (Sales)                           │
│     Lead #892 · 8 min ago                        │
│     [Override & Call] [Skip] [Return to Mktg]    │
│                                                  │
│  🟢 LOW   "Missing compliance cert"             │
│     Agent: Legal/Compliance (Finance)            │
│     Vendor #33 · 1 hr ago                        │
│     [Approve Temp] [Block] [Request Cert]        │
│                                                  │
│  ── Resolved Today: 12 ─────────────────────── │
│  ✅ "Duplicate contact merge" → Approved         │
│  ✅ "Discount > 20%" → Escalated to Sales Dir    │
└──────────────────────────────────────────────────┘
```

## Daily Memo

Wall-mounted board in the Central Lobby. Clicking it opens an HTML overlay panel.

### Behavior
- Inngest cron fires `calllock/memo.daily.generate` at midnight
- Next.js API route aggregates from Inngest event history + `quest_log` + existing `wedge_fitness_snapshots`
- Stored in `daily_memo` table as structured JSON
- Panel supports date navigation (previous/next day)
- Each department section is collapsible

### Memo Display

```
┌─── DAILY MEMO · March 14, 2026 ─────────────────┐
│                                                    │
│  PRODUCT/TECH                                      │
│  ├── 23 calls handled                             │
│  ├── 2 policy escalations (both resolved)         │
│  └── QA flagged 1 verification failure            │
│                                                    │
│  MARKETING                                         │
│  ├── 14 leads qualified                           │
│  ├── 8 passed to Sales as hot leads               │
│  └── Content agent published 2 SEO articles       │
│                                                    │
│  SALES                                             │
│  ├── 8 hot leads received                         │
│  ├── 5 calls completed, 2 demos scheduled         │
│  └── 1 deal closed → sent to Operations           │
│                                                    │
│  OPERATIONS                                        │
│  ├── 1 new customer onboarding started            │
│  ├── 6 support tickets resolved                   │
│  └── Avg response time: 4.2 min                   │
│                                                    │
│  FINANCE/LEGAL                                     │
│  ├── 3 compliance checks completed                │
│  └── 0 blocks issued                              │
│                                                    │
│  [◄ Mar 13]                        [Mar 15 ►]    │
└──────────────────────────────────────────────────┘
```

## Phase 2: Structured Agent Meetings

### When Meetings Trigger
- **Handoff meetings:** Cross-department handoff triggers a briefing (e.g., Marketing → Sales hot lead)
- **Escalation meetings:** Director calls a meeting when a quest is unresolved for too long
- **Daily standups:** Cron-triggered, each department's director summarizes team status

### Visual Treatment
- Central Lobby contains a conference room with a round table and chairs
- When `calllock/meeting.requested` fires, attending agent characters walk from their rooms into the lobby
- They sit around the table. Camera offers a "Join Meeting" button for close-up view
- Speech bubbles appear above each agent as their turn plays out
- Director's chair is visually distinct (bigger, at the head of the table)
- Action items materialize as floating sticky notes that fly to assigned agents when the meeting concludes

### Implementation
- New LangGraph subgraph with round-robin node execution
- Each participating agent gets a turn node receiving meeting context + prior turns
- Director agent gets final turn to summarize decisions and assign action items
- Action items fire as new Inngest events routed to assigned agents
- Full transcript stored in Supabase `meeting` + `meeting_turn` + `meeting_action_item`

## Key Cross-Department Flow: Lead → Call → Customer

The most important visualization in the system:

```
Marketing                    Sales                    Operations
┌──────────┐                ┌──────────┐              ┌──────────┐
│ Growth   │  hot lead      │ SDR      │  closed deal │ Onboard  │
│ agent    │ ──briefcase──► │ agent    │ ──briefcase──►│ agent    │
│ qualifies│  via lobby     │ calls    │  via lobby    │ sets up  │
└──────────┘                └──────────┘              └──────────┘
```

Each transition fires `calllock/agent.handoff`, producing a visible briefcase-carrying walk through the Central Lobby corridors.

## Tech Stack

```
Frontend:
  ├── Next.js 14 (App Router)
  ├── React Three Fiber (3D renderer)
  ├── Drei (R3F helpers: Outlines, Html, OrbitControls, CameraControls)
  ├── Three.js (underlying engine)
  └── Tailwind CSS (HTML overlay panels)

Backend:
  ├── Next.js API routes (SSE endpoint, quest resolution)
  ├── Supabase (agent_office_state, quest_log, daily_memo)
  └── Inngest (event bus, cron for daily memo)

Agent Runtime (existing):
  ├── Python LangGraph harness (emits Inngest events on state transitions)
  └── Inngest TypeScript functions (event processing)

Build Acceleration:
  └── Droid CLI (parallelized scaffolding and component generation)
```

## 3D Asset Strategy

### Style
- Low-poly toon: flat-shaded, color-per-face, no textures
- ~200-500 polygon characters
- ~1000-2000 polygon rooms
- Toon outline shader via Drei `<Outlines>`
- Warm lighting with soft shadows

### Droid Parallelization Plan

| Batch | Tasks | Parallel Agents |
|---|---|---|
| 1 | 5 room shell components (geometry + furniture zones) | 5 |
| 2 | 24 agent character model variants (from shared template) | Config-driven batch |
| 3 | Animation state machine, camera controller, lobby/hallway geometry | 3 |
| 4 | SSE → R3F state bridge, Quest Log overlay, Daily Memo overlay | 3 |
| 5 (Phase 2) | Meeting scene, transcript panel, action item animations | 2 |

### Human-Driven vs Droid-Generated

| Droid generates | Human defines |
|---|---|
| Room component boilerplate | Room layout and furniture placement |
| Character mesh templates | Agent-specific colors and accessories |
| Animation controller wiring | State machine transition rules |
| Camera rig code | Camera positions and fly-to timing |
| SSE connection boilerplate | Inngest event schema |
| UI overlay components | Quest/memo content structure |

## Phase Summary

| Component | Phase | Description |
|---|---|---|
| R3F 3D office with 5 rooms + lobby | 1 | Low-poly toon building, orbital camera |
| Orbital camera + room fly-in | 1 | Click room to enter, ESC to return |
| 24 low-poly toon agent characters | 1 | 5 directors + 19 workers from worker specs |
| 7 LangGraph zones per room | 1 | Furniture clusters mapped to orchestration states |
| 3D hallway handoff animation | 1 | Briefcase-carrying walk through glass corridors |
| Quest Log (HTML overlay) | 1 | Policy gate decisions as actionable quests |
| Daily Memo (HTML overlay) | 1 | Per-department activity summary, date-navigable |
| Inngest event-driven state (SSE) | 1 | Real-time agent state updates |
| Supabase state tables | 1 | agent_office_state, quest_log, daily_memo |
| Structured agent meetings in lobby | 2 | Round-robin LangGraph subgraph, conference table scene |
| Meeting transcript + action items | 2 | Floating sticky notes dispatched to agents |
| Optional Electron desktop wrap | 2 | Always-on desktop window |

## Open Questions

1. **Asset creation:** Generate low-poly models with AI tools (e.g., Meshy, Tripo), hand-model in Blender, or use an asset pack? Decision can be deferred -- R3F accepts any GLTF/GLB.
2. **Sound design:** Should state transitions have audio cues (typing sounds, door opens, error buzzer)? Nice to have but not Phase 1 critical.
3. **Multi-user:** Should multiple team members see the same office simultaneously (shared cursor / presence)? Not needed for Phase 1 but architecturally possible via Supabase Realtime.
