# 3D Agent Office Dashboard

**Date:** 2026-03-15
**Status:** Reviewed (CEO mega-review complete)
**Author:** Rashid Baset + Claude

## Overview

A 3D agent command center that visualizes and controls CallLock AgentOS worker agents in real-time. Inspired by Star-Office-UI (2D pixel art agent status board) and CrewHub (3D toon world with rooms), this system renders a low-poly toon 3D office building where each department occupies a room, agents are persistent characters, and LangGraph orchestration states map to physical zones within each room.

**This is not just a monitor — it is a bidirectional control surface.** Operators can resolve policy gate quests, dispatch tasks to idle agents, override in-flight handoffs, and adjust policy thresholds. All actions are audit-logged.

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
| Dashboard role | Bidirectional command center | Not just monitoring — operators can dispatch tasks, override handoffs, resolve quests, adjust policy thresholds. All actions audit-logged. |
| State management | Zustand | Lightweight, R3F-friendly state management for agent positions, quests, camera, and offline action queue. |
| Realtime delivery | Supabase Realtime | Frontend subscribes to `agent_office_state` and `quest_log` changes via Supabase Realtime channels. No custom SSE endpoint needed. |
| Feature flag | Tenant-level `office_dashboard_enabled` | InngestEmitter in harness checks tenant config before emitting. Per-tenant rollout control. |

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
  triggered_by: "system" | "human",  // who initiated the state change
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

// Command center: task dispatch
"calllock/agent.dispatch" -> {
  agent_id: string,
  tenant_id: string,
  department: string,
  task_description: string,
  dispatched_by: string,        // user_id of the operator
  priority: "low" | "medium" | "high",
  timestamp: string
}

// Command center: handoff override
"calllock/handoff.override" -> {
  handoff_id: string,
  original_target: string,
  new_target: string,
  overridden_by: string,        // user_id of the admin
  reason: string,
  timestamp: string
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

See **Tenant Isolation** section below for complete Phase 1 table definitions with RLS policies and indexes.

### Phase 2 Tables

```sql
CREATE TABLE meeting (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  type TEXT NOT NULL,
  trigger_event TEXT,
  department TEXT,
  status TEXT NOT NULL DEFAULT 'in_progress',
  attendees JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

ALTER TABLE meeting ENABLE ROW LEVEL SECURITY;
ALTER TABLE meeting FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON meeting
  USING (tenant_id = public.current_tenant_id());

CREATE TABLE meeting_turn (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  meeting_id UUID NOT NULL REFERENCES meeting(id),
  agent_id TEXT NOT NULL,
  round INTEGER NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE meeting_turn ENABLE ROW LEVEL SECURITY;
ALTER TABLE meeting_turn FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON meeting_turn
  USING (tenant_id = public.current_tenant_id());

CREATE TABLE meeting_action_item (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  meeting_id UUID NOT NULL REFERENCES meeting(id),
  assigned_to TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  due_by TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

ALTER TABLE meeting_action_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE meeting_action_item FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON meeting_action_item
  USING (tenant_id = public.current_tenant_id());
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
  ├── Zustand (state management: agents, quests, camera, offline queue)
  └── Tailwind CSS (HTML overlay panels)

Backend:
  ├── Next.js API routes (command center: quest/resolve, agent/dispatch, handoff/override, policy/threshold, memo/generate)
  ├── Supabase (agent_office_state, quest_log, daily_memo, command_audit_log)
  ├── Supabase Realtime (read path for agent state + quest status changes)
  ├── Supabase Auth (3-tier roles: viewer/operator/admin)
  └── Inngest (event bus, cron for daily memo)

Agent Runtime (existing + new emitter):
  ├── Python LangGraph harness
  ├── InngestEventEmitter (new, behind tenant-level feature flag)
  ├── Supabase Realtime subscription on quest_log (backup channel)
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
| 4 | Supabase Realtime → Zustand state bridge, Quest Log overlay, Daily Memo overlay | 3 |
| 5 | Command center API routes (5 endpoints), audit log, offline queue | 2 |
| 6 | Delight: mood indicators, hallway heat map, quest urgency timer, hover tooltips | 2 |
| 7 (Phase 2) | Meeting scene, transcript panel, action item animations | 2 |

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
| Supabase Realtime state delivery | 1 | Real-time agent state + quest status updates |
| Supabase state tables | 1 | agent_office_state, quest_log, daily_memo, command_audit_log |
| Command center: task dispatch | 1 | Assign work to idle agents (operator+) |
| Command center: handoff override | 1 | Redirect in-flight handoffs (admin) |
| Command center: policy threshold | 1 | Adjust policy gate config (admin) |
| Command audit log | 1 | All mutations logged for debugging and compliance |
| 3-tier auth (viewer/operator/admin) | 1 | Role-based access to command center endpoints |
| Offline action queue | 1 | Mutations queue when disconnected, drain on reconnect |
| InngestEmitter with feature flag | 1 | Per-tenant `office_dashboard_enabled` toggle |
| Hover tooltip (speech bubble) | 1 | Current task description on agent hover |
| Agent mood indicators | 1 | 3-4 pose variants per state |
| Hallway traffic heat map | 1 | Corridor glow scales with handoff frequency |
| Quest urgency timer + pacing | 1 | Countdown, anxious pacing, director flash on expiry |
| Structured agent meetings in lobby | 2 | Round-robin LangGraph subgraph, conference table scene |
| Meeting transcript + action items | 2 | Floating sticky notes dispatched to agents |
| Achievement toasts | 2 | Milestone notifications for agents/departments |
| Ambient sound design | 2 | Audio layer tied to agent states, mutable |
| Optional Electron desktop wrap | 2 | Always-on desktop window |

## Backend Prerequisites

The dashboard visualizes agent activity, but several backend capabilities must exist for features to show real data rather than static placeholders.

### Agent Reality vs. Vision

The existing codebase has 5 worker specs: `customer-analyst`, `designer`, `engineer`, `product-manager`, `product-marketer`. The spec envisions 24 agents across 5 departments. The gap:

| Status | Agents |
|---|---|
| **Exist as worker specs** | Engineering, Design, Product Manager, Product Marketing, Data/Analytics (customer-analyst) |
| **Planned -- need worker specs** | QA/Testing, Growth/Perf, Content/SEO, Brand/Comms, SDR, Account Executive, Demo/Closer, Customer Support, Onboarding, Process/Systems, Accounting, Legal/Compliance, Admin |
| **New concept -- supervisor agents** | Head of Product, Head of Marketing, Sales Director, Ops Manager, Finance Lead |

**Phase 1 approach:** Ship the dashboard with all 24 characters. Agents without worker specs show as perpetually idle with a "Coming Soon" badge. As worker specs are built, they come alive. This lets the dashboard drive backend development priorities -- "which idle character do we want to activate next?"

### Harness Event Emission

The current Python LangGraph harness does not emit Inngest events on state transitions. The `MetricsEmitter` writes to Supabase's `metric_events` table via HTTP.

**Recommended approach (two paths):**

- **Write path:** Add an `InngestEventEmitter` to the harness that fires `calllock/agent.state.changed` on each LangGraph node entry. This parallels the existing `MetricsEmitter` pattern.
- **Read path:** The dashboard frontend subscribes to Supabase Realtime channels on `agent_office_state` rather than SSE from Next.js. This eliminates the need for a custom SSE endpoint and leverages Supabase's existing real-time infrastructure.

The Inngest event bus remains the canonical write path (harness → Inngest → Inngest function upserts `agent_office_state`). The read path uses Supabase Realtime directly.

**Feature flag:** The `InngestEventEmitter` checks `tenant_config.office_dashboard_enabled` before emitting. This provides a per-tenant kill switch without redeploying the harness.

**Backup channel:** The harness also subscribes to `quest_log` status changes via Supabase Realtime. If an Inngest event for quest resolution is lost, the harness picks up the resolution from the database change. This ensures zero silent failures on the most critical control path.

### Supervisor Graph Generalization

The existing `supervisor.py` compiles a single fixed graph wired to `run_customer_analyst`. For the dashboard to show meaningful state diversity across departments, the supervisor must become parameterized by worker spec, or each department needs its own compiled graph.

This is a Phase 1 prerequisite for real data but not for the dashboard shell. The dashboard can render mock/demo state transitions to validate the visualization while the supervisor is being generalized.

### Inngest Event Naming Convention

Existing events use no namespace prefix (e.g., `ProcessCallPayload`). This spec introduces `calllock/` prefixed events. This should be adopted as the standard going forward, with the existing event type backfilled for consistency. Document as an ADR.

## State Model Reconciliation

The spec's 7 states vs. actual LangGraph nodes:

| Spec State | LangGraph Node | Notes |
|---|---|---|
| idle | _(none -- inferred)_ | No active run. Derived from absence of recent state change. |
| context-assembly | `context_assembly` | Direct mapping |
| policy-gate | `policy_gate` | Direct mapping |
| execution | `worker` | Renamed for clarity in the UI |
| verification | `verification` | Direct mapping |
| persistence | `persist` | Renamed for clarity in the UI |
| error | _(none -- inferred)_ | Derived from exception in any node |

**Additional state:** The harness has a `blocked` node (policy denial). In the dashboard, `blocked` maps to the policy-gate zone with a distinct visual treatment (red barrier instead of yellow pulse).

## Tenant Isolation

Although this is an internal tool, all new tables follow the existing tenant isolation convention. Existing tables use `UUID` for `tenant_id` and the `public.current_tenant_id()` helper function (defined in `005_rls_policies.sql`). New tables match this pattern exactly.

Updated table definitions:

```sql
CREATE TABLE agent_office_state (
  agent_id TEXT NOT NULL,
  tenant_id UUID NOT NULL,
  department TEXT NOT NULL,
  role TEXT NOT NULL,
  supervisor_id TEXT,
  current_state TEXT NOT NULL,
  description TEXT,
  call_id TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (tenant_id, agent_id)
);

ALTER TABLE agent_office_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_office_state FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON agent_office_state
  USING (tenant_id = public.current_tenant_id());

CREATE TABLE quest_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
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

ALTER TABLE quest_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE quest_log FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON quest_log
  USING (tenant_id = public.current_tenant_id());

CREATE INDEX idx_quest_log_pending ON quest_log (tenant_id, status) WHERE status = 'pending';
CREATE INDEX idx_quest_log_created ON quest_log (tenant_id, created_at DESC);

CREATE TABLE daily_memo (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  memo_date DATE NOT NULL,
  content JSONB NOT NULL,
  generated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (tenant_id, memo_date)
);

ALTER TABLE daily_memo ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_memo FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON daily_memo
  USING (tenant_id = public.current_tenant_id());
```

## Command Audit Log

Every mutation through the command center is logged for debugging, compliance, and accountability.

```sql
CREATE TABLE command_audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  user_id UUID NOT NULL,
  action_type TEXT NOT NULL,   -- 'quest_resolve' | 'agent_dispatch' | 'handoff_override' | 'policy_threshold'
  target_agent TEXT,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE command_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE command_audit_log FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON command_audit_log
  USING (tenant_id = public.current_tenant_id());
CREATE INDEX idx_audit_log_tenant_created ON command_audit_log (tenant_id, created_at DESC);
```

## Command Center API Routes

| Route | Method | Auth Role | Description |
|---|---|---|---|
| `/api/quest/resolve` | POST | operator, admin | Resolve a policy gate quest |
| `/api/agent/dispatch` | POST | operator, admin | Assign a task to an idle agent |
| `/api/handoff/override` | POST | admin | Redirect an in-flight handoff to a different agent |
| `/api/policy/threshold` | POST | admin | Adjust policy gate thresholds |
| `/api/memo/generate` | POST | admin | Trigger daily memo generation |

**Dual-path quest resolution:** Quest resolution writes to Supabase directly (dashboard sees it immediately via Realtime) AND fires an Inngest event (harness acts on it). If Inngest is down, the quest shows as resolved but the agent stays in policy-gate with a "pending harness pickup" indicator. The harness also subscribes to `quest_log` changes via Supabase Realtime as a backup channel.

## Error Handling & Degradation

### Connection Health
- Dashboard shows a "Connection Status" indicator: green dot (live), yellow (reconnecting), red (disconnected)
- Supabase Realtime subscription auto-reconnects with exponential backoff
- When disconnected, all agent positions freeze and a "Last updated X seconds ago" timestamp appears
- On reconnect, full state is re-fetched from `agent_office_state` to reconcile any missed transitions

### Quest Resolution Safety
- Quest resolution endpoint requires Supabase auth (internal SSO via Supabase Auth)
- Optimistic locking: quest resolution checks `status = 'pending'` in the UPDATE WHERE clause to prevent double-resolution
- Rate limiting: 1 resolution per quest per second (debounce on frontend)

### 3D Rendering Fallback
- If WebGL context is lost, show a graceful fallback: 2D table view of agent states (HTML-only, no canvas)
- `<Canvas>` component wrapped in `<ErrorBoundary>` that triggers 2D fallback
- Individual agent models that fail to load (GLTF CDN down) show as colored cubes with name labels via `useGLTF.preload()` error handling
- Loading screen with progress bar during initial scene load (2-5 seconds for GLTF + WebGL context)

### Offline Action Queue
- Mutations (quest resolve, dispatch, override) queue locally in Zustand when disconnected
- Actions drain automatically on reconnect, in order
- Queued actions show a "pending sync" indicator in the UI
- Queue overflow (100+ actions) drops oldest non-critical actions with a warning

### Auth Token Management
- `supabase.auth.onAuthStateChange()` listener re-subscribes Realtime channels on token refresh
- Prevents silent subscription death from expired tokens

### Authentication & Authorization
- Supabase Auth with internal SSO (Google Workspace or similar)
- All API routes and Supabase queries require authenticated session
- 3-tier role hierarchy:
  - `viewer` — read-only: see the office, read quests, read memos
  - `operator` — viewer + resolve quests + dispatch tasks
  - `admin` — operator + override handoffs + change policy thresholds
- Roles stored in Supabase auth user metadata
- Enforced server-side on every mutation endpoint
- Task dispatch payloads validated and sanitized to prevent prompt injection into agent prompts

## Phase 1 Done Criteria

Phase 1 is complete when:

1. 3D office renders with 5 rooms + central lobby in orbital view
2. Camera fly-in works for each room, showing 7 LangGraph zones
3. At least 5 agent characters (the existing worker specs) show real state transitions from live Inngest events
4. Remaining 19 agent characters render in idle state with "Coming Soon" indicator
5. Hallway handoff animation plays on `calllock/agent.handoff` events
6. Quest Log overlay displays pending quests and resolves them via button click
7. Daily Memo overlay shows aggregated activity for the previous day
8. Connection health indicator is visible and functional
9. All tables have tenant isolation (RLS) enabled
10. Authentication gates access with 3-tier role enforcement (viewer/operator/admin)
11. Command center: task dispatch to idle agents (operator+)
12. Command center: handoff override (admin)
13. Command audit log records all mutations
14. Hover tooltip on any agent shows current task description (speech bubble)
15. Agent mood indicators: 3-4 pose variants per state (relaxed, focused, stressed, error)
16. Hallway traffic heat map: corridor glow intensity scales with handoff frequency
17. Quest urgency timer: real-time countdown, agent paces anxiously at policy-gate, director's glass flashes on expiry
18. InngestEmitter behind `office_dashboard_enabled` tenant-level feature flag
19. Offline action queue: mutations queue when disconnected, drain on reconnect
20. GLTF model fallback: failed models render as colored cubes with name labels

## Runtime Split ADR

**Decision:** The 3D office dashboard introduces a significant Next.js (TypeScript) surface area beyond the existing convention of "TypeScript only where it interfaces with Inngest or repository validation/extraction."

**Context:** The dashboard is a standalone visualization and control surface. It is not part of the core orchestration runtime. The Python harness remains the sole orchestration layer. TypeScript is used here for:
- React Three Fiber rendering (no Python alternative)
- Next.js API routes for quest resolution (thin HTTP layer over Supabase)
- SSE/Realtime subscription management (browser-native)

**Consequence:** This is a deliberate, bounded expansion. The TypeScript surface area is limited to the `office-dashboard/` directory and does not leak into the harness, knowledge system, or compliance graph.

## Open Questions

1. **Asset creation:** Generate low-poly models with AI tools (e.g., Meshy, Tripo), hand-model in Blender, or use an asset pack? Decision can be deferred -- R3F accepts any GLTF/GLB.
2. **Sound design:** Should state transitions have audio cues (typing sounds, door opens, error buzzer)? Nice to have but not Phase 1 critical.
3. **Multi-user:** Should multiple team members see the same office simultaneously (shared cursor / presence)? Not needed for Phase 1 but architecturally possible via Supabase Realtime.
