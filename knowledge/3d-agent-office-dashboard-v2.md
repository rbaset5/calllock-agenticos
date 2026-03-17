---
id: 3d-agent-office-dashboard-v2
title: 3D Agent Office Dashboard — Revised Design Plan
graph: office-dashboard
owner: founder
last_reviewed: 2026-03-17
trust_level: curated
progressive_disclosure:
  summary_tokens: 600
  full_tokens: 20000
status: Draft - v2.3: Full Workforce Expansion
---

# 3D Agent Office Dashboard — v2.3

**Date:** 2026-03-17
**Status:** Draft - v2.3: Full Workforce Expansion
**Author:** Rashid Baset + Claude
**Supersedes:** v1 (2026-03-15), v2 (2026-03-17)

**v2.1 architectural clarification:** The 3D office is one shared internal headquarters for CallLock's AI workforce. It is not tenant-scoped and does not replicate per customer. The office holds a global canonical roster of 30 internal agents, while customer-specific context attaches only to the work flowing through that office: calls, leads, quests, handoffs, deal-breakers, and KPI outcomes. Phase 1 is a trustworthy read model with one real operator write (`quest_resolve`), not yet a full authoritative runtime control plane.

## Overview

### The Two Layers

**Product layer (per customer):** CallLock's product is a per-customer voice AI agent plus a supporting customer dashboard that displays information from each call. A plumber misses a call → their voice AI handles it → their dashboard shows the transcript + booked job. This is what each customer sees and pays for.

**Internal operations layer (for CallLock):** The 3D office dashboard is a separate, internal-only operating headquarters for CallLock, visualizing the AI workforce that builds, supports, sells, and improves that product across all customers.

### The Boundary

One customer call can trigger activity in both layers:

1. The customer's dashboard shows the transcript, classification, and booked job
2. Internally, CS/product/analytics/support systems react if something needs attention — a policy gate fires, a churn signal is detected, a deal breaker is logged

**The test:**

| If the user is... | They see... | They do NOT see... |
|---|---|---|
| A CallLock **customer** | Their calls, transcripts, booked jobs, settings, ROI, support/onboarding info | Internal product org, growth team, AI workforce, quest log, deal-breaker board |
| CallLock **internal** | The 3D office — all 30 agents, quests, memos, handoffs, deal breaker ledger | Individual customer dashboards (those are the product) |

**The product is not the 3D office. The product is: voice AI agent per customer + customer app/dashboard per customer. The 3D office is the internal operating/control layer behind that product.**

### Workspace Model

The 3D office is a single internal workspace for CallLock, not a tenant-scoped surface. The 30-agent roster is global. Customer/tenant context attaches to the work moving through the office, not to the office itself.

```ts
type WorkspaceScope = {
  workspace_id: string // internal CallLock org / HQ instance
}

type CustomerContext = {
  customer_id?: string
  tenant_id?: string
  call_id?: string
  lead_id?: string
  account_id?: string
}
```

**Workspace ID provisioning:** `workspace_id` is CallLock's own `tenant_id` from the existing `tenants` table. CallLock is its own tenant for internal operations. No new workspace table needed.

**Implications:**
- `agent_registry` and `agent_runtime_state` are global per internal agent, not per tenant
- Quests, deal-breakers, calls, and handoffs may carry `customer_id` / `tenant_id` as work context
- Feature flag is internal workspace-level, not tenant-level
- Auth is internal RBAC, not customer-tenant RLS

### PII and Transcript Exposure

**PII rule:** The internal HQ view is redacted by default. Agents, quest cards, memo panels, and handoff summaries may show only operational summaries unless a user explicitly opens a protected drilldown. No raw customer transcript text, phone numbers, addresses, payment details, or full recordings appear in the orbital or room-level UI.

**Default display policy:**
- **Allowed by default:** classification, intent summary, urgency, call outcome, customer health status, anonymized snippets
- **Restricted to drilldown:** raw transcripts, caller identity, phone numbers, addresses, billing data, full recordings
- **Prohibited in ambient view:** any full-text transcript leakage into speech bubbles, hover cards, memo board, or lobby board

### This Document

This spec covers only the internal operations layer — the 3D office dashboard. The product layer (voice agent + customer dashboard) is covered by the harness, voice pipeline, and app sync documentation.

**North Star Metric:** LTV:CAC Ratio > 3:1. Every agent in this office exists to lower CAC (acquire customers cheaper) or protect LTV (retain customers longer).

**Audience:** Internal — founder and future team. Not tenant-facing.

**Location:** `office-dashboard/` directory in this repo (see Runtime Split ADR).

**Primary surface:** Standalone web app (Next.js), with optional Electron wrap for always-on desktop window.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Dashboard purpose | Internal global AI company HQ | One shared internal workspace across all customers, not tenant-facing |
| 2D vs 3D | 3D (React Three Fiber) | 30 agents across 7 departments create visual density that 3D depth handles naturally |
| Art style | Low-poly toon, flat-shaded | Cheap to render (~200-500 poly characters, ~1000-2000 poly rooms), no textures needed. Toon outline shader via Drei `<Outlines>` |
| State source | Event-projected internal read model | Runtime emits events; office projects them into workspace-scoped tables |
| Agent roster | Global canonical registry | One 30-agent internal workforce; customer context attaches to work, not roster |
| State model | LangGraph node mapping | 7 states: idle, context-assembly, policy-gate, execution, verification, persistence, error. Each maps to a furniture zone within a room |
| Voice call visibility | Yes — calls drive ambient activity | When a customer call arrives, agents in the relevant department show activity. Calls are the lifeblood of the product |
| Control plane | Read-heavy in Phase 1 | Only quest resolution is authoritative in first release. Dispatch and override are non-authoritative intents |
| Build acceleration | Droid CLI | Room shells, agent models, animation controllers, and UI overlays are parallelizable |
| State management | Zustand | Lightweight, R3F-friendly state management |
| Realtime delivery | Supabase Realtime | Frontend subscribes to `agent_runtime_state` and `quest` changes |
| Feature flag | Workspace-level internal flag | `internal_config.office_dashboard_enabled` — controls whether event projection pipeline is active |
| Security model | Internal RBAC + redaction | Protect customer data while preserving internal operational visibility |

## Corporate Hierarchy → Agent Roster

### Executive Suite (4 agents)

The strategic apex. CEO sets direction, C-suite translates into departmental execution.

| Agent | ID | Domain | Key Metric |
|---|---|---|---|
| CEO / Founder | `exec-ceo` | Strategy, vision, closing deals, final decisions | LTV:CAC ratio |
| CPO | `exec-cpo` | What to build and why, pricing, value prop | Feature adoption, retention |
| CTO | `exec-cto` | Feasibility, architecture, reliability | Uptime, latency, zero dropped calls |
| COO | `exec-coo` | Post-sale operations, compliance, churn prevention | Churn rate, onboarding time, NPS |

### Product Management (7 agents) — reports to CPO

The engine of discovery and execution. Every PRD is filtered through: "Does this decrease CAC or increase LTV?"

| Agent | ID | Discipline |
|---|---|---|
| Head of Product (Director) | `pm-product-strategy` | Vision, business models, Lean Canvas, SWOT, PESTLE, Porter's Five Forces |
| PM — Discovery & Innovation | `pm-product-discovery` | OSTs, customer interviews, pretotypes, risky assumptions |
| PO — Execution | `pm-execution` | PRDs, sprints, OKRs, user/job stories, stakeholder comms |
| User/Market Researcher | `pm-market-research` | Personas, customer journeys, TAM/SAM/SOM, user feedback |
| Product Data Analyst | `pm-data-analytics` | Product metrics, A/B tests on product changes, cohort retention |
| ProdOps Manager | `pm-toolkit` | Internal coordination, hiring reviews, proofing comms |
| Lead UI/UX Designer | `pm-designer` | Prototypes, usability testing, mobile-first for contractors on job sites |

**Design note:** Growth PM (`pm-marketing-growth`) and Product Marketing GTM (`pm-go-to-market`) were removed as redundant with Head of Growth — growth strategy and ICP/battlecard work belong in Growth Marketing, not Product.

### Engineering (4 agents) — reports to CTO

Turns PRDs into reality. Focus: latency and reliability to prevent churn.

| Agent | ID | Focus |
|---|---|---|
| VP of Engineering (Director) | `eng-vp` | Sprint planning, capacity estimation, delivery |
| AI/Voice Engineer | `eng-ai-voice` | LLMs, prompt engineering, voice latency minimization |
| Full-Stack Developer | `eng-fullstack` | Dashboards, APIs, databases, customer-facing app |
| QA/Automation Engineer | `eng-qa` | Test scenarios, edge cases, zero hallucinations guarantee |

### Growth Marketing (6 agents) — reports to CEO

The lean acquisition machine. Designed to aggressively prospect, enrich leads, and maximize the Founder's demo calendar.

| Agent | ID | Focus |
|---|---|---|
| Head of Growth (Director) | `growth-head` | Top-of-funnel engine, cold email infra, lead magnets, ICP definition, growth loops, positioning |
| CRO Specialist | `growth-cro` | Funnel optimization, squeeze every booked meeting from existing traffic. Tools: `page-cro`, `signup-cro`, `onboard`, `form-cro`, `popup-cro`, `paywall` |
| Content & Copy | `growth-content` | Copywriting, copy editing, cold email drafts, email sequences, social content. Tools: `copywriting`, `copy-edit`, `cold-email`, `email-seq`, `social` |
| Growth Engineer | `growth-engineer` | Landing pages, ROI calculators, sign-up flows (bypasses core eng backlog) |
| Lifecycle/Retention Marketer | `growth-lifecycle` | Automated onboarding comms (email, SMS, in-app), early activation, stop early churn |
| Growth/Data Analyst | `growth-analyst` | Full-funnel dashboards, growth experiment tracking, prove which experiments print money |

**Boundary clarification:** `growth-lifecycle` owns **automated comms** (drip emails, SMS nudges, in-app tooltips). `cs-onboarding` in Customer Success owns **white-glove setup** (voice agent config, first 50 calls). Different channels, complementary coverage.

**Product Data Analyst vs Growth Data Analyst:** These are NOT redundant. Product analyst answers "is the app good?" for the CPO. Growth analyst answers "is the funnel working?" for Head of Growth. Same toolset, different questions, different stakeholders.

### Sales (1 agent) — reports to CEO

The Founder is the sales machine. This single agent tells the Founder who to call next.

| Agent | ID | Focus |
|---|---|---|
| SDR / Lead Router | `sales-sdr` | Prioritize qualified prospects, manage outbound cold calling, inbound filtering, route to Founder |

**Why 1 agent:** The CEO/Founder acts as sole Account Executive, taking all qualified demos. The SDR's sole metric is routing highly qualified, pre-enriched prospects to the Founder. No separate AE or Demo/Closer needed.

### Customer Success (5 agents) — reports to COO

The LTV protection agency. Ensures the product delivers immediate ROI.

| Agent | ID | Focus |
|---|---|---|
| Head of CS (Director) | `cs-head` | LTV protection, pod management, churn prevention strategy |
| Onboarding Specialist | `cs-onboarding` | First 14-30 days, "saved call = saved revenue" moment in 7 days |
| Account Manager (Pod Lead) | `cs-account-manager` | Regular check-ins, ROI proof with hard data, renewals/upsells |
| Pod Technical Support | `cs-tech-support` | Dedicated troubleshooter for the AM's team |
| Pod Success Associate | `cs-associate` | Day-to-day: prompt tweaks, service area changes, routine tasks |

### Finance/Legal (3 agents) — reports to COO

Protects and manages the business.

| Agent | ID | Focus |
|---|---|---|
| Finance Lead (Director) | `fin-lead` | Budget, unit economics, CAC payback period tracking |
| Accounting | `fin-accounting` | Books, billing, revenue recognition |
| Legal/Compliance | `fin-legal` | Contracts, GDPR, compliance, NDAs |

### Roster Summary

| Department | Agents | Reports To | LTV:CAC Role |
|---|---|---|---|
| Executive Suite | 4 | — | Sets strategy |
| Product Management | 7 | CPO | Build sticky product (LTV) |
| Engineering | 4 | CTO | Reliability prevents churn (LTV) |
| Growth Marketing | 6 | CEO | Fill pipeline cheaply (CAC) |
| Sales | 1 | CEO | Route best leads to Founder (CAC) |
| Customer Success | 5 | COO | Retain customers (LTV) |
| Finance/Legal | 3 | COO | Track unit economics |
| **Total** | **30** | | |

**Breakdown: 4 executives + 5 directors + 21 workers = 30 agents**

Directors: Head of Product, VP Engineering, Head of Growth, Head of CS, Finance Lead.
Sales SDR is a worker, not a director.

### Activation Priority

Departments come alive in this order, matching business priority:

| Priority | Department | Rationale |
|---|---|---|
| 1st | Product/Engineering | Keep the product sharp. 5 worker specs already exist. |
| 2nd | Growth Marketing | Fill the pipeline so the Founder has demos to close. |
| 3rd | Customer Success / Operations | Retain customers after they sign. Protect LTV. |
| 4th | Sales | 1 agent. Lightweight. Comes alive once pipeline flows. |
| 5th | Finance/Legal | Last. Business is running before you optimize books. |

## 3D Office Layout

### Floor Plan (Orbital View)

7 department rooms + Executive Suite + Central Lobby. Mirrors the org chart exactly.

```
                    ┌───────────────┐
                   /  EXECUTIVE    / │
                  /    SUITE      / /│
                 ├───────────────┤/ │
                 │ CEO CPO CTO   │  │
                 │     COO       │ /
                 └───────┬───────┘/
                         │
    ┌─────────┐    ┌─────┴──────────────────────────┐    ┌─────────┐
   /Product  //│  /          CENTRAL LOBBY          /│  / Finance //│
  / Mgmt    / /│ / Deal Breaker Board · Quest Kiosk/ │ / Legal   / /│
 ├─────────┤/ │├─ Memo Board · Meeting Table ──────┤ │├─────────┤/ │
 │ 👔 + 6  │  ││                                    │/ │ 👔 + 2  │  │
 │         │ / └────┬───────────────────────┬──────┘  │         │ /
 └─────────┘/      │                       │          └─────────┘/
                    │                       │
    ┌─────────┐  ┌──┴──────┐  ┌───────────┐  ┌─────────┐
   /Engineer //│/ Growth  //│/ Customer  //│ / Sales  //│
  /         / /│/ Mktg   / /│/ Success  / /│/         / │
 ├─────────┤/ ├─────────┤/ ├─────────┤/  ├─────────┤/ │
 │ 👔 + 3  │  │ 👔 + 5  │  │ 👔 + 4  │   │   1     │  │
 │         │/ │         │/ │         │/   │         │ /
 └─────────┘  └─────────┘  └─────────┘    └─────────┘
```

**Spatial relationships encode real handoff paths:**
- Executive Suite → all departments (strategic direction cascades down)
- Growth Marketing → Sales (enriched lead handoff via lobby corridor)
- Sales → Customer Success (closed deal → onboarding via lobby corridor)
- Product/Engineering ↔ all departments (feature work, bug fixes)
- Finance/Legal ↔ all departments (compliance checks, approvals)
- Growth Marketing ↔ Product Management (Deal Breaker Ledger in lobby)

### Camera System

- **Orbital view (default):** 45-degree isometric angle. All 7 rooms + Executive Suite + lobby visible. User can orbit and zoom.
- **Room fly-in:** Click a room to animate camera through the door. 7 LangGraph zones visible as furniture clusters. Back button or ESC flies camera out.
- **Executive Suite fly-in:** Click the top floor to see the C-suite. CEO's desk has the LTV:CAC dial.
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

**Executive Suite special treatment:** Larger desks, glass walls overlooking the lobby. CEO desk has an LTV:CAC dial. CPO desk has a product roadmap board. CTO desk has a system health monitor. COO desk has a churn radar.

**CEO desk metric:** `LTV:CAC (rolling 90-day blended snapshot)` refreshed every 15 minutes from `office_kpi_snapshot`. UI displays both value and freshness label, e.g. `3.2:1 · updated 11 min ago`. Numerator: projected gross-margin-adjusted LTV for active cohorts. Denominator: fully loaded paid acquisition cost for the same rolling window. **Phase 1:** Ships as placeholder dial showing "Awaiting data" until the KPI computation pipeline exists (Phase 2). The dial and snapshot table are structurally ready — only the computation is deferred.

**Director's corner office:** Glass-walled area in each department room. Director sits at a larger desk. Colored light on the glass reflects department health:
- Green = all agents idle or working normally
- Yellow = policy gate quest pending
- Red = error state in department

### Voice Call Ambient Activity

When a customer's call comes in (via `calllock/call.started` or `calllock/call.ended`):

1. A phone rings on the relevant agent's desk (CS for existing customer, Growth for inbound lead)
2. The agent picks up, walks to execution zone
3. Extraction pipeline runs — visible as document icons flowing between stations
4. Route to appropriate handler (onboarding, support, sales prioritizer)
5. Call counter ticks up on the department's wall display
6. If the call triggers a policy gate (after-hours, schedule change), a quest is created

This makes the product's lifeblood visible in the office — when calls aren't flowing, the office is quiet. When calls spike, the office buzzes.

**PII note:** Call ambient activity shows classification and outcome summaries only. No caller phone numbers, names, or transcript text in the ambient view.

### Deal Breaker Ledger (Central Lobby)

A physical board mounted on the lobby wall between the Growth Marketing and Product Management corridors. This is the spatial manifestation of the Growth Loop (Section 6 of the Operating Blueprint).

**Behavior:**
- Growth Marketing agents walk to the lobby and write entries: "Lost 20% of deals because of X"
- Product Management agents read from the board and carry entries back to their room
- The board shows a running count of open deal breakers and resolved ones
- Clicking the board opens an HTML overlay with the full ledger
- New entries trigger a subtle glow animation on the board
- When a Product agent picks up an entry, a briefcase-carry animation plays back to Product room

**Visual treatment:** Cork board with pinned cards. Red cards = open deal breakers. Green cards = resolved (solution shipped). The ratio of red to green is immediately visible from orbital view.

**Backed by:** `deal_breaker` table (see Supabase Schema).

### Hallway Handoff Animation

When `calllock/agent.handoff` fires:
1. Source agent stands up from their zone
2. Walks through glass-walled corridor into Central Lobby
3. Carries a glowing briefcase (representing context payload)
4. Walks through the corridor to the destination room
5. Destination agent receives the briefcase and walks to context-assembly zone

Cross-department bottlenecks are visible — a busy hallway means lots of work flowing between teams.

**Backed by:** `agent_handoff_log` table (see Supabase Schema).

## Inngest Event Schema

### Common Envelope

All office events carry a workspace scope and optional customer context:

```typescript
type OfficeEventEnvelope = {
  workspace_id: string
  timestamp: string
  customer_id?: string
  tenant_id?: string
  call_id?: string
  lead_id?: string
  account_id?: string
}
```

### Core Events

```typescript
// Agent state transition
"calllock/agent.state.changed" -> {
  workspace_id: string,
  agent_id: string,
  department: string,
  role: "executive" | "director" | "worker",
  supervisor_id?: string,
  from_state: LangGraphState,
  to_state: LangGraphState,
  description: string,
  active_context_type?: "call" | "lead" | "quest" | "deal_breaker" | "memo" | "incident",
  active_context_id?: string,
  customer_id?: string,
  tenant_id?: string,
  call_id?: string,
  triggered_by: "system" | "human",
  timestamp: string
}

// Cross-department handoff
"calllock/agent.handoff" -> {
  workspace_id: string,
  from_agent: string,
  to_agent: string,
  from_department: string,
  to_department: string,
  context_type: "call" | "lead" | "quest" | "deal_breaker" | "incident",
  context_id?: string,
  context_summary: string,
  customer_id?: string,
  tenant_id?: string,
  call_id?: string,
  lead_id?: string,
  timestamp: string
}

// Policy gate hit — becomes a Quest
"calllock/policy.gate.pending" -> {
  workspace_id: string,
  quest_id: string,
  agent_id: string,
  department: string,
  customer_id?: string,
  tenant_id?: string,
  call_id?: string,
  rule_violated: string,
  summary: string,
  options: string[],
  urgency: "low" | "medium" | "high",
  timestamp: string
}

// Policy gate resolved
"calllock/policy.gate.resolved" -> {
  workspace_id: string,
  quest_id: string,
  resolution: string,
  resolved_by: string,
  customer_id?: string,
  tenant_id?: string,
  call_id?: string,
  timestamp: string
}

// Deal breaker logged
"calllock/deal_breaker.logged" -> {
  workspace_id: string,
  deal_breaker_id: string,
  reported_by_agent_id: string,
  title: string,
  summary: string,
  customer_id?: string,
  tenant_id?: string,
  lead_id?: string,
  evidence?: Record<string, unknown>,
  timestamp: string
}

// Daily memo generation (cron-triggered)
"calllock/memo.daily.generate" -> {
  workspace_id: string,
  date: string
}

// Command center: task dispatch (Phase 1: non-authoritative intent)
"calllock/agent.dispatch.intent" -> {
  workspace_id: string,
  agent_id: string,
  department: string,
  task_description: string,
  dispatched_by: string,
  priority: "low" | "medium" | "high",
  timestamp: string
}

// Command center: handoff override (Phase 1: non-authoritative intent)
"calllock/handoff.override.intent" -> {
  workspace_id: string,
  handoff_id: string,
  original_target: string,
  new_target: string,
  overridden_by: string,
  reason: string,
  timestamp: string
}

// Meeting requested (Phase 2)
"calllock/meeting.requested" -> {
  workspace_id: string,
  meeting_id: string,
  type: "handoff" | "escalation" | "standup",
  attendees: { agent_id: string, department: string, role: string }[],
  trigger_event: string,
  customer_id?: string,
  tenant_id?: string,
  call_id?: string,
  timestamp: string
}

// Voice call events — ambient activity triggers
"calllock/call.started" -> {
  workspace_id: string,
  call_id: string,
  customer_id?: string,
  tenant_id?: string,
  caller_phone: string,
  timestamp: string
}

"calllock/call.ended" -> {
  workspace_id: string,
  call_id: string,
  customer_id?: string,
  tenant_id?: string,
  classification: string,
  score: number,
  routed_to?: string,
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

### Workspace Model

The office uses internal workspace-scoped RBAC, not customer-tenant RLS. Access is restricted to authenticated internal users. Customer identifiers appear in work context, but the office itself is not a tenant-isolated product surface.

If row-level controls are needed, they are based on `workspace_id` and internal role membership, not `public.current_tenant_id()`.

### Agent Registry (static roster)

```sql
CREATE TABLE agent_registry (
  agent_id TEXT PRIMARY KEY,
  workspace_id UUID NOT NULL,
  display_name TEXT NOT NULL,
  department TEXT NOT NULL,
  role TEXT NOT NULL,              -- 'executive' | 'director' | 'worker'
  supervisor_id TEXT,
  roster_status TEXT NOT NULL,     -- 'live' | 'coming_soon'
  worker_spec_id TEXT,             -- nullable until backed by real worker spec
  room_key TEXT NOT NULL,
  seat_key TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Agent Runtime State (live read model)

```sql
CREATE TABLE agent_runtime_state (
  workspace_id UUID NOT NULL,
  agent_id TEXT NOT NULL REFERENCES agent_registry(agent_id),
  current_state TEXT NOT NULL,
  description TEXT,
  active_context_type TEXT,        -- 'call' | 'lead' | 'quest' | 'deal_breaker' | 'memo' | 'incident'
  active_context_id TEXT,
  customer_id UUID,
  tenant_id UUID,
  call_id TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (workspace_id, agent_id)
);
```

### Quest

```sql
CREATE TABLE quest (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  agent_id TEXT NOT NULL REFERENCES agent_registry(agent_id),
  department TEXT NOT NULL,
  customer_id UUID,
  tenant_id UUID,
  call_id TEXT,
  rule_violated TEXT NOT NULL,
  summary TEXT NOT NULL,
  options JSONB NOT NULL,
  urgency TEXT NOT NULL DEFAULT 'medium',
  status TEXT NOT NULL DEFAULT 'pending',   -- pending | resolved | expired
  resolution TEXT,
  resolved_by UUID,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_quest_pending ON quest (workspace_id, status) WHERE status = 'pending';
CREATE INDEX idx_quest_created ON quest (workspace_id, created_at DESC);
```

### Deal Breaker

```sql
CREATE TABLE deal_breaker (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  customer_id UUID,
  tenant_id UUID,
  source_department TEXT NOT NULL DEFAULT 'growth_marketing',
  reported_by_agent_id TEXT NOT NULL REFERENCES agent_registry(agent_id),
  owner_agent_id TEXT REFERENCES agent_registry(agent_id),
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  evidence JSONB,
  status TEXT NOT NULL DEFAULT 'open',      -- open | accepted | in_progress | resolved | rejected
  linked_prd_ref TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);
```

### Agent Handoff Log

```sql
CREATE TABLE agent_handoff_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  from_agent_id TEXT NOT NULL REFERENCES agent_registry(agent_id),
  to_agent_id TEXT NOT NULL REFERENCES agent_registry(agent_id),
  from_department TEXT NOT NULL,
  to_department TEXT NOT NULL,
  context_type TEXT NOT NULL,
  context_id TEXT,
  customer_id UUID,
  tenant_id UUID,
  call_id TEXT,
  context_summary TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_handoff_log_workspace_created ON agent_handoff_log (workspace_id, created_at DESC);
```

### Office KPI Snapshot

```sql
CREATE TABLE office_kpi_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  snapshot_at TIMESTAMPTZ NOT NULL,
  ltv_cac_ratio NUMERIC(10,2),
  ltv_cac_window_days INTEGER NOT NULL DEFAULT 90,
  cac_payback_months NUMERIC(10,2),
  qualified_leads INTEGER,
  demos_booked INTEGER,
  deals_closed INTEGER,
  churn_signals INTEGER,
  active_customers INTEGER,
  calls_handled INTEGER,
  memo_payload JSONB
);
```

### Command Audit Log

```sql
CREATE TABLE command_audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  user_id UUID NOT NULL,
  action_type TEXT NOT NULL,       -- 'quest_resolve' | 'dispatch_intent' | 'handoff_override_intent'
  target_agent TEXT,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_log_workspace_created ON command_audit_log (workspace_id, created_at DESC);
```

### Agent State History (sparklines)

```sql
CREATE TABLE agent_state_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  agent_id TEXT NOT NULL REFERENCES agent_registry(agent_id),
  state TEXT NOT NULL,
  description TEXT,
  active_context_type TEXT,
  active_context_id TEXT,
  customer_id UUID,
  tenant_id UUID,
  recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_state_history_agent_24h ON agent_state_history (workspace_id, agent_id, recorded_at DESC);
```

Append-only log of every state transition. Powers the 24-hour sparkline on the agent sidebar. Inngest function that upserts `agent_runtime_state` also appends to `agent_state_history`. Retention: 30 days, then archive or prune.

### Supabase Realtime Publication Setup

All tables subscribed to by the dashboard must be configured for Realtime broadcast. Include in the migration:

```sql
-- Required for Supabase Realtime to broadcast row changes
ALTER TABLE agent_runtime_state REPLICA IDENTITY FULL;
ALTER TABLE quest REPLICA IDENTITY FULL;
ALTER TABLE deal_breaker REPLICA IDENTITY FULL;
ALTER TABLE office_kpi_snapshot REPLICA IDENTITY FULL;

-- Add tables to the Supabase Realtime publication
-- (exact syntax depends on Supabase project setup — may use supabase_realtime publication)
```

**Critical:** Without `REPLICA IDENTITY FULL` and publication membership, Realtime subscriptions connect successfully but receive zero events — a silent failure with no error indication.

### Phase 2 Tables

```sql
CREATE TABLE meeting (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  type TEXT NOT NULL,
  trigger_event TEXT,
  department TEXT,
  status TEXT NOT NULL DEFAULT 'in_progress',
  attendees JSONB NOT NULL,
  customer_id UUID,
  tenant_id UUID,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE meeting_turn (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  meeting_id UUID NOT NULL REFERENCES meeting(id),
  agent_id TEXT NOT NULL,
  round INTEGER NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE meeting_action_item (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL,
  meeting_id UUID NOT NULL REFERENCES meeting(id),
  assigned_to TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  due_by TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);
```

## Control Plane

**Control-plane rule:** In Phase 1, the office is a read-heavy operational surface. The only authoritative runtime mutation is quest resolution. Dispatch and handoff override remain non-authoritative operator intents until the runtime supervisor is generalized and can safely accept external control commands.

### Phase 1: Authoritative Actions

| Action | Event | Auth Role | Status |
|---|---|---|---|
| Resolve quest | `calllock/policy.gate.resolved` | operator, admin | **Authoritative** — changes agent state |

### Phase 1: Non-Authoritative Intents

| Action | Event | Auth Role | Status |
|---|---|---|---|
| Dispatch task | `calllock/agent.dispatch.intent` | operator, admin | **Intent only** — logged, not executed by runtime |
| Override handoff | `calllock/handoff.override.intent` | admin | **Intent only** — logged, not executed by runtime |

These become authoritative in Phase 2+ when the supervisor graph can accept external control commands.

### Auth Roles

- `viewer` — read-only: see the office, read quests, read memos
- `operator` — viewer + resolve quests
- `admin` — operator + manage future control-plane actions, thresholds, and simulation tools

## Quest Log

Lives in the Central Lobby as a clickable kiosk. Also accessible as a persistent sidebar toggle.

### Behavior
- `calllock/policy.gate.pending` events create quests
- Each quest displays: agent name, department, urgency, summary, and resolution options
- Clicking a resolution button fires `calllock/policy.gate.resolved` via Inngest
- The agent at policy-gate zone immediately walks to execution or back to idle
- Resolved quests roll into a collapsible "Resolved Today" section
- Orbital view shows quest count badges on affected rooms

### Quest Display

```
┌─── QUEST LOG ──────────────────────────────────┐
│                                                  │
│  RED HIGH  "After-hours schedule change"         │
│     Agent: cs-onboarding (Customer Success)      │
│     Call #4821 - 2 min ago                       │
│     [Approve] [Deny] [Escalate to COO]           │
│                                                  │
│  YLW MED   "Lead score below threshold"          │
│     Agent: sales-sdr (Sales)                     │
│     Lead #892 - 8 min ago                        │
│     [Override & Route to Founder] [Skip] [Return]│
│                                                  │
│  GRN LOW   "Missing compliance cert"             │
│     Agent: fin-legal (Finance/Legal)             │
│     Vendor #33 - 1 hr ago                        │
│     [Approve Temp] [Block] [Request Cert]        │
│                                                  │
│  -- Resolved Today: 12 ────────────────────────  │
│  OK "Duplicate contact merge" -> Approved        │
│  OK "Discount > 20%" -> Escalated to CEO         │
└──────────────────────────────────────────────────┘
```

## Daily Memo

Wall-mounted board in the Central Lobby. Backed by `office_kpi_snapshot`.

### Memo Display

```
┌─── DAILY MEMO - March 16, 2026 ─────────────────┐
│                                                    │
│  EXECUTIVE SUITE                                   │
│  +-- LTV:CAC ratio: 3.2:1 (target: >3:1)         │
│  +-- 2 strategic decisions pending                │
│  +-- CEO closed 1 deal, 2 demos scheduled         │
│                                                    │
│  PRODUCT MANAGEMENT                                │
│  +-- 3 PRDs in execution, 1 in discovery          │
│  +-- Designer shipped mobile notification proto   │
│  +-- 2 policy escalations (both resolved)         │
│                                                    │
│  ENGINEERING                                       │
│  +-- 23 calls handled by voice pipeline           │
│  +-- QA flagged 1 verification failure            │
│  +-- Latency p99: 1.2s (target: <2s)             │
│                                                    │
│  GROWTH MARKETING                                  │
│  +-- 14 leads qualified via cold email            │
│  +-- CRO: landing page conversion up 12%         │
│  +-- 8 leads routed to Founder as hot leads       │
│                                                    │
│  SALES                                             │
│  +-- SDR routed 8 leads, 5 met qualification gate │
│  +-- Founder completed 3 demos, closed 1          │
│                                                    │
│  CUSTOMER SUCCESS                                  │
│  +-- 1 new customer onboarding started            │
│  +-- 6 support tickets resolved                   │
│  +-- Avg first-response: 4.2 min                  │
│                                                    │
│  FINANCE/LEGAL                                     │
│  +-- 3 compliance checks completed                │
│  +-- CAC payback period: 4.8 months               │
│  +-- 0 blocks issued                              │
│                                                    │
│  [< Mar 15]                        [Mar 17 >]    │
└──────────────────────────────────────────────────┘
```

## Key Cross-Department Flows

### Flow 1: Lead → Demo → Customer (The Revenue Path)

```
Growth Marketing          Sales              Customer Success
┌──────────┐             ┌──────────┐        ┌──────────┐
│ Head of  │  enriched   │ SDR      │  "call │ Onboard  │
│ Growth   │  lead       │ routes   │  this  │ Specialist│
│ qualifies│──briefcase─>│ to       │─ one"─>│ sets up  │
│          │  via lobby  │ Founder  │ via CEO│ voice    │
└──────────┘             └──────────┘        └──────────┘
```

### Flow 2: Call → Insight → Product (The Learning Loop)

```
Voice Pipeline           Customer Success     Product Management
┌──────────┐             ┌──────────┐        ┌──────────┐
│ Call      │  metrics    │ Account  │  usage │ PM       │
│ comes in  │──────────>│ Manager  │─ data─>│ Discovery│
│ (ambient  │            │ tracks   │        │ finds    │
│ activity) │            │ ROI      │        │ patterns │
└──────────┘             └──────────┘        └──────────┘
```

### Flow 3: Deal Breaker → Product Fix (The Growth Loop)

```
Growth Marketing                    Product Management
┌──────────┐                       ┌──────────┐
│ "Lost 20%│   Deal Breaker       │ Head of  │
│ of deals │──  Ledger in  ──────>│ Product  │
│ because  │   Central Lobby      │ owns the │
│ of X"    │                      │ solution │
└──────────┘                       └──────────┘
```

## Workforce Architecture

### Invocation Shape: RunTaskRequest

The existing `ProcessCallRequest` assumes call-centric inputs. A 30-agent workforce needs a generalized request model. Rather than replacing `ProcessCallRequest`, extend it:

```python
class RunTaskRequest(StrictModel):
    worker_id: str                          # agent_id from agent_registry
    tenant_id: str                          # workspace_id (= CallLock tenant_id)
    trigger: str                            # "cron:growth.daily.pipeline" | "event:call.ended" | "dispatch:growth-head"
    task_type: str                          # "daily_sweep" | "lead_score" | "onboarding_check" | "analysis"
    task_context: dict[str, Any]            # agent-specific input payload
    source_refs: list[str] = []             # IDs of triggering events/calls/leads
    priority: str = "normal"                # "low" | "normal" | "high" | "critical"
    idempotency_key: str                    # prevents duplicate execution
    context_budget: int = 1200
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    compliance_rules: list[dict[str, Any]] = Field(default_factory=list)
    tenant_config: dict[str, Any] = Field(default_factory=dict)
    environment_allowed_tools: list[str] = Field(default_factory=list)
    memory: list[dict[str, Any]] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)
    job_requests: list[dict[str, Any]] = Field(default_factory=list)
```

`ProcessCallRequest` becomes a specialized case of `RunTaskRequest` where `task_type = "process_call"` and `task_context` contains `transcript` and `problem_description`.

### Director-as-Dispatcher Pattern

A director is a specialized worker whose output includes downstream `job_requests` for department workers. This reuses the existing `dispatch_job_requests` seam in `supervisor.py:125` and `dispatch.py:36`.

```
Inngest cron/event
       │
       ▼
RunTaskRequest(worker_id="growth-head", trigger="cron:growth.daily.pipeline")
       │
       ▼
┌──────────────────────────────┐
│ run_supervisor()             │  ← existing pipeline, no changes needed
│  context_assembly            │
│  policy_gate                 │
│  _worker_node (growth-head)  │  ← director worker spec decides what to dispatch
│  verification                │
│  _job_dispatch_node          │  ← fans out job_requests to department workers
│  persist                     │
└──────────────────────────────┘
       │
       ▼ job_requests emitted
┌──────────────────────────────┐
│ dispatch_job_requests()      │  ← existing mechanism in dispatch.py
│  → create_job() in Supabase  │
│  → fire Inngest event        │  "harness/job-dispatch"
└──────┬───────────────────────┘
       │
  ┌────┴────┬──────────┬──────────┐
  ▼         ▼          ▼          ▼
RunTaskRequest      RunTaskRequest    RunTaskRequest
(growth-cro)        (growth-analyst)  (growth-content)
  │                   │                 │
  ▼                   ▼                 ▼
run_supervisor()   run_supervisor()  run_supervisor()
```

**Key insight:** The supervisor graph is already parameterized by `worker_spec`. A director agent's worker spec produces `job_requests` as output. The existing `_job_dispatch_node` handles fan-out. No new scheduling infrastructure needed.

### Three Execution Loops

Events and crons should NOT all funnel through the org chart. The workforce operates in three loops:

**Operational loop (event-driven, direct to owner):**
- `calllock/call.ended` → CS department (if existing customer) or Growth (if inbound lead)
- `calllock/customer.onboarded` → `cs-onboarding` directly
- `calllock/support.ticket.created` → `cs-tech-support` directly
- New lead enriched → `sales-sdr` directly

**Management loop (scheduled department sweeps):**
- One cron per department (not per agent): `calllock/dept.{dept}.daily.sweep`
- Cron fires → director agent runs → director decides which workers to dispatch
- Directors: `pm-product-strategy`, `eng-vp`, `growth-head`, `cs-head`, `fin-lead`
- Weekly variant: `calllock/dept.{dept}.weekly.sweep` for deeper analysis

**Executive loop (summary + exception only):**
- `calllock/exec.daily.brief` (cron 7am) → CEO agent
- CEO consumes: KPI snapshot, quest summary, deal breaker count, SDR call list
- C-suite agents consume: department sweep summaries + threshold breach alerts
- Executives do NOT sit in front of operational events

### Execution Modes

Each worker spec declares one of three execution modes. This determines resource usage and scheduling priority:

| Mode | What it does | LLM calls | Examples |
|---|---|---|---|
| `deterministic` | SQL, metrics, filtering, joins, scoring, threshold checks, reconciliation, formatting | 0 | `pm-data-analytics`, `growth-analyst`, `fin-accounting`, `eng-qa` (metric checks) |
| `light_llm` | Summaries, classification, short recommendations, structured extraction review | 1-2 | `cs-head` (churn analysis), `eng-ai-voice` (prompt review), `sales-sdr` (lead scoring) |
| `heavy_llm` | Copywriting, transcript analysis, strategic reasoning, ambiguous decision support | 2-5 | `growth-content` (cold email drafts), `pm-product-discovery` (OST generation), `exec-ceo` (strategic briefing) |

**Scheduling implication:** Deterministic work runs first (instant). Light LLM next (fast). Heavy LLM is queue-managed to respect rate limits. The morning burst of ~15 agents does NOT mean 15 simultaneous LLM calls — most agents are deterministic or light.

### Scheduling Constraints

| Constraint | Rule |
|---|---|
| Concurrency cap per agent | 1 (no agent runs two tasks simultaneously) |
| Concurrency cap per department | 3 (max 3 workers running at once per department), enforced via Inngest concurrency key |
| Cooldown/debounce | Event-driven agents debounce within 60s (coalesce rapid events) |
| Idempotency scope | `{worker_id}:{task_type}:{date}` for crons, `{worker_id}:{source_ref}` for events |
| Supersession | New cron run supersedes any uncompleted prior run of the same type |
| Stale work TTL | If a task hasn't completed in 15 min, mark as timed out, log, do not retry |
| LLM rate limit management | `heavy_llm` agents share a separate Inngest concurrency key with limit = 3 across all departments |

### Quest as Approval Projection

Office quests are NOT a separate human-decision system. They are the office-facing projection of the existing approval system (`approvals.py:8`).

```
Existing approval flow:
  policy_gate → verdict: "escalate" → create_approval_request() → pending in approval_requests table

Office quest projection:
  approval_requests (status=pending) → projected into quest table for office UI
  quest resolution in office → calls resolve_approval_request() → triggers continue_approved_request()
```

This means:
- `quest` table is a **read projection** of `approval_requests`, enriched with office-specific fields (department, urgency, display options)
- Quest resolution writes to `approval_requests` via the existing `resolve_approval_request()` function
- The harness picks up the approval resolution via the existing `continue_approved_request()` flow
- No new human-decision runtime needed

### Terminology

| Term | Definition |
|---|---|
| **Run** | A single execution of the supervisor graph for one agent. Has a `run_id`. |
| **Job** | A persisted work item in the `jobs` table. Created by `dispatch_job_requests`. May trigger a run. |
| **Quest** | An office-facing projection of a pending approval request. Resolved via the approval system. |
| **Sweep** | A scheduled department-level cron that triggers the director agent. |
| **Dispatch** | A director creating `job_requests` that fan out to department workers. |

### Agent Task Matrix

#### Executive Suite (4 agents)

| Agent | ID | Loop | Trigger | Input | Output | Frequency |
|---|---|---|---|---|---|---|
| CEO | `exec-ceo` | Executive | `calllock/exec.daily.brief` | KPI snapshot, quest summary, deal breaker count, SDR call list | "Good morning" briefing, strategic decision quests if thresholds breached | Daily 7am |
| CPO | `exec-cpo` | Executive | `calllock/exec.weekly.strategy` + deal breaker events | Deal breaker ledger, product usage, feature adoption | Prioritized deal breaker response, roadmap recommendations | Weekly Mon 8am + event |
| CTO | `exec-cto` | Executive | `calllock/exec.daily.brief` | Voice pipeline latency, error rates, uptime, QA results | System health for memo, incident quests if SLA breached | Daily 6am |
| COO | `exec-coo` | Executive | `calllock/exec.daily.brief` | Churn signals, onboarding status, support volume, compliance | Ops health for memo, churn risk quests | Daily 7am |

#### Product Management (7 agents) — Sweep: `calllock/dept.product.daily.sweep`

| Agent | ID | Loop | Trigger | Input | Output | Frequency |
|---|---|---|---|---|---|---|
| Head of Product | `pm-product-strategy` | Management | Dept sweep + deal breaker events | Deal breaker ledger, usage data, churn reasons | Dispatches to PM workers. Strategy updates. | Daily + event |
| PM Discovery | `pm-product-discovery` | Management | Dispatched by director | Interview transcripts, ticket themes, call patterns | OSTs, experiment proposals, assumption maps | On dispatch |
| PO Execution | `pm-execution` | Management | Dispatched by director + bi-weekly sprint cron | PRD queue, sprint backlog, OKR progress | Sprint plans, user stories, status updates | Bi-weekly + dispatch |
| Market Researcher | `pm-market-research` | Management | Monthly sweep variant | Call demographics, lead sources, competitor mentions | Persona updates, TAM/SAM/SOM, segment analysis | Monthly |
| Product Data Analyst | `pm-data-analytics` | Management | Daily sweep | Product usage, feature adoption, A/B results | Metrics dashboard data, cohort analysis | Daily |
| ProdOps | `pm-toolkit` | Management | Dispatched by director | Coordination needs, hiring pipeline | Proofed comms, hiring reviews, process docs | On dispatch |
| Lead Designer | `pm-designer` | Management | Dispatched by director | PRDs, user feedback, usability results | Prototypes, usability reports | On dispatch |

#### Engineering (4 agents) — Sweep: `calllock/dept.engineering.daily.sweep`

| Agent | ID | Loop | Trigger | Input | Output | Frequency |
|---|---|---|---|---|---|---|
| VP Engineering | `eng-vp` | Management | Dept sweep + incident events | Sprint status, PR queue, incidents, capacity | Dispatches to eng workers. Sprint health for memo. | Daily + event |
| AI/Voice Engineer | `eng-ai-voice` | Operational | `calllock/call.ended` (sampled) + dispatch | Call transcripts, latency, prompt performance | Prompt improvements, latency reports | Sampled + dispatch |
| Full-Stack Dev | `eng-fullstack` | Management | Dispatched by director | PRDs, bugs, API performance | Implementation plans, performance reports | On dispatch |
| QA Engineer | `eng-qa` | Management | Daily sweep + deployment events | Sampled calls, extraction results, classifications | Test results, hallucination reports, regression alerts | Daily + event |

#### Growth Marketing (6 agents) — Sweep: `calllock/dept.growth.daily.sweep`

| Agent | ID | Loop | Trigger | Input | Output | Frequency |
|---|---|---|---|---|---|---|
| Head of Growth | `growth-head` | Management | Dept sweep + lead events | Funnel metrics, lead volume, conversion rates | Dispatches to growth workers. Pipeline health for memo. | Daily + event |
| CRO Specialist | `growth-cro` | Management | Weekly sweep variant | Landing page analytics, funnel data | Optimization recommendations, A/B proposals | Weekly |
| Content & Copy | `growth-content` | Management | Dispatched by director | Campaign briefs, winning angles, objections | Cold email drafts, sequences, social content | On dispatch |
| Growth Engineer | `growth-engineer` | Management | Dispatched by director | CRO recommendations, page briefs | Landing page implementations, calculator updates | On dispatch |
| Lifecycle Marketer | `growth-lifecycle` | Operational | `calllock/customer.onboarded` + daily sweep | New customer events, activation metrics, churn signals | Onboarding sequences, SMS nudges, activation reports | Event + daily |
| Growth Analyst | `growth-analyst` | Management | Daily sweep | Full-funnel data, experiment results, cost data | Funnel dashboards, experiment scorecards, CAC by channel | Daily |

#### Sales (1 agent) — Direct to CEO

| Agent | ID | Loop | Trigger | Input | Output | Frequency |
|---|---|---|---|---|---|---|
| SDR / Lead Router | `sales-sdr` | Operational | `calllock/sdr.daily.prioritize` + new lead events | Enriched leads, ICP criteria, lead scores | Prioritized "call these N people" list | Daily 7:30am + event |

#### Customer Success (5 agents) — Sweep: `calllock/dept.cs.daily.sweep`

| Agent | ID | Loop | Trigger | Input | Output | Frequency |
|---|---|---|---|---|---|---|
| Head of CS | `cs-head` | Management | Dept sweep + churn signal events | Customer health, churn signals, NPS, onboarding status | Dispatches to CS workers. LTV report for memo. | Daily + event |
| Onboarding Specialist | `cs-onboarding` | Operational | `calllock/customer.onboarded` + daily sweep | New customer data, first-7-day call volume | Onboarding status, "no saved call by day 7" quests | Event + daily |
| Account Manager | `cs-account-manager` | Management | Weekly sweep + churn events | Usage data, ROI metrics, renewal dates | Account health reports, ROI proofs, renewal quests | Weekly + event |
| Pod Tech Support | `cs-tech-support` | Operational | `calllock/support.ticket.created` + dispatch | Support tickets, error logs, call failure data | Troubleshooting reports, resolution actions | Event + dispatch |
| Pod Success Associate | `cs-associate` | Management | Dispatched by director | Routine task queue | Completed routine tasks | On dispatch |

#### Finance/Legal (3 agents) — Sweep: `calllock/dept.finance.weekly.sweep`

| Agent | ID | Loop | Trigger | Input | Output | Frequency |
|---|---|---|---|---|---|---|
| Finance Lead | `fin-lead` | Management | Weekly sweep + monthly close | Revenue, costs, customer count, churn | Dispatches to fin workers. Unit economics for memo. | Weekly + monthly |
| Accounting | `fin-accounting` | Management | Daily sweep | Billing events, payments, subscriptions | Books reconciliation, billing anomaly alerts | Daily |
| Legal/Compliance | `fin-legal` | Management | Monthly sweep + contract events | Contracts, GDPR audit, compliance checklist | Compliance reports, contract review quests | Monthly + event |

### Trigger Summary (after cron consolidation)

| Trigger Type | Count | Examples |
|---|---|---|
| Department daily sweeps | 5 | `calllock/dept.{product,engineering,growth,cs,finance}.daily.sweep` |
| Department weekly sweeps | 3 | `calllock/dept.{product,growth,finance}.weekly.sweep` |
| Department monthly sweeps | 2 | `calllock/dept.{product,finance}.monthly.sweep` |
| Executive daily brief | 1 | `calllock/exec.daily.brief` |
| Executive weekly strategy | 1 | `calllock/exec.weekly.strategy` |
| SDR daily prioritize | 1 | `calllock/sdr.daily.prioritize` |
| Operational event triggers | 4 | `call.ended`, `customer.onboarded`, `support.ticket.created`, new lead |
| **Total Inngest crons** | **13** | Down from ~20 in the per-agent model |
| **Total event triggers** | **4** | Direct to owning agent |

## Backend Prerequisites

### Phase 1 Runtime Truth

The office can ship before the full workforce exists. `agent_registry` defines all 30 characters now. `agent_runtime_state` is live for agents backed by real worker specs and synthetic/demo for the remainder. The visual roster is therefore stable even while the underlying workforce is rolled out incrementally.

### Canonical Roster Source

The single source of truth for the 30-agent roster is `knowledge/office-roster.yaml`. This file defines each agent's `agent_id`, `display_name`, `department`, `role`, `supervisor_id`, `roster_status`, `worker_spec_id`, `room_key`, and `seat_key`. A seed script reads this file and populates `agent_registry`. The markdown roster tables in this spec are derived from the YAML file, not the other way around.

### Existing Worker Spec → New Roster Mapping

| Existing Spec | Maps To |
|---|---|
| `product-manager` | `pm-execution` (PO — Execution) |
| `designer` | `pm-designer` (Lead UI/UX Designer) |
| `engineer` | `eng-fullstack` (Full-Stack Developer) |
| `product-marketer` | `growth-head` (Head of Growth) — closest match, may need rework |
| `customer-analyst` | `pm-data-analytics` (Product Data Analyst) — closest match |

### Harness Event Emission

- **Write path:** `InngestEventEmitter` fires `calllock/agent.state.changed` on each LangGraph node entry. Parallels existing `MetricsEmitter`.
- **agent_id sourcing:** The emitter reads the `worker_spec.id` of the currently executing worker and uses it as `agent_id`. A small mapping config handles the 5 cases where existing spec ids differ from office agent_ids (e.g., `customer-analyst` → `pm-data-analytics`).
- **Read path:** Dashboard subscribes to Supabase Realtime on `agent_runtime_state`.
- **Feature flag:** `internal_config.office_dashboard_enabled` (workspace-level, not tenant-level).
- **Failure handling:** The emitter must log + continue on all failures (timeout, rate limit, malformed payload, connection error). It must NEVER block the harness pipeline. If the feature flag check itself fails (DB unreachable), default to disabled.
- **Backup channel:** Harness subscribes to `quest` status changes via Supabase Realtime for zero silent failures. This is a Phase 1 requirement — quest resolution is the ONE authoritative action and must not silently fail if the Inngest event is lost.

### Supervisor Graph Generalization

The existing `supervisor.py` compiles a single fixed graph. For 30 agents across 7 departments, the supervisor must become parameterized by worker spec, or each department needs its own compiled graph.

Phase 1 uses synthetic/demo state transitions while the supervisor is generalized.

## Tech Stack

```
Frontend (office-dashboard/):
  ├── Next.js 14 (App Router)
  ├── React Three Fiber (3D renderer)
  ├── Drei (R3F helpers)
  ├── Three.js (engine)
  ├── Zustand (state management)
  └── Tailwind CSS (HTML overlay panels)

Backend:
  ├── Next.js API routes (quest resolve, memo generate)
  ├── Supabase (tables + Realtime + Auth)
  └── Inngest (event bus + cron)

Agent Runtime (existing + new emitter):
  ├── Python LangGraph harness
  ├── InngestEventEmitter (new)
  └── Inngest TypeScript functions

Build Acceleration:
  └── Droid CLI
```

## Error Handling & Degradation

### Connection Health
- Green dot (live), yellow (reconnecting), red (disconnected)
- Supabase Realtime auto-reconnects with exponential backoff
- On reconnect, full state re-fetched from `agent_runtime_state`

### Quest Resolution Safety
- Supabase auth required (internal SSO)
- Optimistic locking: `status = 'pending'` in UPDATE WHERE
- Rate limiting: 1 resolution per quest per second

### Inngest Function Resilience
- If `agent_id` is not in `agent_registry` (FK violation), the function logs a warning and skips — does not crash. This handles the case where a new worker spec is deployed before the registry is seeded.
- Inngest auto-retry (3x) handles transient Supabase write failures.
- After 3 retries, failed events go to Inngest DLQ for manual inspection.

### 3D Rendering Fallback
- WebGL context loss → 2D table view of agent states
- `<Canvas>` in `<ErrorBoundary>`
- Failed GLTF models → colored cubes with name labels

## Phase 1 Scope

### Goal

Ship a trustworthy internal read model with a compelling 3D shell, not a full command center.

### Phase 1 Includes

- Orbital office view with all rooms + Executive Suite + lobby
- Room fly-in for all departments
- 5 live agents backed by real worker specs (showing real runtime transitions)
- 25 placeholder agents marked `Coming Soon`
- Live `agent_runtime_state` subscription via Supabase Realtime
- Pending/resolved/expired quest log
- Quest auto-expiry via Inngest cron (every 15 min; TTL: 1h high, 2h medium, 4h low urgency)
- Daily memo board (backed by `office_kpi_snapshot`)
- Read-only hallway handoff animation (backed by `agent_handoff_log`)
- One real operator action: `quest_resolve`
- Harness Realtime backup subscription for quest resolution (fallback if Inngest event lost)
- Internal auth + RBAC (viewer/operator/admin)
- Basic connection health indicator
- Simple placeholder geometry fallback for failed GLTF
- PII-safe redacted summaries in all ambient UI
- CEO LTV:CAC dial as placeholder ("Awaiting data") until KPI computation exists
- Canonical roster source file (`knowledge/office-roster.yaml`) + seed script for `agent_registry`
- **Full 30-agent workforce:** All agents have worker specs, wired into harness via RunTaskRequest + director-as-dispatcher
- **Three execution loops:** Operational (event-driven), Management (dept sweeps), Executive (summary + exception)
- **"Good morning" briefing:** CEO agent output displayed as splash card on first daily load
- **Agent activity sparklines:** 24h activity bars in sidebar (backed by `agent_state_history` table)
- **Deal breaker → quest auto-link:** Inngest function creates quest for Head of Product when deal breaker logged
- **Keyboard shortcuts:** 0-7 for rooms, Q/M/D for overlays, ESC to exit
- **Voice call live pulse:** Phone icon pulses in lobby when a call is in progress

### Phase 1 Excludes

- Authoritative dispatch (logged as intent only)
- Authoritative handoff override (logged as intent only)
- Offline action queue
- Mood/pose variants beyond minimal state animation
- Hallway heat map
- Urgency pacing behavior
- Structured meetings (Phase 2)
- Ambient audio (Phase 2)
- Electron wrapper (Phase 2)
- Advanced GLTF failure handling beyond simple fallback
- KPI computation pipeline (CEO dial shows placeholder until Phase 2)

### Phase 1 Done Criteria

1. Orbital office renders with all rooms and lobby
2. Room fly-in works for each department and Executive Suite
3. Five mapped live agents show real runtime transitions
4. Remaining agents render as placeholders with `Coming Soon`
5. Quest log shows pending/resolved/expired items from real events
6. Operator can resolve quests and actions are audit logged
7. Quest auto-expiry cron runs and marks stale quests as expired
8. Daily memo board renders from stored memo/KPI snapshot data
9. Handoff animation plays from read-only `agent_handoff_log`
10. Internal RBAC gates access correctly
11. PII-safe redacted summaries are enforced in ambient UI
12. Harness Realtime backup subscription picks up quest resolutions if Inngest event is lost
13. Supabase Realtime publication is configured for all office tables (verified in deploy checklist)

### Phase 2+

| Component | Phase | Description |
|---|---|---|
| Authoritative dispatch + handoff override | 2 | Requires generalized supervisor |
| Structured agent meetings in lobby | 2 | Round-robin LangGraph subgraph |
| Meeting transcript + action items | 2 | Floating sticky notes dispatched to agents |
| Agent mood/pose variants | 2 | 3-4 poses per state |
| Hallway traffic heat map | 2 | Corridor glow scales with handoff frequency |
| Quest urgency timer + pacing | 2 | Countdown, director flash on expiry |
| Achievement toasts | 2 | Milestone notifications |
| Ambient sound design | 2 | Audio tied to agent states |
| Offline action queue | 2 | Queue when disconnected, drain on reconnect |
| Electron desktop wrap | 2 | Always-on window |

## Test Strategy

### Test Pyramid

| Layer | What | Tool | Priority |
|---|---|---|---|
| Unit | Zustand stores: agent state updates, quest resolution, connection health state machine | Vitest | High |
| Unit | InngestEventEmitter (Python): payload construction, feature flag check, graceful failure on timeout/connection error | pytest | High |
| Unit | agent_id mapping: worker_spec.id → office agent_id resolution, unknown spec handling | pytest | High |
| Integration | Inngest functions: event → Supabase upsert (valid agent_id succeeds, unknown agent_id skips gracefully, concurrent upserts resolve) | Inngest dev server + test Supabase | Medium |
| Integration | API routes: quest resolve with optimistic locking (double-resolve returns 409, auth enforcement, audit log written) | Next.js test client | Medium |
| Integration | Supabase Realtime: subscription connects and receives events after table mutation | Supabase test project | Medium |
| Visual | R3F scene renders without crashing, ErrorBoundary fallback triggers on WebGL loss | Storybook + snapshot | Low |
| E2E | Full flow: emit event → agent moves in dashboard (deferred to Phase 2) | Playwright | Phase 2 |

### 2am Friday Confidence Tests

The following tests must pass before shipping:

1. **InngestEventEmitter with Inngest unreachable** → harness pipeline completes normally, event is logged as lost
2. **Quest resolve with concurrent operators** → first resolve succeeds, second gets 409, audit log has both attempts
3. **Inngest function with unknown agent_id** → function logs warning and completes (no crash, no DLQ)
4. **Supabase Realtime subscription after token refresh** → dashboard re-subscribes and receives events

## Observability

### Minimum Counters

| Metric | Type | What it tells you |
|---|---|---|
| `office.events.emitted` | Counter | Pipeline is alive — events are flowing from harness to Inngest |
| `office.events.failed` | Counter | Events are being lost — emitter hitting errors |
| `office.quests.resolved` | Counter | The ONE write path is working |
| `office.quests.expired` | Counter | Auto-expiry cron is running |
| `office.state_changes` | Counter | Agents are doing something (not all idle) |
| `office.realtime.connected` | Gauge (boolean) | Dashboard is receiving Realtime events |

### Structured Logging

Log at each layer with structured fields:

| Layer | Log on | Fields |
|---|---|---|
| InngestEventEmitter (Python) | emit success, emit failure, feature flag check | `agent_id`, `event_type`, `workspace_id`, `error` (if failed) |
| Inngest functions (TypeScript) | upsert success, FK skip, retry, DLQ | `agent_id`, `event_name`, `attempt`, `error` |
| API routes (Next.js) | quest resolve success, 409 conflict, 403 denied | `quest_id`, `user_id`, `action`, `status_code` |
| Realtime subscription (client) | connect, disconnect, reconnect, token refresh | `tables`, `connection_state`, `stale_seconds` |

### Post-Deploy Verification Checklist (first 5 minutes)

1. Open dashboard — does the connection health indicator show green?
2. Check Inngest dashboard — are `calllock/agent.state.changed` events appearing?
3. Trigger a test LangGraph run — does the agent move from idle to execution in the 3D view?
4. Resolve a test quest — does the agent move from policy-gate to idle?
5. Check `command_audit_log` — is the quest resolution logged?

## Runtime Split ADR

**Decision:** The 3D office dashboard introduces a Next.js (TypeScript) surface area in the `office-dashboard/` directory.

**Context:** The dashboard is a standalone visualization and control surface. It is not part of the core orchestration runtime. The Python harness remains the sole orchestration layer. TypeScript is used for R3F rendering, Next.js API routes, and Realtime subscription management.

**Consequence:** Bounded expansion. TypeScript does not leak into the harness, knowledge system, or compliance graph.

## Inngest Event Naming Convention ADR

**Decision:** All new events use the `calllock/` prefix (e.g., `calllock/agent.state.changed`).

**Context:** Existing events use no namespace prefix (e.g., `ProcessCallPayload`). The namespaced convention should be adopted going forward.

**Consequence:** Existing event names should be backfilled for consistency in a future migration.

## Resolved Design Questions

| # | Question | Decision | Rationale |
|---|---|---|---|
| 1 | Asset creation method | AI-generated (Meshy/Tripo), polish in Blender if needed | At 200-500 poly with flat shading, AI tools produce adequate quality in minutes. Generate base template, swap colors/accessories per agent. |
| 2 | Sound design | Yes, but Phase 2 | Subtle audio makes the office feel alive. Ship visual layer first. |
| 3 | Multi-user presence | Not needed now, architecturally unblocked | Founder is primary user. Supabase Realtime supports multiple subscribers. Add shared cursors when team reaches 3+. |
| 4 | Content & Copy agent | Added as 6th Growth Marketing agent (`growth-content`) | Matches CRO + Content & Copy diagram. Clean separation: CRO optimizes funnels, Content & Copy creates the copy/emails/social. |
| 5 | Deal Breaker Ledger | Physical cork board in Central Lobby | Growth writes, Product reads. Red/green card ratio visible from orbital view. Backed by `deal_breaker` table. |
| 6 | Sales room | Full room, even with 1 agent | Lean by design. Preserves future flexibility. Keeps sales/marketing boundary clear. |
| 7 | Tenancy model | Workspace, not tenant | Office is one internal HQ. Customer context attaches to work, not to the office itself. |
| 8 | Control plane scope | Read model + quest resolve only in Phase 1 | Dispatch and override are intents until supervisor is generalized. |
| 9 | PII in ambient view | Redacted by default | No raw transcripts, phone numbers, or caller identity in speech bubbles, hover cards, or lobby board. |
| 10 | LTV:CAC dial | Rolling 90-day blended snapshot, refreshed every 15 min | Shows value + freshness label. Believable, not magical. |
| 11 | Phase 1 scope | 10 done criteria, not 22 | Credible first release. Ship a read model, not a full command center. |
| 12 | Security model | Internal RBAC, not tenant RLS | Office is not a tenant surface. Workspace-scoped access control. |
| 13 | workspace_id source | CallLock's own tenant_id from tenants table | "CallLock is its own tenant for internal ops." Zero new tables. |
| 14 | agent_id source | worker_spec.id + small mapping config | Emitter reads the executing worker spec. 5 name mismatches handled by config. |
| 15 | Quest resolution backup | Harness Realtime subscription on quest table | Phase 1 requirement. If Inngest event lost, harness picks up resolution via Realtime. |
| 16 | Quest auto-expiry | Inngest cron every 15 min, TTL by urgency | High=1h, Medium=2h, Low=4h. Expired quests remain manually resolvable. |
| 17 | CEO KPI dial Phase 1 | Placeholder "Awaiting data" | KPI computation deferred to Phase 2. Dial structure is ready. |
| 18 | Roster source of truth | knowledge/office-roster.yaml + seed script | Single source. Markdown tables derived from YAML, not the other way around. |

## Changelog

| Date | Change |
|---|---|
| 2026-03-15 | v1: Original 24-agent, 5-department design |
| 2026-03-17 | v2: Restructured to mirror corporate hierarchy. Added Executive Suite (CEO, CPO, CTO, COO). Expanded Product to 7 agents. Collapsed Sales to 1. Added CS pods. Removed redundant agents. Added Content & Copy. 30 agents across 7 departments. Voice call ambient activity. LTV:CAC North Star. |
| 2026-03-17 | v2.1: Workspace architecture tightening. Replaced tenant model with workspace model. Split agent_registry (static) from agent_runtime_state (live). Added deal_breaker, agent_handoff_log, office_kpi_snapshot tables. Clarified control plane: quest resolve is authoritative, dispatch/override are Phase 1 intents. Added PII redaction rules. Defined LTV:CAC dial as rolling 90-day snapshot with freshness. Cut Phase 1 to 10 credible done criteria. Fixed roster math (4 execs + 5 directors + 21 workers). Replaced tenant RLS with internal RBAC. Updated feature flag to workspace-level. |
| 2026-03-17 | v2.3: Full workforce expansion (SCOPE EXPANSION). All 30 agents get worker specs and real tasks. Added Workforce Architecture section: RunTaskRequest schema, director-as-dispatcher pattern (reusing existing supervisor.py + dispatch.py seams), three execution loops (operational/management/executive), three execution modes (deterministic/light_llm/heavy_llm), scheduling constraints with Inngest concurrency controls, quest-as-approval-projection. Agent Task Matrix for all 30 agents. Consolidated crons to 13 via department-level sweeps. Added agent_state_history table for sparklines. Phase 1 delights: "Good morning" briefing, activity sparklines, deal breaker → quest auto-link, keyboard shortcuts, voice call live pulse. Staged department rollout (Engineering first). |
| 2026-03-17 | v2.2: CEO mega-review (HOLD SCOPE). Applied 12 review findings: (1) workspace_id = CallLock tenant_id, (2) agent_id sourced from worker_spec.id with mapping config, (3) Supabase Realtime publication setup required in migrations, (4) InngestEventEmitter must log+continue on all failures, (5) Inngest functions handle FK violations gracefully, (6) harness Realtime backup subscription for quest resolution added to Phase 1, (7) quest auto-expiry via Inngest cron added to Phase 1, (8) CEO dial ships as "Awaiting data" placeholder, (9) canonical roster YAML + seed script, (10) handoff_log index added, (11) Test Strategy section added (pyramid + 2am confidence tests), (12) Observability section added (6 counters + structured logging + deploy checklist). Phase 1 done criteria expanded from 10 to 13. |
