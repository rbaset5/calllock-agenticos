# CallLock AgentOS Architecture

> Canonical architecture document. Replaces `2026-03-12-calllock-agentos-architecture-design.md`.
> Last updated: 2026-03-17.

---

## Part I. What CallLock Is

CallLock operates as a **two-layer system**.

### Product Layer (customer-facing)

For each customer, CallLock provides:

- A **voice AI agent** that handles inbound calls
- A **CallLock App** that displays transcripts, call outcomes, bookings, ROI, account state, onboarding information, and support-related information

This is the product CallLock sells and delivers.

### Internal Operations Layer (CallLock-facing)

CallLock's team primarily uses the **3D Command Center**, which serves as the internal visualization, coordination, and selective execution interface for the AI workforce that builds, supports, grows, and improves the product across all customers.

The 3D Command Center is not part of the customer product surface.

### Boundary Test

A single customer event may affect both layers. A missed call may appear in the CallLock App as a transcript and booked job, while also triggering internal activity in the 3D Command Center if customer success, product, analytics, support, or growth systems need to react. This does not blur the boundary — the same business event produces both customer-facing and internal-facing views through cleanly separated read models.

**If the user is a CallLock customer**, they see:

- Their calls, transcripts, booked jobs, settings, ROI, onboarding and support information
- Their CallLock App

They never see:

- CallLock's internal product organization, growth team, AI workforce, quest log, deal-breaker board, or 3D Command Center

**If the user is CallLock internal**, they primarily use the 3D Command Center.

### Design Principles

- The product is the voice AI agent plus the CallLock App delivered per customer.
- The 3D Command Center is an internal CallLock interface, not part of the customer-facing product.
- Real capability must be distinguished from aspirational personas: registered agents, implemented workers, and synthetic visual activity are not the same thing.
- Customer events may feed both customer-facing and internal-facing read models, but those surfaces must remain cleanly separated.
- The internal system stays tied to business outcomes: product quality, customer retention, growth efficiency, and LTV:CAC.

---

## Part II. System Model

Underneath both layers, the platform is organized into **three planes**:

| Plane | Role |
|-------|------|
| **Control plane** | Decides, plans, routes, supervises, and governs work |
| **Data plane** | Executes actions in the world — calls, transcripts, bookings, CRM writes, email, SMS |
| **Learning plane** | Evaluates outcomes and improves prompts, policies, memory, and deployment decisions over time |

Across those planes, the system is described by **eight layers**:

| # | Layer | Primary Plane | What It Owns |
|---|-------|--------------|--------------|
| 1 | **Cognition** | Control | LLM reasoning, model gateway, confidence scoring, prompt execution |
| 2 | **Knowledge & Memory** | Control + Data | Knowledge graphs, worker specs, industry packs, context assembly, retrieval, caching, tenant-scoped memory |
| 3 | **Work Graph** | Control | Task decomposition, dependency tracking, bead management, replanning |
| 4 | **Coordination** | Control | Multi-agent routing, handoffs, Agent Mail, human escalation, supervisor logic |
| 5 | **Execution** | Data | Tool invocation, sandboxed execution, browser automation, external API calls, artifact persistence |
| 6 | **Safety & Control** | Control + Data | Policy gate, V&V pipeline, circuit breakers, blast radius limits, kill switches, approval gates |
| 7 | **Operations** | Data + Learning | Deployment, delivery pipelines, tenant lifecycle, onboarding, health monitoring, observability, tracing |
| 8 | **Learning & Improvement** | Learning | Evaluation, experiment isolation, improvement lab, promotion pipeline, feedback loops |

### How the Three Planes Map to the Eight Layers

```
  CONTROL PLANE                    DATA PLANE                    LEARNING PLANE
  ─────────────                    ──────────                    ──────────────
  L1 Cognition                     L5 Execution                  L8 Learning & Improvement
  L2 Knowledge & Memory ◄──────── L2 Knowledge & Memory
  L3 Work Graph                    L7 Operations ◄──────────── L7 Operations
  L4 Coordination                  L6 Safety & Control
  L6 Safety & Control
```

Some layers span planes. Knowledge & Memory spans control (context assembly, retrieval) and data (cached reads, graph persistence). Safety & Control spans control (policy decisions) and data (enforcement, blocking). Operations spans data (deployments, tenant lifecycle) and learning (observability feeding improvement).

### Role of the 3D Command Center

The 3D Command Center is the **internal operating interface over the control plane**, supported by read models from the data and learning planes and a limited set of explicit write actions.

Its capabilities:

- Display live internal state (agent presence, department structure, system health)
- Coordinate agents and handoffs
- Surface priorities, deal-breakers, and escalations
- Trigger approved workflows and operator actions
- Support overrides, dispatch, intervention, and recovery
- Act as the internal command layer for operating the company

The authority distinction:

- The **3D Command Center is authoritative for a bounded set of internal operator actions and their UI-facing control objects**: quests, operator directives, deal-breaker board entries, approval decisions, and dispatch commands. These are objects the Command Center creates and owns.
- **Most runtime state is projected, not owned.** Agent registry, runtime state, handoffs, execution history, and coordination state are produced by the harness and event pipeline. The Command Center consumes these as read models. It can trigger actions against them (pause an agent, escalate a handoff), but the source of truth remains the harness/event system.
- The **underlying product systems remain authoritative for product-domain records**: calls, transcripts, bookings, customer accounts, CRM state, billing records.

#### Founder Cockpit View

The Founder Cockpit is a **privileged mode within the 3D Command Center**, not a separate system. It adds:

- Strategic overrides and approval authority
- Cross-department visibility
- Portfolio KPIs and industry-by-industry performance
- Budget and margin oversight
- Experiment oversight (Improvement Lab visibility)
- Release oversight (Safe Delivery visibility)
- Kill switches and pause controls
- Cross-tenant administrative override — **available only in Cockpit admin mode**, not the general 3D Command Center surface. Normal internal views are redacted and role-scoped; only authenticated Cockpit admin mode can cross tenant boundaries, with audit logging on every cross-tenant access.

Design principle: the Cockpit observes and approves. It does not perform routine delivery work. Workers propose; the Cockpit decides.

### Source-of-Truth Matrix

| Object | Source of Truth |
|--------|---------------|
| Calls / transcripts / bookings | Product systems (Supabase, Retell, Cal.com) |
| Tenant config | Supabase |
| Industry pack definitions | Repo knowledge layer (`knowledge/industry-packs/`) |
| Worker specs | Repo knowledge layer (`knowledge/worker-specs/`) |
| Compliance runtime rules | Supabase (database-backed, authoritative at runtime) |
| Compliance intent / documentation | Repo knowledge layer (markdown, authoring-facing) |
| Bead graph | br (bead storage) |
| Agent threads / reservations | Agent Mail |
| Agent runtime state / execution history | Harness + event pipeline (projected to Command Center) |
| Traces / eval runs | LangSmith |
| Quests / feature tracks / epics | Linear (projected to Command Center) |
| Internal directives / approvals | 3D Command Center |

---

## Part III. The Flywheel (Internal Engineering Method)

> **Scope note:** The Flywheel describes how CallLock is *built and improved* — it is the internal engineering operating method, not the runtime architecture of the product. Plan space, bead space, Agent Mail, `br`, `bv`, single-branch git, fungible agents, and staggered starts are engineering process concerns. They govern how the team (human + AI) develops and ships changes to the system described in Parts I, II, and IV–XII. The Flywheel does not run in production; production runs the eight-layer architecture.

The Flywheel is the **inner execution engine** for planning, building, and improving the system. It maps primarily to **L3 Work Graph and L4 Coordination**, with operational touchpoints in L5 Execution and L1 Cognition. The center of gravity is work packaging and coordination, not execution itself. The Flywheel governs development, not customer-facing runtime.

### Three Reasoning Spaces

| Space | Artifact | Primary Questions | Cost of Mistakes |
|-------|----------|-------------------|------------------|
| **Plan space** | Markdown design document | What should the system be? | 1x (pure reasoning) |
| **Bead space** | Task graph with dependencies | How to package work for execution? | 5x (orchestration rewrites) |
| **Code space** | Source files and tests | Implementation and verification | 25x (implementation + cleanup) |

The principle: catch the bug where it's cheapest. Inject architectural mistakes at the plan layer where they cost 1x to fix, not in code space where they cost 25x.

### Execution Loop

1. **Intent definition** — articulate project goals, user workflows, strategic direction
2. **Multi-model planning** — generate competing plans from frontier models, synthesize into a hybrid, refine 4-5 rounds
3. **Plan-to-beads conversion** — transform the plan into self-contained work units (beads) carrying context, dependencies, testing obligations, and rationale
4. **Bead polishing** — 4-6+ rounds of deduplication, dependency strengthening, test completeness, and coverage verification until convergence
5. **Swarm coordination launch** — deploy fungible agents coordinated through Agent Mail (point-to-point communication), br (bead storage and status), and bv (graph-theory routing)
6. **Implementation & tending** — agents work in parallel on beads; human monitors on ~10-30 minute cadence, handles compactions and surprises
7. **Review & hardening** — per-bead self-reviews, cross-agent reviews, comprehensive test creation, UI/UX polish

### Coordination Triangle

Three tools form an inseparable system:

| Tool | Role |
|------|------|
| **Beads (br)** | Durable, localized issue state with dependency graph |
| **Agent Mail** | High-bandwidth negotiation layer with file reservations and advisory locks |
| **bv (Beads Viewer)** | Graph-theory routing using PageRank, betweenness centrality, HITS, critical path |

Remove any side and the swarm loses coordination determinism.

### Planning Dominance

The methodology inverts traditional development: **~85% of effort is front-loaded into planning, ~15% into implementation**. This compounds because:

- Markdown plans fit entirely in context windows (unlike codebases)
- Models reason holistically about entire systems at once
- Each planning improvement amortizes across every downstream bead and code change
- Without front-loaded planning, agents improvise architecture from narrow local windows, producing placeholder abstractions, contradictory assumptions, and compatibility shims

### Agent Architecture

- **Fungible agents** — every agent is a generalist; no specialized roles, no ringleader coordinator
- **Single-branch git** — all agents commit to main; no feature branches, no worktrees
- **File reservations** — advisory locks with TTL expiry via Agent Mail prevent conflicts
- **Staggered starts** — 30+ seconds apart to avoid thundering herd on the same frontier
- **Recovery** — when an agent crashes, the bead remains `in_progress`; any other agent resumes it

### Mental Model

These conceptual frameworks are complementary, not competing:

- The **Flywheel** is the internal engineering method for planning, building, and shipping changes
- The **15 design concepts** (Part IV) are the runtime safety and reliability guardrails
- The **8-layer architecture** (Part II) is the full capability map of the production system

The Flywheel governs how the system is developed. The design concepts and eight layers govern how the system runs. The Flywheel feeds the architecture; it does not run inside it at customer-facing runtime.

---

## Part IV. Design Concepts

The 15 design concepts are not another stack. They are the **runtime guardrails and control patterns** that make the eight-layer architecture safe, inspectable, and operable.

### Concept Definitions

**1. Agent Circuit Breaker** — Automatically disables an agent or workflow path after repeated failures, preventing cascading damage. When an agent's error rate exceeds a threshold within a time window, the circuit opens: new requests are rejected immediately rather than attempted. After a cooldown period, the circuit half-opens to test recovery. Closed → Open → Half-Open → Closed.

**2. Blast Radius Limiter** — Constrains the scope of any single agent action so that a failure or misbehavior cannot affect more than one tenant, one workflow, or one bounded surface at a time. Implemented through tenant isolation (RLS + app-layer filtering), per-tenant resource budgets, and scoped tool grants.

**3. Orchestrator vs Choreography** — Explicit architectural choice for how multi-step work is coordinated. Orchestrator pattern: a central supervisor routes work to specialists. Choreography pattern: agents react to events independently. CallLock uses orchestrator (LangGraph supervisor) for structured workflows and choreography (Inngest events) for loose coupling between services.

**4. Tool Invocation Timeout** — Every external tool call carries a timeout. If a tool (Cal.com booking, Twilio SMS, browser automation, sandboxed execution) does not respond within its budget, the call is aborted, logged, and escalated or retried per policy. No tool call runs unbounded.

**5. Confidence Threshold Gate** — LLM outputs below a configured confidence threshold are not treated as actionable. Low-confidence outputs trigger: retry with enriched context, escalation to human review, or graceful degradation. The threshold is tunable per action type (higher for booking/SMS, lower for internal analysis).

**6. Context Window Checkpointing** — After context compaction, agents must re-read their operating contract (AGENTS.md, worker spec, active task context). Checkpointing ensures that compaction does not cause agents to forget safety constraints, tool permissions, or task state. The harness enforces re-read after every compaction event.

**7. Idempotent Tool Calls** — All tool invocations that trigger external side effects (bookings, SMS alerts, email, publish actions) carry idempotency keys. A retried or duplicated job produces the same result, not a duplicate booking or duplicate emergency alert. Inngest supports idempotency keys natively.

**8. Dead Letter Queue for Agents** — Failed agent work that cannot be retried or recovered is routed to a dead letter queue rather than silently dropped. DLQ entries carry full context (agent, tenant, job, error, input state) and are surfaced in the 3D Command Center for human triage.

**9. LLM Gateway Pattern** — All LLM calls route through a single gateway (LiteLLM) that provides: model routing (Claude Sonnet 4.6 primary, Ollama for triage), per-tenant cost tracking, budget enforcement, rate limiting, fallback logic, and observability. No agent calls an LLM directly.

**10. Semantic Caching** — Repeated or near-duplicate queries are served from cache rather than invoking the LLM. Cache keys are tenant-namespaced. Cache invalidation is deploy-triggered for policy/compliance content (never TTL-based for safety-critical data). Reduces cost and latency for hot-path operations.

**11. Human Escalation Protocol** — Defined triggers, channels, and SLAs for routing work to humans. Escalation fires when: confidence is below threshold, policy gate blocks with no automated resolution, V&V fails after retry, budget limits are reached, or circuit breakers open. Escalations surface in the 3D Command Center with full context.

**12. Multi-Agent State Sync** — When multiple agents operate on shared state (tenant data, bead graph, file surfaces), synchronization is maintained through: Agent Mail reservations, advisory file locks with TTL, pre-commit guards blocking reserved-file commits, and Supabase realtime for shared database state.

**13. Replanning Loop** — When implementation reveals that the current plan is wrong or incomplete, work stops and the system re-enters plan space. The replanning trigger fires when: bead completion rate drops below threshold, agents report blocking contradictions, or the human operator identifies strategic drift. Replanning revises the bead graph before resuming execution.

**14. Canary Agent Deployment** — New agent configurations, worker spec changes, or prompt updates are deployed to a single tenant or synthetic test environment before rolling out broadly. The canary runs under full observability. If eval metrics degrade, the change is rolled back before wider deployment.

**15. Agentic Observability Tracing** — Every agent action, tool call, LLM invocation, policy gate decision, and V&V check is traced end-to-end. Traces carry: agent ID, tenant ID, job ID, action type, input/output summaries, latency, cost, and outcome. Traces flow to LangSmith (with PII redaction) and feed the learning plane.

### Crosswalk: Design Concepts → System Layers

| Layer | Design Concepts |
|-------|----------------|
| **L1 Cognition** | Confidence Threshold Gate |
| **L2 Knowledge & Memory** | Context Window Checkpointing, Semantic Caching |
| **L3 Work Graph** | Replanning Loop, Orchestrator vs Choreography |
| **L4 Coordination** | Multi-Agent State Sync, Human Escalation Protocol |
| **L5 Execution** | LLM Gateway Pattern, Tool Invocation Timeout, Idempotent Tool Calls |
| **L6 Safety & Control** | Agent Circuit Breaker, Blast Radius Limiter, Human Escalation Protocol |
| **L7 Operations** | Dead Letter Queue, Canary Agent Deployment, Agentic Observability Tracing |
| **L8 Learning & Improvement** | Fed by: Agentic Observability Tracing, Dead Letter Queue, Replanning Loop, eval outputs |

Human Escalation Protocol appears in both L4 (coordination trigger) and L6 (safety enforcement). This is intentional — escalation is both a coordination mechanism and a safety boundary.

---

## Part V. Product Surface

The product layer delivers per-customer instances of: voice AI agent + CallLock App.

### Current Production System (March 2026)

| Component | Stack | Status |
|-----------|-------|--------|
| Voice agent | Retell AI V10 (10-state FSM, LLM-driven transitions, GPT-4o) | **Live** |
| Backend | Node.js / TypeScript / Express (V2), deployed on Render | **Live** |
| Database | Supabase (PostgreSQL + realtime) | **Live** |
| CallLock App | Next.js 16 / React 19, deployed on Vercel | **Live** |
| Booking | Cal.com integration | **Live** |
| Alerts | Twilio SMS (emergency + sales lead) | **Live** |
| Industry logic | HVAC-only (117 smart tags, 3 emergency tiers, service taxonomy) | **Hardcoded in V2** |
| Multi-tenant (voice) | Retell agent metadata routing (agent ID / phone number) | **Partial** |
| Multi-tenant (app) | Not yet | **Not started** |
| Tests | 31+ Vitest integration tests (V2), unit tests (CallLock App) | **Partial** |

### Shared Product Core

The industry-agnostic product that every trade and every client uses.

Contains:

- Voice runtime (Retell AI)
- Web application (CallLock App — Next.js 16)
- Backend API (Express V2)
- Auth & permissions
- Billing
- Notifications (Twilio SMS)
- Logging (Pino)
- Booking (Cal.com)
- Reporting shell
- APIs
- Shared workflow framework

Design principle: the core stays trade-neutral. Everything above it (harness, delivery, command center) makes it safe and smart. Everything below it (industry packs, tenant configs) makes it specific.

### Industry Pack Layer

The abstraction for serving multiple trades from one platform.

Current packs: HVAC. Future: Plumbing, Rooter, Electrical, Roofing, Pest.

Each pack contains:

- Terminology and service taxonomy
- Urgency logic and emergency tiers
- Booking logic and constraints
- Scripts and objection handling
- Follow-up patterns
- Trade-specific reporting logic
- Trade-specific compliance nuances

Pack directory structure:

```
knowledge/industry-packs/
  hvac/
    pack.yaml              # Pack manifest: name, version, trade, dependencies
    taxonomy.yaml          # Service types, categories, smart tags
    urgency.yaml           # Emergency tiers, escalation rules, priority logic
    compliance.yaml        # Trade-specific disclosures, forbidden claims, licensing
    scripts/               # Call scripts, objection handling, follow-up templates
    booking-rules.yaml     # Trade-specific booking logic and constraints
    reporting.yaml         # Trade-specific metrics and report templates
    voice/                 # Voice agent configurations
  plumbing/
    ...
```

Pack manifest schema:

```yaml
name: "hvac"
version: "1.0.0"
trade: "HVAC"
description: "Heating, ventilation, and air conditioning"
extends: []                # Other packs this one builds on
requires_compliance: true
smart_tag_count: 117       # For HVAC, migrated from V2
```

Runtime loading: the harness reads `tenant_config.industry_pack_id`, resolves the pack directory, and includes relevant sections in context assembly. Pack files are cached in Redis and invalidated on deploy.

Design principle: industry packs are configuration, knowledge, and bounded workflow variants — not separate codebases. Adding a new trade means adding a new pack, not forking the product.

### Tenant Configuration & Isolation

Each client gets a private config and namespace within the platform.

**Instance formula:**

> `shared product core` + `one industry pack` + `one tenant config` = client instance

Per-tenant configuration:

| Category | Fields |
|----------|--------|
| Identity | `tenant_id`, `tenant_name`, `industry_pack_id`, brands served |
| Operations | Service area, pricing rules, hours, offers/promotions |
| Voice/Tone | Tone/brand instructions, disclosures |
| Governance | Allowed tools, escalation contacts |
| Isolation | Memory scope, trace namespace, eval namespace |

**Data isolation — defense in depth:**

1. **Database-level tenant context** — The harness uses privileged database access (service role key), but every tenant-scoped operation must enter an explicit tenant context via `set_config('app.current_tenant', tenant_id, true)` before executing queries. Database policies enforce tenant boundaries regardless of connection privilege level.
2. **Application-layer filtering** — All queries include explicit `WHERE tenant_id = ?` as a secondary safeguard. This catches cases where database policies are misconfigured or bypassed.

Cross-tenant data access is never permitted at the application layer. The only exception is the Founder Cockpit's cross-tenant administrative view, which uses a dedicated admin role with explicit RLS bypass and audit logging.

| Scope | Isolation Mechanism |
|-------|-------------------|
| Database (Supabase) | RLS policies + app-layer `tenant_id` filtering |
| Cache (Redis) | Tenant-namespaced cache keys (*Semantic Caching*) |
| Traces (LangSmith) | Tenant-scoped trace tags and retention (*Agentic Observability Tracing*) |
| Evals (LangSmith) | Tenant-scoped eval datasets and experiments |
| Artifacts | `tenant_id` metadata on all artifacts |
| Knowledge graphs | Shared graphs are read-only for tenants; customer insight graphs are tenant-scoped |

Design principle: tenants are lightweight configurations with isolated namespaces, not bespoke systems. If persistent memory is added, it must be scoped per tenant to prevent cross-tenant leakage (*Blast Radius Limiter*).

### Evolution Map

```
  CURRENT PRODUCTION              TARGET LAYER                         ACTION
  ──────────────────              ────────────                         ──────
  Retell AI V10 (voice)           L5 Execution (voice runtime)         KEEP
  Express V2 (backend)            L5 Execution (product core)          EVOLVE — becomes trade-neutral core
  Supabase                        L2 Knowledge & Memory (app database) KEEP
  Next.js CallLock App            L5 Execution (web app)               KEEP — evolves with core
  Cal.com                         L5 Execution (integration)           KEEP
  Twilio                          L5 Execution (integration)           KEEP
  Pino logging                    L7 Operations (observability)        ADD ALONGSIDE — Pino continues locally
  HVAC smart tags (hardcoded)     L2 Knowledge & Memory (industry pack) EXTRACT from V2 into pack format
  Emergency tiers (hardcoded)     L6 Safety & Control (compliance)     EXTRACT from V2 into compliance graph
  Retell webhook auth             L6 Safety & Control (policy gate)    CARRY FORWARD
  (nothing)                       L1 Cognition (agent harness)         BUILD NEW
  (nothing)                       L3 Work Graph (delegation/jobs)      BUILD NEW
  (nothing)                       L2 Knowledge & Memory (graphs)       BUILD NEW
  (nothing)                       L4 Coordination (workforce)          BUILD NEW
  (nothing)                       L8 Learning & Improvement (lab)      BUILD NEW
  (nothing)                       3D Command Center                    BUILD NEW
```

### What This Spec Does NOT Replace

- Retell AI — stays as the voice runtime
- Supabase — stays as the application database
- Cal.com — stays as the booking provider
- Twilio — stays as the alert provider
- Express V2 — evolves into part of the product core, not replaced
- Existing Vitest suite — carries forward, augmented by LangSmith evals

---

## Part VI. Internal Operating Surface

### 3D Command Center

The 3D Command Center is the primary internal interface through which CallLock visualizes, coordinates, and selectively executes work across its AI workforce.

**Objects the Command Center owns** (creates and is authoritative for):

- Quests and operator directives
- Deal-breaker board entries
- Approval decisions and dispatch commands

**State the Command Center projects** (consumes as read models from harness/event pipeline):

- Agent presence and department structure
- Work graph / bead status visibility
- Escalation queue
- System health metrics
- Customer-by-customer operational state
- Internal execution history

The Command Center can trigger actions against projected state (pause an agent, escalate a handoff, initiate a workflow), but the source of truth for that state remains the harness and event pipeline.

The Command Center may display both real runtime activity and synthetic visualization layers (e.g., projected office presence for planned-but-unimplemented roles), and **these must always be visually distinguishable**. Users must never confuse a synthetic visual shell with an implemented, running capability.

The **Founder Cockpit** is a privileged view within the Command Center that adds: strategic overrides, approval authority, cross-department visibility, high-level KPIs, and intervention controls.

### Internal Workforce

Internal workers are specialist workflows/subgraphs, not personalities.

#### Roster vs Live Runtime

The system distinguishes three tiers of workforce presence. These are not interchangeable:

| Tier | Definition | Count (current) | What It Means |
|------|-----------|-----------------|---------------|
| **Implemented live workers** | Worker spec exists, eval suite passes, harness can dispatch work to this worker in production | 0 (pre-Phase 2) | Real runtime capability. The worker does actual work. |
| **Registered workforce roster** | Worker spec authored in `knowledge/worker-specs/`, CI-validated, but not yet activated (no eval coverage, no harness wiring) | 5 | Designed and scoped. Ready to implement. Not yet running. |
| **Projected office presence** | Visual representation in the 3D Command Center — may represent a registered worker, a planned future role, or a department placeholder | Up to 30+ | UI/visualization layer only. No runtime authority. A projected agent with no registered spec and no live implementation is a visual shell, not a worker. |

This distinction matters because the 3D Command Center can display all three tiers, but only implemented live workers perform real work. The Command Center must visually distinguish these tiers so that internal users never confuse a projected office presence with an implemented capability.

**Rules for tier transitions:**

- Projected → Registered: author a worker spec that passes CI validation
- Registered → Implemented: pass minimum eval suite, wire into harness, deploy through Safe Delivery
- No tier may be skipped. A projected agent cannot become implemented without passing through registered.

#### Current Registered Workers

| Worker | Mission |
|--------|---------|
| Product Manager | Prioritization, roadmap decisions, feature specs |
| Engineer | Implementation, code quality, technical decisions |
| Designer | UX/UI decisions, design system |
| Product Marketer | Positioning, messaging, go-to-market |
| Customer Analyst | Call patterns, churn signals, satisfaction insights |

**Supervisor pattern:** The supervisor is a harness-level routing construct, not a sixth worker. It is the top-level LangGraph graph that receives tasks, determines which specialists to invoke, and routes results. It does not have a worker spec, mission, or personality — it is orchestration logic (*Orchestrator vs Choreography*).

**Rules:**

- Each worker is defined by a Standard Worker Schema spec in `knowledge/worker-specs/`
- Workers may share skill packs but may not share primary mission ownership
- No new worker without a clear non-overlapping mission
- No worker promoted from spec to active use without eval coverage for its `success_metrics`
- Start with 5 registered. Earn more through measured improvement, not role imagination.
- The 3D Command Center may project additional roles for visualization, but projected presence confers no runtime authority.

### Standard Worker Schema

Every internal worker is defined by a YAML spec:

```yaml
# knowledge/worker-specs/{worker-name}.yaml

# --- Required ---
mission: ""
scope: ""
execution_scope: ""    # "internal" or "tenant-bound"
inputs: []
outputs: []
tools_allowed: []
success_metrics: []
approval_boundaries: [] # List of actions, or "inherits_global_policy"

# --- Recommended ---
job_creation: ""       # "sync_only" | "async_allowed" | "scheduled_allowed" | "all"

# --- Optional ---
escalation_rules: ""
linked_skill_packs: []
```

Required fields must contain a real value or an explicit debt marker (`not_yet_defined`); silent omission is not allowed.

Anti-patterns: no placeholder prose, no personality descriptions, no duplicate/overlapping specialists until evals prove differentiation helps.

### Worker Specs vs Skill Packs

- **Worker spec** = who this worker is and how it operates (identity + authority)
- **Skill pack** = methods and frameworks this worker can invoke (capability)

This repo is the canonical source of truth for all worker specs and skill packs. Upstream repos (`agency-agents`, `phuryn-pm-skills`) are reference inputs, never runtime dependencies.

### Delegation & Jobs

Three delegation modes:

| Mode | Behavior | Implementation |
|------|----------|---------------|
| **Sync** | Do this and wait | LangGraph in-graph/subgraph |
| **Async** | Do this and report back | Inngest durable functions |
| **Scheduled** | Do this later with fresh state | Inngest (`step.sleep()`, `step.sleepUntil()`, `step.sendEvent()`) |

Scheduled jobs execute against current state at run time, not the state that existed when scheduled.

Job metadata:

| Field | Purpose |
|-------|---------|
| `job_id` | Identity |
| `tenant_id` | Isolation (*Blast Radius Limiter*) |
| `origin_worker_id` | Ownership |
| `origin_run_id` | Provenance |
| `job_type` | Classification |
| `status` | Lifecycle |
| `supersedes_job_id` | Lineage (links replaced jobs) |
| `source_call_id` | Correlation — links to originating voice call |
| `created_at` | Temporal |
| `updated_at` | Temporal |

Job permissions:

| Operation | Who |
|-----------|-----|
| Status lookup | Origin worker, Founder Cockpit, Tenant Ops, harness-granted readers |
| Cancel | Origin worker, Founder Cockpit, Tenant Ops |
| Replace | Origin worker, Founder Cockpit, Tenant Ops |

Replace is a first-class operation (not manual cancel + create). `supersedes_job_id` maintains audit trail. All jobs with external side effects carry idempotency keys (*Idempotent Tool Calls*).

---

## Part VII. Agent Harness

The runtime operating system for all agent work. Maps primarily to L1 (Cognition), L4 (Coordination), and L5 (Execution).

### Capabilities & Infrastructure

| Capability | Implementation | Layer |
|------------|---------------|-------|
| Orchestration & State | LangGraph (graphs, subgraphs, checkpoints) | L4 |
| Delegation & Jobs | LangGraph subgraphs (sync) + Inngest (async/scheduled) | L3, L5 |
| Tool Registry / MCP | Harness-managed tool access | L5 |
| Sandboxed Execution | E2B | L5 |
| Browser Automation | Stagehand | L5 |
| Artifact Production | Agents produce artifacts during execution; storage is L2, lifecycle governance is L7 | L5 (creation) |
| Context Management | Context assembly, compaction, windowing, progressive disclosure | L2 |
| Memory & Retrieval | Tenant-scoped retrieval, cache, and optional persistent memory | L2 |
| Policy / Compliance Gate | Centralized pre-execution gate (*Agent Circuit Breaker*, *Blast Radius Limiter*) | L6 |
| Verification & Validation | Post-execution quality checks (*Confidence Threshold Gate*) | L6 |
| Tracing / Observability | LangSmith with PII redaction (*Agentic Observability Tracing*) | L7 |
| Alerting | Emits alerts on policy block rate, worker degradation, job failure spikes | L7 |
| Model Gateway | Helicone (evaluate) or LiteLLM → Claude Sonnet 4.6 (primary) + Ollama (triage) (*LLM Gateway Pattern*). Helicone provides edge-deployed proxy (< 1ms latency), per-tenant cost tracking, request-level logging, caching, rate limiting, and SOC 2 / HIPAA compliance. LangSmith remains for workflow-level tracing and evals. | L1 |

### Infrastructure Resilience

| Component | Classification | On Failure |
|-----------|---------------|------------|
| LangGraph | **Blocking** | All harness work stops. No degraded mode. (*Agent Circuit Breaker* opens.) |
| Inngest | **Blocking for async/scheduled** | Sync work continues. Async/scheduled jobs queue or fail. Stale job detection required. |
| LLM Gateway (Helicone or LiteLLM) | **Blocking** | All LLM calls fail. No silent fallback. Gateway may route to Ollama for triage only. |
| LangSmith | **Degradable** | Tracing stops; worker execution continues. Pino fallback locally. |
| E2B | **Degradable** | Sandboxed execution unavailable; non-sandbox workers continue. |
| Stagehand | **Degradable** | Browser automation unavailable; non-browser workers continue. |
| Redis | **Degradable** | Cache miss falls back to file reads. Performance degrades; correctness maintained. |

Failed blocking components route to *Dead Letter Queue for Agents*. Recovery follows *Agent Circuit Breaker* half-open → closed pattern.

### Infrastructure Deployment

| Component | Hosting | Platform | Deploy Mechanism |
|-----------|---------|----------|-----------------|
| LangGraph | Self-hosted (Node.js) | Render | Git push deploy |
| Inngest | Managed SaaS | Inngest Cloud | API key + event routing |
| LLM Gateway | Helicone (managed SaaS, Cloudflare edge) or LiteLLM (self-hosted on Render). Evaluate in Phase 1. | API key or git push deploy |
| LangSmith | Managed SaaS | LangChain Cloud | API key |
| E2B | Managed SaaS | E2B Cloud | API key |
| Stagehand | Self-hosted (within harness) | Render (same as LangGraph) | Bundled with harness |
| Redis | Managed | Render Redis or Upstash | Platform-managed |

### Triggering & Integration

```
  TRIGGER PATH (inbound):
  Retell AI ──webhook──▶ Express V2 ──Inngest event──▶ Agent Harness
  (call complete)         (process,                     (context assembly,
                           persist to                    worker dispatch,
                           Supabase)                     artifact creation)

  RETURN PATH (outbound):
  Agent Harness ──direct write──▶ Supabase        (persist results, artifacts, job status)
                ──Inngest event──▶ Express V2      (notify product core of completed work)
                ──API call──▶ Cal.com / Twilio      (external actions: bookings, alerts)
                ──trace──▶ LangSmith                (observability, eval data)
                ──git commit──▶ Artifact repo       (generated docs, reports, plans)
```

External actions (bookings, alerts) go through the tool registry and are subject to Policy Gate and V&V checks (*Tool Invocation Timeout*, *Idempotent Tool Calls*).

### Service Authentication

| Integration | Auth Mechanism | Secret Management |
|-------------|---------------|-------------------|
| Express V2 → Inngest | Inngest event key (signing key) | Render env var |
| Harness → Inngest | Inngest event key | Render env var |
| Harness → LangSmith | API key | Render env var |
| Harness → E2B | API key | Render env var |
| Harness → LLM Gateway | Helicone: API key + base URL swap. LiteLLM: internal (localhost). | Render env var |
| LLM Gateway → Anthropic | API key (managed by gateway) | Render env var or Helicone dashboard |
| LLM Gateway → Ollama | Local network (no auth) | N/A |
| Harness → Linear | API key (OAuth for user-facing, API key for harness) | Render env var |
| Harness → Supabase | Service role key (bypasses RLS for harness ops) | Render env var |
| Harness → Redis | Connection string with auth token | Render env var |
| Harness → Cal.com | API key | Render env var |
| Harness → Twilio | Account SID + Auth Token | Render env var |

All secrets stored in platform env vars, never in code. Secrets must be rotatable without code deploy.

### Policy Gate (L6)

The policy gate checks every agent action before execution:

- **What it checks:** forbidden claims, pricing language, required disclosures, tenant-specific restrictions, tool permissions, publish/send authorization
- **When it fires:** pre-execution, before the harness grants tool access or allows output
- **On violation:** block and log (default), or escalate to Founder Cockpit if configured (*Human Escalation Protocol*)
- **Default when no rule matches:** **deny and log.** Workers must have explicit permission.
- **Inputs:** compliance graph, industry pack rules, tenant config, feature flags
- **Conflict resolution:** most-restrictive-wins. Contradictory rules → block and escalate.

### Verification & Validation Pipeline (L6)

V&V checks every worker output after execution but before persistence or external action:

- **What it checks:** output format, factual accuracy against knowledge graph, tone compliance, safety (no forbidden claims, no PII leakage), booking/alert correctness
- **When it fires:** post-execution, before artifact persistence or external action
- **On failure:** block and log. Retry once with failure reason appended. If retry fails, escalate with failed output attached (*Human Escalation Protocol*, *Dead Letter Queue*).
- **Distinction from Policy Gate:** Policy fires before (is this permitted?). V&V fires after (is this correct and safe?). Both must pass.

### Tool Governance (L5, L6)

Model: **Authored → Validated → Granted**

| Stage | What Happens | Where |
|-------|-------------|-------|
| Authored | Worker spec declares `tools_allowed` | Worker spec YAML |
| Validated | CI/lint gate checks spec against global policy | Authoring-time (CI) |
| Granted | Harness resolves what's available for this run, this tenant, this environment | Runtime (harness) |

Runtime policy is always authoritative over authored specs.

### Context Management (L2)

For each worker run, the harness assembles context from multiple sources. Priority order when context exceeds the model window:

1. Worker spec (mission, scope, tools) — always included
2. Active task/job context — always included
3. Tenant config — always included for tenant-scoped runs
4. Relevant industry pack sections — included, compacted if needed
5. Knowledge graph nodes (pulled by relevance) — progressive disclosure, summarized first
6. Memory & retrieval results — included up to budget
7. Historical context — compacted or dropped first

Compaction reduces lower-priority sources first. The harness manages the context budget; workers do not assemble their own context. After compaction, *Context Window Checkpointing* ensures agents re-read their operating contract.

### Error Philosophy

1. **No silent failures** — every error logged with full context (*Agentic Observability Tracing*)
2. **Fail loud** — block and surface to Cockpit rather than swallow (*Human Escalation Protocol*)
3. **LLM output validation** — all outputs through V&V; malformed/refusal responses retried once, then escalated (*Confidence Threshold Gate*)
4. **Partial state is the enemy** — multi-step operations must be atomic or have explicit rollback

Traces contain customer PII. Before sending to LangSmith: redact/hash direct identifiers, tag with data classification level, apply tenant-scoped retention policies.

---

## Part VIII. Knowledge Substrate

Maps to L2 (Knowledge & Memory). The structured knowledge layer under the entire system.

### Knowledge Graphs

| Graph | Scope | Trust Level |
|-------|-------|-------------|
| Company graph | Business model, strategy, team, goals | Curated |
| Product graph | Features, roadmap, architecture, dependencies | Curated |
| Industry graphs | Per-trade: HVAC, Plumbing, Rooter, future verticals | Curated |
| Compliance graph | Regulations, required disclosures, forbidden claims, licensing | Curated |
| Customer insight graph | Patterns from calls, feedback, churn signals, satisfaction | Provisional (untrusted input) |

Implementation:

- Markdown files with YAML/frontmatter metadata
- Wiki links (`[[path]]` syntax resolving relative to `knowledge/`)
- MOCs (Maps of Content) / `_moc.md` index files for navigation
- Progressive disclosure (summary → detail)
- Ownership + freshness metadata on every node

### Customer-Derived Content Pipeline

Customer-derived content is untrusted input. Content passes through three states:

| State | Examples | Trust | Rules |
|-------|----------|-------|-------|
| **Raw** | Transcript, message, call notes | Never trusted | Never injected into worker context or policy decisions. Stored for audit. |
| **Sanitized** | Neutralized transcript | Low trust | Instruction-like or adversarial content neutralized. Not yet usable as knowledge. |
| **Structured insight** | Claims, labels, patterns with provenance | Usable with limits | Explicit claims with provenance to raw source. Confidence/verification status assigned. Safe to use as knowledge input with policy limits. |

Only structured insights may influence agent behavior, and only through normal context assembly where they are lower-priority than curated knowledge. This prevents data poisoning through adversarial caller content (*Blast Radius Limiter*).

### Retrieval & Caching

Two complementary mechanisms:

1. **Retrieval engine:** QMD or equivalent local hybrid search. Indexes markdown/YAML into SQLite with BM25 full-text + optional vector semantic search + LLM re-ranking. Runs locally (no cloud dependency). Collections map to graph categories. MCP server mode integrates with harness tool registry.

2. **Cache layer (Redis):** Hot-path caching for frequently accessed nodes. Cache keys tenant-namespaced (*Semantic Caching*). Compliance and policy nodes invalidated on deploy (never TTL-based). Cache miss falls back to file reads.

### Compliance Rules

Markdown/YAML compliance content is **descriptive and authoring-facing**; executable compliance rules are **database-backed in Supabase and authoritative at runtime**. When there is any conflict, the database rules win — markdown documents intent, the database executes policy.

The skill pack `skill-packs/compliance/` contains methods for applying compliance rules (checking workflows, audit procedures); the compliance graph in Supabase contains the rules themselves.

---

## Part IX. Tenant Operations

Maps to L7 (Operations). Sits between internal workforce and client instances.

Tenant Operations is an **operational system managed by the Agent Harness**, not a worker agent. It is a set of harness-orchestrated workflows and automations.

### Responsibilities

- Client onboarding
- Assigning industry packs
- Loading tenant configs
- Applying inherited policy rules
- Provisioning automations
- Monitoring client health
- Routing escalations (*Human Escalation Protocol*)
- Safe deployment/release controls per tenant (*Canary Agent Deployment*)

### Onboarding Workflow

```
  1. Create tenant record ──▶ Supabase (tenant_id, tenant_name, contact)
  2. Assign industry pack ──▶ Validate pack exists, set tenant_config.industry_pack_id
  3. Load tenant config    ──▶ Populate defaults from industry pack, allow overrides
  4. Apply RLS policies    ──▶ Ensure tenant_id RLS active on all tenant-scoped tables
  5. Provision automations ──▶ Set up Inngest scheduled jobs (follow-ups, reports)
  6. Configure voice agent ──▶ Create/assign Retell agent with tenant-specific metadata
  7. Verify isolation      ──▶ Automated check: can this tenant see other tenants' data? (must fail)
  8. Cockpit notification  ──▶ Alert founder that new tenant is provisioned

  ON FAILURE AT ANY STEP:
  Roll back all completed steps. Tenant marked "onboarding_failed" with failure step
  and error. Cockpit alerted. No partial tenant state left active.
```

Required inputs: `tenant_name`, `industry_pack_id`, `contact_email`, `service_area`. Missing any → reject and surface error.

Governance: Tenant Ops workflows execute under the harness with the same tool governance, policy gate, and tracing as any worker. Administrative actions require Cockpit approval and are logged.

### Durable Workspace / Artifact Layer

Where agents externalize work:

| Surface | Purpose |
|---------|---------|
| Git repositories | Code, config, prompt files, knowledge graph files |
| Sandbox filesystem | Ephemeral working space within E2B sandboxes |
| Artifact / log store | Generated reports, summaries, analysis outputs |
| Planning documents | Specs, implementation plans, experiment designs |

Artifact governance:

| Rule | Detail |
|------|--------|
| Access control | Tenant-scoped artifacts readable only by originating tenant's workers, Tenant Ops, and Cockpit. Internal artifacts readable by internal workers and Cockpit. |
| Retention | Tenant artifacts follow tenant-scoped retention policies. Internal artifacts follow global retention policy. Sandbox files deleted on teardown. |
| Registry of record | Git for version-controlled outputs. Supabase for structured data artifacts. TBD object store for binary/large-file artifacts. |
| Lifecycle | Created → Active → Archived → Deleted. No silent deletion. |
| Auditability | Every artifact records: `created_by`, `tenant_id`, `created_at`, `source_job_id`, `artifact_type`. |

---

## Part X. Evaluation & Learning

Maps to L8 (Learning & Improvement) and the learning plane.

### Evaluation Layer

Evals at three levels:

| Level | Question |
|-------|----------|
| **Core** | Does the shared product still work? |
| **Industry** | Does HVAC/Plumbing/Rooter still work? |
| **Tenant** | Does this specific client's configured behavior still work? |

Eval targets: lead routing accuracy, booking logic correctness, tone compliance, objection handling quality, summary quality, publish/send safety, reporting quality, worker `success_metrics`.

### Two Testing Concerns

| Concern | Tool | Coverage |
|---------|------|----------|
| **Behavioral evals** | LangSmith datasets + evaluators | AI output quality: routing, tone, summaries, booking, worker metrics |
| **Infrastructure tests** | Vitest | Harness correctness: policy gate, context assembly, tool governance, job lifecycle, tenant isolation, idempotency, cache scoping |
| **Resilience tests** | Vitest with mocked failures | Degradable fallback behavior, blocking component error surfacing, stale job detection |

All three are required. Evals passing while harness infrastructure is broken is a silent failure.

### Eval Data Sourcing

| Source | Use | Notes |
|--------|-----|-------|
| Synthetic test cases | Infrastructure tests, policy gate logic, tenant isolation | Hand-written, deterministic, no PII |
| Anonymized production data | Behavioral evals | Derived from real transcripts via customer content pipeline. PII redacted. Subject to tenant consent. |
| Hand-curated golden examples | Critical path evals, baseline comparisons | Founder-reviewed. Minimum: 10 per eval target before first worker activation. |

### Minimum Viable Eval Suite

Before any worker is promoted from spec to active use:

- At least 10 golden examples per `success_metric` in the worker's spec
- Infrastructure tests covering policy gate, context assembly, and tool governance for that worker's `tools_allowed`
- One resilience test per blocking dependency and one per degradable dependency the worker uses

### Improvement Lab

Offline or pre-production improvement harness for systematic product improvement.

Process:

1. Propose a small change
2. Mutate one bounded surface
3. Run a fixed-budget experiment
4. Score against baseline using the same LangSmith evaluators from the Evaluation Layer
5. Keep or discard
6. Log the result

Good mutation targets: prompt files, workflow nodes, script variants, copy variants, threshold rules, industry-pack logic.

Experiment isolation: only one experiment may mutate a given surface at a time. Sequential, not concurrent. Lock registry with TTL/heartbeat prevents stale locks. Cockpit can force-release (*Agent Circuit Breaker* pattern applied to experiments).

Design principle: the Lab proposes changes; it cannot directly promote them to production. Changes that survive experiments are promoted through the Safe Delivery Layer (*Canary Agent Deployment*).

---

## Part XI. Stack Reference

| Category | Components |
|----------|-----------|
| **Voice runtime** | Retell AI (10-state FSM, LLM-driven transitions, GPT-4o) |
| **Agent harness** | LangGraph, LangSmith (evals + workflow tracing), Claude Sonnet 4.6 (primary), Ollama (triage), Helicone or LiteLLM (LLM gateway), Redis, E2B, Stagehand |
| **Application database** | Supabase (PostgreSQL + realtime) |
| **Product core** | Express V2 (Node.js/TypeScript), Next.js 16 (React 19) |
| **Integrations** | Cal.com (booking), Twilio (SMS alerts), Retell AI webhooks, Linear (work tracking) |
| **Safe delivery** | Vercel (CallLock App), Render (backend + harness), Retell API (voice config) |
| **Delegation/jobs** | LangGraph subgraphs (sync), Inngest (async/scheduled, handles, cancel/replace, idempotency) |
| **Knowledge** | Markdown/YAML graphs, MOCs, wiki links, frontmatter metadata, worker specs, skill packs |
| **Quality** | LangSmith evals (core/industry/tenant), Vitest (existing suite), Improvement Lab |
| **Coordination** | Agent Mail, br (bead storage), bv (graph-theory routing) |

### Safe Delivery Layer

Three deployment surfaces:

| Surface | Platform | Rollback | Preview/Staging |
|---------|----------|----------|-----------------|
| CallLock App (Next.js) | Vercel | Instant rollback | Preview deployments |
| Backend (Express V2) | Render | Manual deploy to previous commit | Branch deploys |
| Voice agent (Retell AI) | Retell API | Revert to previous config version | Test phone numbers |

Shared:

- Feature flags extend to harness capabilities, not just UI
- Knowledge graph, worker spec, and skill pack changes deployed via git, rolled back via git revert
- No automated change reaches production without preview, protection, and promotion gates

Design principle: a broken deploy costs more than a slow workflow. This layer matters more than orchestration sophistication.

---

## Part XII. Implementation Phasing

### Dependency Graph

```
  Phase 1 (Foundation)
  ├── Knowledge Substrate (graphs, worker specs, skill packs)
  ├── Industry Pack format + HVAC extraction from V2
  ├── Tenant Config schema + RLS isolation
  ├── Harness infrastructure (LangGraph + Redis on Render)
  └── LLM Gateway evaluation (Helicone vs LiteLLM)

  Phase 2 (Core Harness)                    depends on Phase 1
  ├── Policy Gate + compliance graph
  ├── Context assembly pipeline
  ├── Tool governance (authored → validated → granted)
  ├── Harness triggering (Express V2 → Inngest → Harness)
  ├── Return path (Harness → Supabase + Inngest events)
  ├── First worker activation (Customer Analyst) + minimum eval suite
  ├── 3D Command Center — initial read model (quest UI, agent status, internal control shell)
  └── Linear integration (quest/feature tracking backend for Command Center)

  Phase 3 (Full Operations)                 depends on Phase 2
  ├── V&V pipeline
  ├── Delegation & Jobs (async/scheduled via Inngest)
  ├── Tenant Operations (onboarding workflow)
  ├── Artifact governance + persistence
  ├── Remaining workers (PM, Engineer, Designer, Marketer)
  ├── Cockpit alerting + kill switches
  └── 3D Command Center — operator actions (dispatch, escalation triggers, workflow initiation)

  Phase 4 (Improvement)                     depends on Phase 3
  ├── Improvement Lab (experiment isolation, lock registry)
  ├── Full eval coverage (all three tiers)
  ├── Customer content pipeline (Raw → Sanitized → Structured)
  └── 3D Command Center — full internal operating surface (cross-department views, Founder Cockpit admin mode)
```

### Phase 1: Foundation

Goal: Establish the knowledge substrate, industry pack format, tenant isolation, and base harness infrastructure. No agent work runs yet.

| Deliverable | Acceptance Criteria |
|-------------|-------------------|
| Knowledge graph directory structure | Markdown/YAML graphs for company, product, HVAC industry, compliance. MOCs and wiki links working. |
| Knowledge retrieval engine | QMD or equivalent evaluated. Indexed search returning relevant nodes within latency budget. |
| Worker specs (5 initial) | All 5 defined in Standard Worker Schema. CI validation passing. |
| HVAC industry pack | 117 smart tags, 3 emergency tiers, service taxonomy extracted from V2. |
| Tenant config schema | Schema defined in Supabase. RLS policies active on all tenant-scoped tables. |
| Harness infrastructure | LangGraph, Redis deployed on Render. Health checks passing. |
| LLM Gateway decision | Evaluate Helicone (managed, edge-deployed, SOC 2/HIPAA, < 1ms latency, per-tenant cost tracking) vs LiteLLM (self-hosted, full control). Decision criteria: latency, cost visibility, compliance posture, operational burden. Chosen gateway deployed and routing to Claude Sonnet 4.6. |

### Phase 2: Core Harness

Goal: The harness can receive an event from Express V2, assemble context, run a worker through the policy gate, and persist results. One worker (Customer Analyst) is live.

| Deliverable | Acceptance Criteria |
|-------------|-------------------|
| Policy Gate | Deny-by-default working. Compliance graph reads. Most-restrictive-wins conflict resolution. |
| Context assembly | Priority ordering correct. Compaction working. Budget enforced. |
| Harness triggering | Express V2 → Inngest → Harness flow working end-to-end. |
| Return path | Harness → Supabase writes + Inngest notification events. |
| Customer Analyst worker | Activated with minimum eval suite (10 golden examples per metric). |
| Service authentication | All integration points authenticated per service auth table. |
| 3D Command Center (initial read model) | Quest UI, agent status projections, internal control shell. Read-only views over harness state. No operator write actions yet. |
| Linear integration | Linear as quest/feature tracking backend. Agents can create/update issues via tool registry (subject to Policy Gate). Command Center projects Linear state into quest UI. Bead-level execution state stays in `br` — Linear owns human-visible work items only. |

### Phase 3: Full Operations

Goal: All workers active, tenant onboarding automated, async jobs running, full artifact governance. Command Center gains operator write actions.

| Deliverable | Acceptance Criteria |
|-------------|-------------------|
| V&V pipeline | Post-execution checks working. Retry + escalation on failure. |
| Delegation & Jobs | Async/scheduled via Inngest. Idempotency keys on external side effects. |
| Tenant Operations | Onboarding workflow end-to-end. Rollback on failure. |
| Artifact governance | Persistence with tenant scoping, lifecycle, auditability. |
| Remaining workers | PM, Engineer, Designer, Marketer activated with eval suites. |
| Cockpit alerting + kill switches | Alerts on policy block rate, worker degradation, job failure spikes. Kill switches functional. |
| 3D Command Center (operator actions) | Dispatch, escalation triggers, workflow initiation. Operator can act on projected state, not just read it. |

### Phase 4: Improvement

Goal: Improvement Lab, full eval coverage, customer content pipeline, 3D Command Center reaches full internal operating surface with Founder Cockpit admin mode.

### Phasing Principles

- Each phase is deployable independently — no phase depends on a later phase
- Express V2 continues handling all production traffic throughout; harness work is additive
- Feature flags gate new harness capabilities; partial phase completion is safe
- Phase boundaries are not hard walls — work can start on Phase N+1 items once their Phase N dependencies are complete

---

## Governance Summary

| Principle | Rule |
|-----------|------|
| Tool access | Authored → Validated (CI) → Granted (runtime) |
| Approval boundaries | Same authored → validated → enforced pattern |
| Job ownership | Origin worker manages its own jobs; Cockpit/Ops have admin override |
| Worker creation | No new worker without non-overlapping mission + eval coverage |
| Knowledge authority | This repo owns all specs and skill packs; upstream is reference only |
| Deployment | All changes through Safe Delivery promotion gates (*Canary Agent Deployment*) |
| Tenant isolation | Scoped memory, traces, evals, configs — no cross-tenant leakage (*Blast Radius Limiter*) |
| Artifact governance | Persisted outputs inherit tenant/internal access controls and retention rules |
| Worker inter-visibility | Workers cannot read other workers' job status unless `job_read` is in `tools_allowed` and granted by harness |
| Error handling | No silent failures; fail loud; partial state is the enemy (*Dead Letter Queue*, *Human Escalation Protocol*) |

---

## What Is Explicitly Not Core

Do not make these foundational right now:

- Symphony — coding-work orchestration, optional later
- Hermes Agent as production runtime — useful as internal operator harness, not core
- Broad multi-agent committee consensus — use supervisor + specialists (*Orchestrator vs Choreography*)
- Multiple memory systems at once — one memory approach, well-scoped
- A different flagship model per worker — Claude Sonnet 4.6 is primary (*LLM Gateway Pattern*)
- Autonomous self-modification in production — improvements go through the Lab
- `agency-agents` as infrastructure — reference material only
- Automatic upstream sync from reference repos — one-time distillation only
- Dozens of specialist roles before evals prove they help
- Personality-first design over workflow-first design

---

## Open Questions

**Non-blocking for Phase 1** (resolve when needed):

1. **Persistent memory provider** — Mem0 or alternative? Deferred until tenant memory scope is needed.
2. **Semantic cache threshold** — When does repetition justify Qdrant over Redis? Needs usage data. Also evaluate multimodal embedding models (e.g., Gemini Embedding 2) for unified text + audio retrieval when vector search is justified.
3. **Skill pack granularity** — How large should a single skill pack be? TBD as first packs are authored.
4. **Improvement Lab cadence** — How often do experiment loops run? Fixed budget? Lab is Phase 3+.

**Resolved:**

- **Minimum viable eval suite** — 10 golden examples per success_metric, infrastructure tests for policy gate / context assembly / tool governance, one resilience test per dependency.
- **Artifact registry of record** — Git for version-controlled outputs; Supabase for structured data; TBD object store for binary/large-file artifacts.

---

## Companion Spec Authority

This architecture spec is authoritative for: shared platform boundaries, runtime split, tenant isolation, deployment posture, system model (layers, planes, design concepts), and infrastructure constraints.

The growth-system companion spec in `knowledge/growth-system/design-doc.md` is authoritative for GTM and growth-system behavior: growth memory, wedge/segment/angle/asset/proof/doctrine semantics, routing, lifecycle, experimentation, conviction/readiness, and founder review behavior.

The canonical program sequence lives in `plans/whole-system-executable-master-plan.md`.
