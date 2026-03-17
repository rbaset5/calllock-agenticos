# 3D Agent Office Dashboard (Command Center)

**Date:** 2026-03-15 (revised 2026-03-17)
**Status:** Design approved
**Author:** Rashid Baset + Claude

> References:
> - `calllock-agentos-architecture.md` — two-layer system model, three planes, boundary test
> - `2026-03-17-corporate-hierarchy-agent-roster.md` — full agent roster, reporting hierarchy, department details
> - `2026-03-17-product-guardian-design.md` — eng-ai-voice + eng-qa continuous improvement system

## Overview

CallLock's product is a per-customer voice AI agent plus a supporting customer app/dashboard that displays information from each call. The 3D office dashboard is a separate, internal-only operating headquarters for CallLock, visualizing the AI workforce that builds, supports, sells, and improves that product across all customers.

**This is not just a monitor — it is a bidirectional command surface.** Operators can resolve policy gate quests, dispatch tasks to idle agents, override in-flight handoffs, adjust policy thresholds, and trigger on-demand investigations. All actions are audit-logged.

**Audience:** Internal — CallLock team only. Not tenant-facing.

**Primary surface:** Standalone web app (Next.js) in `office-dashboard/` directory, with optional Electron wrap for always-on desktop window.

**Boundary test:** A customer never sees this. A CallLock internal user primarily uses this.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| 2D vs 3D | 3D (React Three Fiber) | 30 agents across 7 departments + executive suite create visual density that 3D depth handles naturally. |
| Art style | Low-poly toon, flat-shaded | Cheap to render (~200-500 poly characters, ~1000-2000 poly rooms), no textures needed, charming aesthetic. Toon outline shader via Drei `<Outlines>`. |
| State source | Event-driven via Inngest | Agents emit Inngest events on state transitions. Dashboard subscribes via Supabase Realtime. No polling. |
| Agent roster | 30 persistent characters | 4 executives + 5 directors + 21 workers. See corporate hierarchy doc for full roster. |
| State model | LangGraph node mapping | 7 states: idle, context-assembly, policy-gate, execution, verification, persistence, error. Each maps to a furniture cluster (zone) within a room. |
| Density handling | 3D depth + camera fly-in | Orbital view shows all rooms; click a room to fly camera inside. No tabs or artificial pagination. |
| Dashboard role | Bidirectional command surface | Operators dispatch tasks, override handoffs, resolve quests, trigger investigations, adjust thresholds. All audit-logged. |
| State management | Zustand | Lightweight, R3F-friendly state management for agent positions, quests, camera, and offline action queue. |
| Realtime delivery | Supabase Realtime | Frontend subscribes to `agent_office_state` and `quest_log` changes. No custom SSE endpoint needed. |
| Feature flag | Tenant-level `office_dashboard_enabled` | InngestEmitter in harness checks tenant config before emitting. Per-tenant rollout control. |
| Location | `office-dashboard/` in this repo | Internal tooling stays together. Runtime Split ADR justifies bounded TypeScript expansion. |
| Asset creation | AI-generated (Meshy/Tripo) | Generate low-poly base template, swap colors/accessories per agent. Polish in Blender if needed. |
| Sound design | Phase 2 | Subtle audio (keyboard clicks, paper shuffling, phone rings) adds life but is polish, not structure. |
| Multi-user | Not needed now | Supabase Realtime supports it architecturally. Add shared cursors/presence when team grows to 3+. |

## Department Structure

7 departments + Executive Suite. See `2026-03-17-corporate-hierarchy-agent-roster.md` for full agent details, IDs, and reporting lines.

| Department | Agents | Director | Key Metric |
|---|---|---|---|
| Executive Suite | 4 | — (C-Suite) | LTV:CAC ratio |
| Product Management | 7 | Head of Product (`pm-product-strategy`) | Feature adoption, retention |
| Engineering | 4 | VP of Engineering (`eng-vp`) | Uptime, latency, zero dropped calls |
| Growth Marketing | 6 | Head of Growth (`growth-head`) | Pipeline volume, CAC |
| Sales | 1 | — (reports to CEO directly) | Qualified demos booked |
| Customer Success | 5 | Head of CS (`cs-head`) | Churn rate, onboarding time |
| Finance/Legal | 3 | Finance Lead (`fin-lead`) | Budget accuracy, compliance |

**Total: 30 agents** (4 execs + 5 directors + 21 workers)

## 3D Office Layout

### Floor Plan (Orbital View)

```
                +----------------+
                |   Executive    |
                |     Suite      |
                |  CEO CPO CTO   |
                |      COO       |
                +-------+--------+
                        |
  +----------+   +------+------------------+   +----------+
  | Product  |   |     CENTRAL LOBBY       |   | Finance  |
  | Mgmt     |---| Deal Breaker Board      |---| /Legal   |
  | 7 agents |   | Quest Kiosk             |   | 3 agents |
  +----------+   | Daily Memo Board        |   +----------+
                  | Meeting Table           |
  +----------+   |                         |   +----------+
  | Engin-   |---|                         |---| Customer |
  | eering   |   |                         |   | Success  |
  | 4 agents |   +------+----------+-------+   | 5 agents |
  +----------+          |          |            +----------+
               +---------+   +-----+-----+
               | Growth   |   | Sales    |
               | Marketing|---| 1 agent  |
               | 6 agents |   +----------+
               +----------+
```

### Spatial Relationships (handoff paths)

- **Growth Marketing -> Sales:** Hot lead handoff via lobby corridor (SDR receives enriched lead)
- **Sales -> Customer Success:** Closed deal -> onboarding via lobby corridor
- **Growth Marketing <-> Product:** Deal Breaker Ledger flow through lobby (Growth writes, Product reads)
- **Engineering <-> all departments:** Feature work, bug fixes, Product Guardian reports
- **Finance/Legal <-> all departments:** Compliance checks, approvals
- **Executive Suite -> all:** Strategic directives cascade down through directors

### Camera System

- **Orbital view (default):** 45-degree isometric angle. All 7 rooms + executive suite + lobby visible. User can orbit and zoom with mouse/trackpad.
- **Room fly-in:** Click a room to animate camera through the door into the interior. 7 LangGraph zones visible as furniture clusters. Back button or ESC flies camera out.
- **Executive fly-in:** Click Executive Suite for close-up of C-Suite desks with company-wide KPI displays.
- **Meeting close-up:** When a meeting is active in the lobby, a "Join Meeting" button flies camera to the conference table.

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

**Director's corner office:** Glass-walled area in each room's corner. Director sits at a larger desk. Colored light on glass reflects department health:
- Green = all agents idle or working normally
- Yellow = policy gate quest pending or seam violation detected
- Red = error state in department

**Executive Suite:** Four desks arranged around a central strategy table. Company-wide KPI displays float above the table (LTV:CAC ratio, churn rate, pipeline volume, MRR). CEO desk is central and largest.

### Voice Call Ambient Activity

When a customer call comes in, the office reacts:
- A phone rings on the Engineering room desk (eng-ai-voice)
- The call counter in the Daily Memo ticks up
- If the call triggers a scorecard warning, eng-ai-voice walks to context-assembly
- If the call triggers a seam violation, eng-qa walks to policy-gate
- The Customer Success room shows a customer health board update

This makes the product's lifeblood visible without cluttering the office with per-call detail.

### Hallway Handoff Animation

When `calllock/agent.handoff` fires:
1. Source agent stands up from their zone
2. Walks through glass-walled corridor into Central Lobby
3. Carries a glowing briefcase (representing context payload)
4. Walks through the corridor to the destination room
5. Destination agent receives the briefcase and walks to context-assembly zone

Cross-department bottlenecks become visible — a busy hallway means lots of work flowing between teams.

## Central Lobby Features

### Deal Breaker Ledger (Physical Board)

A large board on the lobby wall where Growth Marketing logs problems and Product Management reads solutions.

**Behavior:**
- Growth Marketing agents walk to the lobby and write entries on the board
- Product Management agents read entries and carry them back to their room
- Board shows running count of open deal breakers, oldest unresolved, resolution rate
- Click to expand: problem description, evidence (lost deal count, objection frequency)
- Product responds: prioritizes against roadmap, assigns to sprint or defers with rationale

**Data flow:**
```
Growth Marketing writes           Product Management reads
+-----------------------+         +-----------------------+
| "Lost 20% of demos   |         | Prioritized against   |
|  because no mobile    | ------> |  Q2 roadmap.          |
|  booking view"        |         | Sprint 7, KR 2.       |
| Evidence: 8 lost      |         | Assigned: pm-execution|
|  deals in 2 weeks     |         |                       |
+-----------------------+         +-----------------------+
```

### Quest Log (Clickable Kiosk + Sidebar)

Lives in the Central Lobby as a clickable kiosk. Also accessible as a persistent sidebar toggle (HTML overlay via Drei `<Html>`).

**Behavior:**
- `calllock/policy.gate.pending` events create quests
- Each quest displays: agent name, department, urgency, human-readable summary, resolution options
- Clicking a resolution button fires `calllock/policy.gate.resolved` via Inngest
- The agent waiting in the policy-gate zone immediately walks to execution or back to idle
- Resolved quests roll into a collapsible "Resolved Today" section
- Orbital view shows quest count badges on affected rooms (director's glass turns yellow)

```
+--- QUEST LOG ------------------------------------------------+
|                                                                |
|  [HIGH]  "Retell prompt regression detected"                  |
|     Agent: eng-ai-voice (Engineering)                         |
|     Extraction accuracy dropped to 87% (threshold: 90%)      |
|     [Investigate] [Acknowledge] [Escalate to CTO]             |
|                                                                |
|  [MED]   "Seam violation: job_type missing on emergency cards"|
|     Agent: eng-qa (Engineering)                               |
|     Field extracted but not displayed in hong-kong-v1         |
|     [Create Issue] [Override] [Defer]                         |
|                                                                |
|  [LOW]   "Missing compliance cert for vendor"                 |
|     Agent: fin-legal (Finance/Legal)                          |
|     Vendor #33 - 1 hr ago                                     |
|     [Approve Temp] [Block] [Request Cert]                     |
|                                                                |
|  -- Resolved Today: 12 ------------------------------------ |
|  [done] "Duplicate contact merge" -> Approved                 |
|  [done] "Lead below ICP threshold" -> Returned to Growth     |
+--------------------------------------------------------------+
```

### Daily Memo (Wall-Mounted Board)

Wall-mounted board in the Central Lobby. Clicking opens an HTML overlay panel.

**Behavior:**
- Inngest cron fires `calllock/memo.daily.generate` at midnight
- Next.js API route aggregates from Inngest event history + `quest_log` + health reports from Product Guardian
- Stored in `daily_memo` table as structured JSON
- Panel supports date navigation (previous/next day)
- Each department section is collapsible

```
+--- DAILY MEMO - March 17, 2026 --------------------------------+
|                                                                    |
|  EXECUTIVE                                                         |
|  +-- CEO: 2 strategic directives issued                           |
|  +-- LTV:CAC ratio: 3.2:1 (target: 3.0)                         |
|                                                                    |
|  PRODUCT MANAGEMENT                                                |
|  +-- 3 PRDs in execution, 1 in discovery                         |
|  +-- Deal Breaker Ledger: 2 new, 1 resolved                     |
|  +-- Market research: TAM update in progress                     |
|                                                                    |
|  ENGINEERING                                                       |
|  +-- eng-ai-voice: [green] 94% extraction accuracy               |
|  +-- eng-qa: [yellow] 1 seam violation (job_type on emergency)   |
|  +-- 0 config drift, 0 dropped calls                             |
|                                                                    |
|  GROWTH MARKETING                                                  |
|  +-- 14 leads qualified, 8 passed to SDR                         |
|  +-- CRO: signup page A/B test running (variant B +12%)          |
|  +-- Content: 2 cold email sequences deployed                    |
|                                                                    |
|  SALES                                                             |
|  +-- SDR: 5 prospects prioritized for founder                    |
|  +-- 3 demos booked, 2 qualified above threshold                 |
|                                                                    |
|  CUSTOMER SUCCESS                                                  |
|  +-- 1 new customer onboarding (day 3 of 14)                     |
|  +-- 6 support tickets resolved, avg 4.2 min                     |
|  +-- Customer health: 11 green, 1 yellow                         |
|                                                                    |
|  FINANCE/LEGAL                                                     |
|  +-- 3 compliance checks completed, 0 blocks                     |
|  +-- CAC payback period: 4.2 months (target: <12)                |
|                                                                    |
|  [< Mar 16]                                      [Mar 18 >]      |
+------------------------------------------------------------------+
```

### Meeting Table (Phase 2)

Central Lobby contains a conference room with a round table and chairs. See Phase 2 section.

## Office as Command Surface

The 3D office is the primary way to interact with agents. Every idle agent is a dispatch target. Every active agent is observable.

### Click-to-Dispatch

Click any idle agent to dispatch an ad hoc task:
- "Investigate last 3 calls from customer X" -> eng-ai-voice
- "Run seam audit now" -> eng-qa
- "Analyze churn risk for accounts with declining call volume" -> pm-data-analytics
- "Draft cold email sequence for HVAC emergency segment" -> growth-content

Dispatched tasks fire `calllock/agent.dispatch` via Inngest. The agent walks from idle to context-assembly, then through the normal LangGraph pipeline.

### Click-to-Override

Click any agent in policy-gate to see the quest details and resolve inline. Click any active handoff in the lobby to redirect it to a different agent.

### Department Health at a Glance

From orbital view, each room's director glass color shows department health. Click any department for the drill-down. The Executive Suite shows company-wide KPIs.

## Inngest Event Schema

### Core Events

```typescript
// Agent state transition
"calllock/agent.state.changed" -> {
  agent_id: string,           // e.g., "eng-ai-voice"
  tenant_id: string,
  department: "executive" | "product_mgmt" | "engineering" | "growth_marketing" | "sales" | "customer_success" | "finance_legal",
  role: "executive" | "director" | "worker",
  supervisor_id?: string,     // director's agent_id
  from_state: LangGraphState,
  to_state: LangGraphState,
  description: string,        // "Running daily voice health check"
  triggered_by: "system" | "human" | "cron" | "reactive",
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
  overridden_by: string,
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

// Voice pipeline health (from Product Guardian)
"calllock/voice.health.report" -> {
  agent_id: string,
  report_type: "voice-health-check" | "e2e-smoke-test" | "seam-audit",
  status: "green" | "yellow" | "red",
  metrics: Record<string, number>,
  issues_created: number,
  timestamp: string
}

// Deal Breaker Ledger entry
"calllock/deal-breaker.logged" -> {
  id: string,
  logged_by: string,           // agent_id from growth marketing
  problem: string,
  evidence: string,
  lost_deal_count: number,
  timestamp: string
}

// Deal Breaker resolution
"calllock/deal-breaker.resolved" -> {
  id: string,
  resolved_by: string,         // agent_id from product
  resolution: string,
  sprint_assigned?: string,
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
CREATE TABLE agent_office_state (
  agent_id TEXT NOT NULL,
  tenant_id UUID NOT NULL,
  department TEXT NOT NULL,
  role TEXT NOT NULL,               -- 'executive' | 'director' | 'worker'
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

CREATE TABLE command_audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  user_id UUID NOT NULL,
  action_type TEXT NOT NULL,
  target_agent TEXT,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE command_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE command_audit_log FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON command_audit_log
  USING (tenant_id = public.current_tenant_id());
CREATE INDEX idx_audit_log_tenant_created ON command_audit_log (tenant_id, created_at DESC);

CREATE TABLE deal_breaker_ledger (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  logged_by TEXT NOT NULL,
  problem TEXT NOT NULL,
  evidence TEXT NOT NULL,
  lost_deal_count INTEGER DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'open',
  resolved_by TEXT,
  resolution TEXT,
  sprint_assigned TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);

ALTER TABLE deal_breaker_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE deal_breaker_ledger FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON deal_breaker_ledger
  USING (tenant_id = public.current_tenant_id());
CREATE INDEX idx_deal_breaker_open ON deal_breaker_ledger (tenant_id, status) WHERE status = 'open';
```

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

## Command Center API Routes

| Route | Method | Auth Role | Description |
|---|---|---|---|
| `/api/quest/resolve` | POST | operator, admin | Resolve a policy gate quest |
| `/api/agent/dispatch` | POST | operator, admin | Assign a task to an idle agent |
| `/api/handoff/override` | POST | admin | Redirect an in-flight handoff |
| `/api/policy/threshold` | POST | admin | Adjust policy gate thresholds |
| `/api/memo/generate` | POST | admin | Trigger daily memo generation |
| `/api/deal-breaker/log` | POST | operator, admin | Log a new deal breaker entry |
| `/api/deal-breaker/resolve` | POST | operator, admin | Resolve a deal breaker |

**Dual-path quest resolution:** Quest resolution writes to Supabase directly (dashboard sees immediately via Realtime) AND fires Inngest event (harness acts on it). If Inngest is down, quest shows as resolved but agent stays in policy-gate with "pending harness pickup" indicator. Harness also subscribes to `quest_log` changes via Supabase Realtime as backup channel.

## Error Handling & Degradation

### Connection Health
- Dashboard shows "Connection Status" indicator: green dot (live), yellow (reconnecting), red (disconnected)
- Supabase Realtime subscription auto-reconnects with exponential backoff
- When disconnected, all agent positions freeze and "Last updated X seconds ago" timestamp appears
- On reconnect, full state re-fetched from `agent_office_state` to reconcile missed transitions

### Quest Resolution Safety
- Quest resolution endpoint requires Supabase auth (internal SSO)
- Optimistic locking: resolution checks `status = 'pending'` in UPDATE WHERE clause
- Rate limiting: 1 resolution per quest per second (debounce on frontend)

### 3D Rendering Fallback
- If WebGL context is lost, graceful fallback: 2D table view of agent states (HTML-only)
- `<Canvas>` wrapped in `<ErrorBoundary>` that triggers 2D fallback
- Failed agent models render as colored cubes with name labels
- Loading screen with progress bar during initial scene load

### Offline Action Queue
- Mutations queue locally in Zustand when disconnected
- Drain automatically on reconnect, in order
- "Pending sync" indicator in UI
- Queue overflow (100+ actions) drops oldest non-critical with warning

### Auth
- Supabase Auth with internal SSO
- 3-tier role hierarchy: viewer (read-only), operator (+ resolve quests, dispatch tasks), admin (+ override handoffs, change thresholds)
- Roles stored in Supabase auth user metadata, enforced server-side
- Task dispatch payloads validated and sanitized to prevent prompt injection

## Three-Plane Alignment

The 3D office operates primarily as an interface over the control plane, with read models from data and learning planes:

| Plane | What the Office Shows | What the Office Does |
|---|---|---|
| **Control** | Agent states, quests, handoffs, department health, deal breaker board | Dispatch tasks, resolve quests, override handoffs |
| **Data** | Call counters, customer health indicators, pipeline metrics (read-only) | Does NOT store or display individual call records |
| **Learning** | Product Guardian health reports, extraction accuracy trends, seam violations | Trigger on-demand investigations, acknowledge regressions |

**The clean distinction:** The office is authoritative for internal control objects (quests, agent registry, handoffs, approvals, deal breakers). Product-domain records (calls, transcripts, bookings, customer accounts) remain authoritative in Supabase, read by the customer app.

## Tech Stack

```
Frontend:
  +-- Next.js 16 (App Router)
  +-- React Three Fiber (3D renderer)
  +-- Drei (R3F helpers: Outlines, Html, OrbitControls, CameraControls)
  +-- Three.js (underlying engine)
  +-- Zustand (state management: agents, quests, camera, offline queue)
  +-- Tailwind CSS (HTML overlay panels)

Backend:
  +-- Next.js API routes (command center: 7 endpoints)
  +-- Supabase (agent_office_state, quest_log, daily_memo, command_audit_log, deal_breaker_ledger)
  +-- Supabase Realtime (read path for agent state + quest status + deal breakers)
  +-- Supabase Auth (3-tier roles: viewer/operator/admin)
  +-- Inngest (event bus, cron for daily memo + department sweeps)

Agent Runtime (existing + new emitter):
  +-- Python LangGraph harness
  +-- InngestEventEmitter (behind tenant-level feature flag)
  +-- Supabase Realtime subscription on quest_log (backup channel)
  +-- Inngest TypeScript functions (event processing)
```

## 3D Asset Strategy

### Style
- Low-poly toon: flat-shaded, color-per-face, no textures
- ~200-500 polygon characters
- ~1000-2000 polygon rooms
- Toon outline shader via Drei `<Outlines>`
- Warm lighting with soft shadows

### Build Plan

| Batch | Tasks | Parallel Agents |
|---|---|---|
| 1 | 7 room shells + executive suite + lobby (geometry + furniture zones) | 8 |
| 2 | 30 agent character model variants (from shared template) | Config-driven batch |
| 3 | Animation state machine, camera controller, hallway geometry | 3 |
| 4 | Supabase Realtime -> Zustand state bridge, Quest Log overlay, Daily Memo overlay, Deal Breaker Board | 4 |
| 5 | Command center API routes (7 endpoints), audit log, offline queue | 2 |
| 6 | Delight: mood indicators, hallway heat map, quest urgency timer, hover tooltips, voice call ambient | 3 |
| 7 (Phase 2) | Meeting scene, transcript panel, action item animations, sound design | 2 |

## Phase 2: Structured Agent Meetings

### When Meetings Trigger
- **Handoff meetings:** Cross-department handoff triggers briefing (e.g., Growth Marketing -> Sales hot lead)
- **Escalation meetings:** Director calls meeting when quest unresolved too long
- **Daily standups:** Cron-triggered, each department's director summarizes team status

### Visual Treatment
- Central Lobby conference room with round table and chairs
- `calllock/meeting.requested` fires, attending agents walk from rooms into lobby
- They sit at table; camera offers "Join Meeting" button for close-up
- Speech bubbles above each agent as turns play out
- Director's chair is visually distinct (bigger, head of table)
- Action items materialize as floating sticky notes, fly to assigned agents on conclusion

### Implementation
- LangGraph subgraph with round-robin node execution
- Each agent gets a turn node receiving meeting context + prior turns
- Director gets final turn to summarize decisions and assign action items
- Action items fire as Inngest events routed to assigned agents
- Full transcript stored in Supabase `meeting` + `meeting_turn` + `meeting_action_item`

## State Model Reconciliation

The spec's 7 states vs. actual LangGraph nodes:

| Spec State | LangGraph Node | Notes |
|---|---|---|
| idle | _(inferred)_ | No active run. Derived from absence of recent state change. |
| context-assembly | `context_assembly` | Direct mapping |
| policy-gate | `policy_gate` | Direct mapping |
| execution | `worker` | Renamed for clarity in UI |
| verification | `verification` | Direct mapping |
| persistence | `persist` | Renamed for clarity in UI |
| error | _(inferred)_ | Derived from exception in any node |

**Additional state:** The harness `blocked` node (policy denial) maps to policy-gate zone with distinct visual treatment (red barrier instead of yellow pulse).

## Backend Prerequisites

### Agent Reality vs. Vision

See `2026-03-17-corporate-hierarchy-agent-roster.md` for full worker spec status. Summary:

| Status | Count | Details |
|---|---|---|
| Exist as worker specs | 5 | customer-analyst, designer, engineer, product-manager, product-marketer |
| Designed (ready to build) | 2 | eng-ai-voice, eng-qa (Product Guardian spec) |
| Planned (need specs) | 23 | All other agents |

**Phase 1 approach:** Ship with all 30 characters. Agents without worker specs show as perpetually idle with "Coming Soon" badge. As specs are built, they come alive. The dashboard drives backend priorities — "which idle character do we want to activate next?"

### Harness Event Emission

- **Write path:** `InngestEventEmitter` fires `calllock/agent.state.changed` on each LangGraph node entry. Parallels existing `MetricsEmitter` pattern.
- **Read path:** Dashboard subscribes to Supabase Realtime on `agent_office_state`. No custom SSE endpoint.
- **Feature flag:** `InngestEventEmitter` checks `tenant_config.office_dashboard_enabled` before emitting.
- **Backup channel:** Harness subscribes to `quest_log` status changes via Supabase Realtime. Zero silent failures on the critical control path.

### Inngest Event Naming Convention

All new events use `calllock/` prefix. Existing events (e.g., `ProcessCallPayload`) should be backfilled for consistency. Documented in ADR `015-inngest-event-naming-convention.md`.

## Phase 1 Done Criteria

Phase 1 is complete when:

1. 3D office renders with 7 rooms + executive suite + central lobby in orbital view
2. Camera fly-in works for each room, showing 7 LangGraph zones
3. At least 7 agent characters (5 existing + eng-ai-voice + eng-qa) show real state transitions from live Inngest events
4. Remaining 23 agent characters render in idle state with "Coming Soon" indicator
5. Hallway handoff animation plays on `calllock/agent.handoff` events
6. Quest Log overlay displays pending quests and resolves them via button click
7. Daily Memo overlay shows aggregated activity for the previous day (7 departments)
8. Deal Breaker Ledger board in lobby shows open/resolved entries
9. Connection health indicator is visible and functional
10. All tables have tenant isolation (RLS) enabled
11. Authentication gates access with 3-tier role enforcement
12. Command center: task dispatch to idle agents (operator+)
13. Command center: handoff override (admin)
14. Command audit log records all mutations
15. Hover tooltip on any agent shows current task description (speech bubble)
16. Agent mood indicators: 3-4 pose variants per state
17. Hallway traffic heat map: corridor glow scales with handoff frequency
18. Quest urgency timer: countdown, anxious pacing, director flash on expiry
19. Voice call ambient activity: phone ring, counter tick
20. InngestEmitter behind `office_dashboard_enabled` feature flag
21. Offline action queue: mutations queue when disconnected, drain on reconnect
22. GLTF model fallback: failed models render as colored cubes with name labels

## Runtime Split ADR

**Decision:** The 3D office dashboard introduces a significant Next.js (TypeScript) surface area beyond the existing convention of "TypeScript only where it interfaces with Inngest or repository validation/extraction."

**Context:** The dashboard is a standalone visualization and control surface. It is not part of the core orchestration runtime. The Python harness remains the sole orchestration layer. TypeScript is used here for: React Three Fiber rendering (no Python alternative), Next.js API routes for quest resolution (thin HTTP layer over Supabase), and Realtime subscription management (browser-native).

**Consequence:** This is a deliberate, bounded expansion. The TypeScript surface area is limited to the `office-dashboard/` directory and does not leak into the harness, knowledge system, or compliance graph.

## Key Cross-Department Flows

### Lead -> Demo -> Customer (Primary Revenue Flow)

```
Growth Marketing          Sales               Customer Success
+-------------+          +----------+         +---------------+
| Head of     | hot lead | SDR      | closed  | Onboarding    |
| Growth      |--brief-->| routes   | deal    | Specialist    |
| qualifies   | case     | to CEO   |--brief->| configures    |
+-------------+          +----------+ case    | voice agent   |
                                              +---------------+
```

### Product Guardian Flow (Continuous Improvement)

```
Voice Pipeline          Engineering              Customer App
+-------------+        +--------+--------+      +-------------+
| Retell call |--data-->| eng-ai | eng-qa |--PR->| hong-kong-v1|
| extraction  |        | -voice | seam   |      | card display|
| scoring     |        | health | valid  |      | transcript  |
+-------------+        +--------+--------+      +-------------+
```

### Deal Breaker Flow (Growth Loop)

```
Growth Marketing         Central Lobby           Product Management
+-------------+         +----------------+      +----------------+
| Lost deal   |--walk-->| Deal Breaker   |<-read| Head of Product|
| evidence    | to lobby| Board          |      | prioritizes    |
+-------------+         +----------------+      +----------------+
```
