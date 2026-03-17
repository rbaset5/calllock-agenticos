# CallLock AgentOS Architecture Spec

## 0. Current State & Evolution Path

CallLock is not greenfield. A production system is already handling real calls. This section maps the existing production components to their target-state equivalents in this spec.

### Production System (as of March 2026)

| Component | Stack | Status |
|-----------|-------|--------|
| Voice agent | Retell AI V10 (10-state FSM, LLM-driven transitions, GPT-4o) | **Live** |
| Backend | Node.js / TypeScript / Express (V2), deployed on Render | **Live** |
| Database | Supabase (PostgreSQL + realtime) | **Live** |
| Dashboard | Next.js 16 / React 19, deployed on Vercel | **Live** |
| Booking | Cal.com integration | **Live** |
| Alerts | Twilio SMS (emergency + sales lead) | **Live** |
| Industry logic | HVAC-only (117 smart tags, 3 emergency tiers, service taxonomy) | **Hardcoded in V2** |
| Multi-tenant (voice) | Retell agent metadata routing (agent ID / phone number) | **Partial** |
| Multi-tenant (app) | Not yet | **Not started** |
| Tests | 31+ Vitest integration tests (V2), unit tests (dashboard) | **Partial** |

### Evolution Map

```
  CURRENT PRODUCTION              TARGET SPEC LAYER                    ACTION
  ──────────────────              ─────────────────                    ──────
  Retell AI V10 (voice)           Voice Runtime (new layer)            KEEP — voice stays on Retell AI
  Express V2 (backend)            Shared Product Core                  EVOLVE — becomes trade-neutral core
  Supabase                        Application Database                 KEEP — already PostgreSQL
  Next.js dashboard               Shared Product Core (web app)        KEEP — evolves with core
  Cal.com                         Product Core integration             KEEP — booking stays
  Twilio                          Product Core integration             KEEP — alerts stay
  Pino logging                    Tracing / Observability (LangSmith)  ADD ALONGSIDE — Pino continues locally
  HVAC smart tags (hardcoded)     Industry Pack (HVAC)                 EXTRACT — from V2 into pack format
  Emergency tiers (hardcoded)     Compliance Graph                     EXTRACT — from V2 into graph
  Retell webhook auth             Policy / Compliance Gate             CARRY FORWARD — existing security patterns
  (nothing)                       Agent Harness Layer                  BUILD NEW
  (nothing)                       Delegation & Jobs (Inngest)          BUILD NEW
  (nothing)                       Knowledge Substrate (graphs)         BUILD NEW
  (nothing)                       Worker Specs + Skill Packs           BUILD NEW
  (nothing)                       Improvement Lab                      BUILD NEW
  (nothing)                       Founder Cockpit                      BUILD NEW
```

### Architectural Boundary

The Agent Harness Layer orchestrates **everything except real-time voice conversation**. Retell AI remains the voice runtime. The harness handles: internal workers, async/scheduled jobs, eval/improvement loops, tenant operations, and non-voice product workflows.

```
  ┌─────────────────────────────────────────────────────┐
  │              AGENT HARNESS (LangGraph)               │
  │  Workers, Jobs, Policy, Eval, Improvement Lab        │
  └──────────────────────┬──────────────────────────────┘
                         │ orchestrates
  ┌──────────────────────┼──────────────────────────────┐
  │                      │                              │
  │  PRODUCT CORE        │    VOICE RUNTIME             │
  │  (Express V2 +       │    (Retell AI V10)           │
  │   Next.js +          │                              │
  │   Supabase +         │    Handles: real-time calls, │
  │   Cal.com + Twilio)  │    FSM transitions, GPT-4o   │
  │                      │                              │
  └──────────────────────┴──────────────────────────────┘
```

### What This Spec Does NOT Replace

- Retell AI — stays as the voice runtime
- Supabase — stays as the application database
- Cal.com — stays as the booking provider
- Twilio — stays as the alert provider
- Express V2 — evolves into part of the product core, not replaced
- Existing Vitest suite — carries forward, augmented by LangSmith evals

---

## 1. Overview & Core Principle

CallLock AgentOS is a multi-tenant, multi-industry operating platform for agent-powered home-services software.

**Core formula:**

> Core product + industry pack + tenant config + agent harness + safe delivery + eval/improvement loop = scalable agentic company system

The system is designed around a shared product core, harness-enforced governance, and tenant-scoped specialization rather than bespoke per-client systems.

**What this is:**

- One shared voice/web platform
- Industry packs for HVAC, Plumbing, Rooter, and future trades
- Tenant configs per client
- Safe delivery rails for coding agents
- Structured knowledge graphs under the whole system
- An agent harness that provides orchestration, delegation, policy, and observability

**What this is not:**

- Many separate products
- One giant mega-agent
- A "mini agency" of personality-driven specialists
- A prompt library masquerading as a production system

### Companion Spec Authority

This architecture spec remains authoritative for shared platform boundaries, runtime split, tenant isolation, deployment posture, and ADR-backed infrastructure constraints.

The growth-system companion spec in `knowledge/growth-system/design-doc.md` is authoritative for GTM and growth-system behavior:

- Growth Memory and growth-system object model
- wedge, segment, angle, asset, proof, doctrine, and wedge-fitness semantics
- routing, lifecycle, experimentation, conviction/readiness, and founder review behavior
- advanced growth modules such as pricing, channel mix, geographic intelligence, and aggregate intelligence
- rollout and trust-ladder behavior for the growth system

That companion spec now explicitly separates implementation-blocking Stage 0-2 contracts from later-stage directional modules; shared-platform docs should not blur that boundary.

Legacy narrowed terms from the prior persuasion-platform rewrite (`persuasion_path`, `graph_mutation`, `review_object`, `lineage_chain`, `decisioning_projections`, `operator_projections`, `control_plane_auth`, `federated_benchmark`) remain valid only through the explicit compatibility bridge in `knowledge/growth-system/design-doc.md`.

The canonical program sequence now lives in `plans/whole-system-executable-master-plan.md`.

Phase plans may provide supporting detail, but they should not redefine those persuasion-platform contracts or override the master plan on sequencing, readiness gates, or execution priority.

---

## 2. Architecture Hierarchy

```
Founder Cockpit
├── Safe Delivery Layer
│   ├── Dashboard deploys (Vercel)
│   ├── Backend deploys (Render)
│   └── Voice agent deploys (Retell AI config)
├── Agent Harness Layer
│   ├── Orchestration & State (LangGraph)
│   ├── Delegation & Jobs (LangGraph subgraphs + Inngest)
│   ├── Tool Registry / MCP
│   ├── Sandboxed Execution (E2B)
│   ├── Browser Automation (Stagehand)
│   ├── Context Management
│   ├── Memory & Retrieval
│   ├── Policy / Compliance Gate
│   ├── Verification & Validation
│   ├── Tracing / Observability (LangSmith)
│   └── Model Gateway (LiteLLM → Claude Sonnet 4.6 + Ollama)
├── Voice Runtime (Retell AI)
│   └── 10-state FSM, LLM-driven transitions, GPT-4o
├── Durable Workspace / Artifact Layer
├── Knowledge Substrate
│   ├── Company Graph
│   ├── Product Graph
│   ├── Industry Graphs
│   ├── Compliance Graph
│   ├── Customer Insight Graph
│   ├── Worker Spec Library
│   └── Skill Packs
├── Shared Product Core (Express V2 + Next.js + Supabase + Cal.com + Twilio)
├── Industry Pack Layer (HVAC, Plumbing, Rooter, ...)
├── Tenant Config / Isolation
├── Internal Workforce
├── Tenant Operations
├── Client Instances
├── Evaluation Layer
└── Improvement Lab
```

Layers near the top govern the system; layers in the middle define shared capabilities and product structure; layers near the bottom represent tenant-scoped execution, evaluation, and improvement.

---

## 3. Founder Cockpit

The command layer. Not a worker agent — a control surface for the founder/operator.

**Responsibilities:**

- Portfolio KPIs and industry-by-industry performance
- Client health monitoring
- Approvals for risky actions (publish, send, billing changes)
- Budget and margin oversight
- Experiment oversight (Improvement Lab visibility)
- Release oversight (Safe Delivery visibility)
- Eval results visibility (promotion decisions require eval data)
- Kill switches and pause controls

**Alerting:** The harness emits alerts to the Cockpit when: policy gate block rate exceeds threshold, worker success metrics degrade, job failure rate spikes, or external service errors exceed threshold. Without proactive alerting, kill switches and pause controls are reactive-only.

**Design principle:** The Cockpit observes and approves. It does not perform routine delivery work. Workers propose; the Cockpit decides. This is the only layer with cross-tenant administrative override.

---

## 4. Safe Delivery Layer

Keeps coding agents and automated changes from breaking production. This layer governs changes to product code, configs, prompts, and other production-affecting artifacts.

**Three deployment surfaces:**

| Surface | Platform | Rollback | Preview/Staging |
|---------|----------|----------|-----------------|
| Dashboard (Next.js) | Vercel | Instant rollback | Vercel preview deployments |
| Backend (Express V2) | Render | Manual deploy to previous commit | Render preview environments or branch deploys |
| Voice agent (Retell AI) | Retell API | Revert to previous agent config version | Blue/green agent configs or test phone numbers |

**Components (dashboard — Vercel):**

- Vercel preview deployments (non-production branches and PRs)
- Vercel Flags (feature flags)
- Vercel Deployment Protection (project-level)
- Instant rollback (production deployments)
- Promotion-based release flow (preview → production via approval gates)

**Components (backend — Render):**

- Branch-based preview environments
- Manual rollback to previous deploy
- Health check monitoring
- Zero-downtime deploys

**Components (voice agent — Retell AI):**

- Agent config versioning (V4 → V6 → V10 history exists)
- Test phone number for pre-production validation
- Fallback to previous config version on failure
- One PR per issue, no batch deploys (proven practice from V10 optimization log)

**Shared:**

- Branch-safe test environments / branchable data where supported (aspirational; specific tooling TBD, e.g., Neon branching for Postgres)
- Feature flags should extend to harness capabilities (enabling/disabling workers, knowledge graphs, Improvement Lab experiments), not just dashboard UI
- Knowledge graph, worker spec, and skill pack changes are deployed via git and rolled back via git revert — these are version-controlled markdown/YAML files with the same rollback affordance as code

**Design principle:** No automated change reaches production without passing through preview, protection, and promotion gates. This applies to all three deployment surfaces — dashboard, backend, and voice agent. This layer matters more than orchestration sophistication — a broken deploy costs more than a slow workflow.

---

## 5. Agent Harness Layer

The runtime operating system for all agent work. Consolidates orchestration, delegation, policy, tooling, and observability into one named layer.

### 5a. Capabilities & Infrastructure

**Contains:**

| Capability | Implementation |
|------------|---------------|
| Orchestration & State | LangGraph (graphs, subgraphs, checkpoints) |
| Delegation & Jobs | LangGraph subgraphs (sync) + Inngest (async/scheduled, handles, cancel/replace) |
| Tool Registry / MCP | Harness-managed tool access |
| Sandboxed Execution | E2B |
| Browser Automation | Stagehand |
| Context Management | Context assembly, compaction, windowing, progressive disclosure (see 5d) |
| Memory & Retrieval | Tenant-scoped retrieval, cache, and optional persistent memory services |
| Policy / Compliance Gate | Centralized pre-execution gate; reads from compliance graph + industry pack + tenant config. On violation: block and log (default), or escalate to Cockpit for approval if configured. See 5c. |
| Verification & Validation | Post-execution quality checks — output correctness, safety, and compliance. Distinct from the Policy Gate: policy fires before execution, V&V fires after. See 5c. |
| Tracing / Observability | LangSmith (PII redaction required — see 5e) |
| Alerting | Harness emits alerts to Cockpit on policy gate block rate, worker metric degradation, job failure spikes, external service errors |
| Model Gateway | LiteLLM → Claude Sonnet 4.6 (primary, or current best Anthropic model at implementation time) + Ollama (cheap/local triage). Per-tenant cost tracking required; budget enforcement at gateway level; Cockpit visibility into LLM spend per tenant. |

**Infrastructure resilience classification:**

| Component | Classification | On failure |
|-----------|---------------|------------|
| LangGraph | **Blocking** | All harness work stops. No degraded mode — orchestration is foundational. |
| Inngest | **Blocking for async/scheduled** | Sync work continues via LangGraph subgraphs. Async/scheduled jobs queue or fail. Stale job detection required. |
| LiteLLM | **Blocking** | All LLM calls fail. No silent fallback — surface error immediately. If primary model (Claude) is unavailable, LiteLLM may route to Ollama for triage-level work only. |
| LangSmith | **Degradable** | Tracing and evals stop, but worker execution continues. Log locally (Pino) as fallback. Alert on prolonged outage. |
| E2B | **Degradable** | Sandboxed execution unavailable. Workers requiring sandbox are blocked; others continue. |
| Stagehand | **Degradable** | Browser automation unavailable. Workers requiring it are blocked; others continue. |
| Redis | **Degradable** | Cache miss falls back to file reads. Performance degrades but correctness maintained. |

**Harness infrastructure deployment:**

| Component | Hosting | Platform | Deploy mechanism |
|-----------|---------|----------|-----------------|
| LangGraph | Self-hosted (Node.js process) | Render (alongside or separate from Express V2) | Git push deploy |
| Inngest | Managed SaaS | Inngest Cloud | API key + event routing config |
| LiteLLM | Self-hosted proxy | Render (separate service) | Git push deploy |
| LangSmith | Managed SaaS | LangChain Cloud | API key |
| E2B | Managed SaaS | E2B Cloud | API key |
| Stagehand | Self-hosted (within harness process) | Render (same as LangGraph) | Bundled with harness deploy |
| Redis | Managed | Render Redis or Upstash | Platform-managed |

### 5b. Triggering & Integration

**Harness triggering:**

The harness is triggered by events from the existing production system. The primary trigger path: Express V2 emits an Inngest event after processing a Retell webhook, and the harness subscribes to that event. This bridge must be backward-compatible — Express V2 emitting events that nothing yet listens to is safe; deploying harness listeners before Express V2 emits events means missed work.

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

The return path uses direct Supabase writes for data persistence (harness has its own Supabase client) and Inngest events to notify Express V2 of completed work. External actions (bookings, alerts) go through the harness's tool registry and are subject to Policy Gate and V&V checks before execution.

**Service authentication:**

| Integration | Auth mechanism | Secret management |
|-------------|---------------|-------------------|
| Express V2 → Inngest | Inngest event key (signing key verifies source) | Render env var |
| Harness → Inngest | Inngest event key | Render env var |
| Harness → LangSmith | API key | Render env var |
| Harness → E2B | API key | Render env var |
| Harness → LiteLLM | Internal (same-process or localhost) | N/A or Render env var |
| LiteLLM → Anthropic | API key | Render env var |
| LiteLLM → Ollama | Local network (no auth) | N/A |
| Harness → Supabase | Service role key (bypasses RLS for harness operations) | Render env var |
| Harness → Redis | Connection string with auth token | Render env var |
| Harness → Cal.com | API key | Render env var |
| Harness → Twilio | Account SID + Auth Token | Render env var |

All secrets are stored in platform env vars (Render environment groups), never in code. Secrets must be rotatable without code deploy (env var update + service restart).

### 5c. Policy & Verification

**Policy / Compliance Gate detail:**

The policy gate checks every agent action before execution:

- **What it checks:** forbidden claims, pricing language, required disclosures, tenant-specific restrictions, tool permissions, publish/send authorization
- **When it fires:** pre-execution, before the harness grants tool access or allows output
- **On violation:** block the action and log (default behavior), or escalate to Cockpit for approval if the tenant/global config allows escalation for that action type
- **Default behavior when no rule matches:** **deny and log.** Actions with no matching allow/deny rule are blocked. Workers must have explicit permission. This follows the same "structural over prompt" principle proven in the V10 voice agent.
- **Inputs:** compliance graph, industry pack rules, tenant config, current feature flags
- **Conflict resolution principle:** When the compliance graph returns contradictory rules, **most-restrictive-wins.** If one rule requires a disclosure and another forbids it for the same context, the action is blocked and escalated to Cockpit. This prevents the gate from silently choosing the permissive interpretation. The full conflict resolution rule set is a P1 TODO.

**Verification & Validation (V&V) detail:**

V&V checks every worker output after execution but before persistence or external action:

- **What it checks:** output format correctness, factual accuracy against knowledge graph, tone compliance with tenant config, safety (no forbidden claims, no PII leakage in outputs), booking/alert detail correctness
- **When it fires:** post-execution, before artifact persistence or external action (Cal.com booking, Twilio SMS, publish)
- **On failure:** block the output and log. Retry once with the original context + failure reason appended. If retry fails, escalate to Cockpit with the failed output attached for human review.
- **Distinction from Policy Gate:** The Policy Gate fires *before* execution and checks whether the action is *permitted*. V&V fires *after* execution and checks whether the output is *correct and safe*. Both must pass for work to reach users or external systems.

### 5d. Context & Memory

**Context Management detail:**

For each worker run, the harness assembles context from multiple sources. Priority order when context exceeds the model window:

1. Worker spec (mission, scope, tools) — always included
2. Active task/job context — always included
3. Tenant config — always included for tenant-scoped runs
4. Relevant industry pack sections — included, compacted if needed
5. Knowledge graph nodes (pulled by relevance) — progressive disclosure, summarized first
6. Memory & retrieval results — included up to budget
7. Historical context — compacted or dropped first

Compaction reduces lower-priority sources before higher-priority ones. The harness manages the context budget; workers do not assemble their own context.

### 5e. Error Philosophy & Observability

**Error philosophy:**

1. **No silent failures** — every error must be logged with full context: worker, tenant, job, action attempted, and error detail
2. **Fail loud, not fail silent** — if in doubt, block the action and surface to Cockpit rather than swallowing the error
3. **LLM output validation** — all LLM responses go through V&V before being treated as actionable; malformed, empty, or refusal responses are retried once, then escalated
4. **Partial state is the enemy** — multi-step operations (tenant onboarding, job replacement) must be atomic or have explicit rollback/cleanup

**Trace data classification:**

Traces contain customer PII (names, phone numbers, addresses, service requests from call transcripts). Before sending to LangSmith: (1) redact or hash direct identifiers (name, phone, address), (2) tag traces with data classification level, (3) apply tenant-scoped retention policies. Traces are governed by the same artifact governance rules (Section 20).

---

## 6. Decision: Tool Governance

**Model:** Authored → Validated → Granted

| Stage | What happens | Where |
|-------|-------------|-------|
| **Authored** | Worker spec declares `tools_allowed` — the tools this worker is designed to use | Worker spec YAML |
| **Validated** | CI/lint gate checks the spec against global policy; blocks merge if conflicts exist | Authoring-time (CI) |
| **Granted** | Harness resolves what's actually available for this run, this tenant, this environment | Runtime (harness) |

**Rules:**

- `tools_allowed` is an authored capability contract, not a wishlist
- Validation is a *process* (CI gate), not a stored field — avoids staleness
- `tools_granted` is resolved at runtime and never persisted in the spec
- `approval_boundaries` follow the same authored → validated → enforced pattern
- Runtime policy is always authoritative over authored specs

---

## 7. Durable Workspace / Artifact Layer

Where agents externalize work. Every agent operation that produces lasting output needs a place to put it.

**Contains:**

| Surface | Purpose |
|---------|---------|
| Git repositories | Code, config, prompt files, knowledge graph files |
| Sandbox filesystem | Ephemeral working space within E2B sandboxes |
| Artifact / log store | Generated reports, summaries, analysis outputs |
| Reporting docs | Human-readable summaries and dashboards (not the sole source of truth for raw artifacts) |
| Planning documents | Specs, implementation plans, experiment designs |

**Artifact governance:**

| Rule | Detail |
|------|--------|
| **Access control** | Tenant-scoped artifacts are readable only by the originating tenant's workers, Tenant Ops, and Cockpit. Internal artifacts (company-wide reports, experiment results) are readable by internal workers and Cockpit. |
| **Retention** | Tenant artifacts follow tenant-scoped retention policies (configurable per tenant). Internal artifacts follow a global retention policy. Ephemeral sandbox files are deleted on sandbox teardown. |
| **Registry of record** | Git is the primary artifact registry for version-controlled outputs (code, configs, knowledge, plans). Supabase is the registry for structured data artifacts (reports, job results, eval scores). The artifact/log store (TBD: S3, Supabase storage, or equivalent) handles binary/large-file artifacts. |
| **Lifecycle** | Created → Active → Archived → Deleted. Artifacts are never silently deleted; archival requires explicit action or retention policy expiry. |
| **Auditability** | Every artifact records: `created_by` (worker/job), `tenant_id` (or `internal`), `created_at`, `source_job_id`, and `artifact_type`. |

**Design principle:** Artifacts are the durable record of agent work. If a worker produces something, it should be retrievable, auditable, and scoped to the tenant or internal context that produced it. Artifacts inherit tenant/internal access boundaries and retention rules. Ephemeral work (sandbox scratch files) is acceptable, but any output that informs decisions or reaches users must be persisted.

---

## 8. Knowledge Substrate

The structured knowledge layer under the entire system. Not primarily a transactional database — a curated graph of interconnected markdown/YAML nodes with explicit relationships.

**Graphs:**

| Graph | Scope |
|-------|-------|
| Company graph | Business model, strategy, team, goals |
| Product graph | Features, roadmap, architecture, dependencies |
| Industry graphs | Per-trade: HVAC, Plumbing, Rooter, future verticals |
| Compliance graph | Regulations, required disclosures, forbidden claims, licensing |
| Customer insight graph | Patterns from calls, feedback, churn signals, satisfaction |

**Worker Spec Library** (`knowledge/worker-specs/`)

Canonical internal worker definitions. Each file uses the Standard Worker Schema. Authored by humans, informed by reference material (e.g., `agency-agents`), owned by this repo.

**Skill Packs** (`knowledge/skill-packs/`)

Reusable domain method libraries organized by function (pm/, seo/, content/, research/, compliance/). These are *what workers invoke*, not who workers are. Skill packs are reusable across workers; they are not owned by a single role. Informed by reference material (e.g., `phuryn/pm-skills`), owned by this repo. Note: `skill-packs/compliance/` contains *methods for applying compliance rules* (e.g., checking workflows, audit procedures); the Compliance Graph in the Knowledge Substrate contains the *rules themselves* (regulations, forbidden claims, disclosures). The skill pack queries the graph; it does not duplicate it.

**Implementation:**

- Markdown files with YAML/frontmatter metadata
- Wiki links in prose for explicit relationships
- MOCs (Maps of Content) / index files for navigation
- Progressive disclosure (summary → detail)
- Ownership + freshness metadata on every node

**Trust levels:** Not all graph nodes are equal. Hand-curated graphs (company, product, compliance) are trusted input. Graphs derived from external or user-generated content (customer insight graph, built from call transcripts) must be treated as untrusted and pass through the customer-derived content pipeline before influencing agent behavior.

**Customer-derived content pipeline:**

Customer-derived content is untrusted input. Raw transcripts, summaries, and extracted insights must never be injected directly into agent prompts or policy decisions. Content passes through three states:

| State | Examples | Trust | Rules |
|-------|----------|-------|-------|
| **Raw** | Transcript, message, call notes | Never trusted | Never directly injected into worker context or policy decisions. Stored as-is for audit/provenance. |
| **Sanitized** | Neutralized transcript | Low trust | Instruction-like or adversarial content neutralized. Normalized into safe intermediate form. Not yet usable as knowledge input. |
| **Structured insight** | Claims, labels, patterns with provenance | Usable with limits | Explicit claims/labels/patterns with provenance back to raw source. Confidence/verification status assigned. Emits structured claims, not free-form prompt text. Separates factual observations from user requests/opinions. Safe to use as knowledge input with policy limits. |

Only structured insights may influence agent behavior, and only through the normal context assembly pipeline (Section 5) where they are lower-priority than curated knowledge. This prevents data poisoning through adversarial caller content.

**Structured insight example:**

```yaml
# Example: structured insight extracted from a call transcript
insight_id: "ins_20260312_abc123"
source:
  type: "call_transcript"
  call_id: "call_xyz789"
  tenant_id: "tenant_acme_hvac"
  timestamp: "2026-03-12T14:30:00Z"
claim: "Customer reports AC unit making grinding noise after recent filter replacement"
category: "symptom_report"
confidence: 0.85
verification_status: "unverified"  # unverified | verified | disputed
separations:
  factual_observation: "AC unit making grinding noise"
  customer_request: "Wants same-day service"
  customer_opinion: "Thinks filter was installed wrong"
provenance_chain:
  raw_transcript_id: "raw_20260312_abc123"
  sanitization_run_id: "san_20260312_def456"
  extraction_model: "claude-sonnet-4.6"
  extraction_run_id: "run_20260312_ghi789"
```

**Retrieval & Caching:** At scale, reading and parsing markdown files per worker run will be slow. Two complementary mechanisms address this:

1. **Retrieval engine (evaluate in Phase 1):** QMD (github.com/tobi/qmd) or equivalent local hybrid search engine. Indexes markdown/YAML knowledge graph files into SQLite with BM25 full-text + optional vector semantic search + LLM re-ranking. Runs locally alongside the harness (Node.js/Bun, no cloud dependency). Collections map to graph categories (company, product, compliance, industry packs). MCP server mode integrates directly with the harness tool registry. Evaluate during Phase 1 Knowledge Substrate buildout — this determines how Section 5d item 5 ("knowledge graph nodes pulled by relevance") actually works at runtime.

2. **Cache layer (Redis):** Hot-path caching for frequently accessed graph nodes. Cache keys must be namespace-scoped by tenant where applicable, consistent with the tenant isolation principle (Section 13) — a cache key collision between tenants could serve wrong industry/compliance data. The invalidation mechanism must ensure compliance and policy graph nodes are never stale beyond a defined threshold (invalidated on every deploy, not TTL-based).

The retrieval engine handles *finding the right nodes*; the cache handles *serving them fast on repeat access*. The context management priority ordering (Section 5) describes *what* to include; retrieval + caching determines *how* it's available. Performance targets for graph reads and context assembly are TBD pending baseline measurements from Phase 1 implementation.

**Design principle:** Knowledge graphs are the system's curated shared knowledge substrate. They are read by workers, the policy gate, industry packs, and the eval layer. They are not the orchestrator — they inform it.

---

## 9. Decision: Standard Worker Schema

Every internal worker is defined by a YAML spec in `knowledge/worker-specs/`.

**Schema:**

```yaml
# knowledge/worker-specs/{worker-name}.yaml

# --- Required ---
mission: ""            # What this worker exists to do
scope: ""              # Boundaries of responsibility
execution_scope: ""    # "internal" or "tenant-bound" — where this worker operates
inputs: []             # What it receives to do its work
outputs: []            # What it produces
tools_allowed: []      # Tools this worker is designed to use
success_metrics: []    # How to measure if this worker is effective
approval_boundaries: [] # Actions requiring human/cockpit approval
                        # Valid: list of actions, or "inherits_global_policy"

# --- Recommended ---
job_creation: ""       # Whether this worker can spawn async/scheduled jobs
                       # Valid: "sync_only", "async_allowed", "scheduled_allowed", or "all"
                       # Default assumption if omitted: "sync_only"

# --- Optional ---
escalation_rules: ""     # When/how to escalate
                         # Valid: description, "none", or omitted
linked_skill_packs: []   # Skill packs this worker can invoke
                         # Valid: list of pack paths, or omitted
```

**Field tiering:**

| Tier | Fields | Rule |
|------|--------|------|
| **Required** | mission, scope, execution_scope, inputs, outputs, tools_allowed, success_metrics, approval_boundaries | Absence makes the worker unsafe, ambiguous, or unusable by the eval/governance layer |
| **Recommended** | job_creation | Should exist for workers that dispatch work; `sync_only` assumed if omitted |
| **Optional** | escalation_rules, linked_skill_packs | Include only when they reflect real behavior |

Required fields must contain either a real value or an explicit debt marker such as `not_yet_defined`; silent omission is not allowed.

Note: `inputs` and `outputs` are string arrays for now; they may evolve into typed objects as implementations mature.

**Anti-patterns:**

- No placeholder prose ("escalate when needed", "success means doing a good job")
- No personality descriptions — workers are workflows, not characters
- No duplicate/overlapping specialists until evals prove differentiation helps
- `agency-agents` is reference material for authoring, never a runtime dependency

---

## 10. Decision: Worker Specs vs Skill Packs

**Worker spec** = who this worker is and how it operates (identity + authority)

**Skill pack** = methods and frameworks this worker can invoke (capability)

**Directory structure:**

```
knowledge/
  worker-specs/
    product-manager.yaml
    engineer.yaml
    designer.yaml
    product-marketer.yaml
    customer-analyst.yaml
  skill-packs/
    pm/
    seo/
    content/
    research/
    compliance/
references/
  upstream/
    agency-agents/       # Snapshot/notes, not imported at runtime
    phuryn-pm-skills/    # Snapshot/notes, not imported at runtime
```

**Rules:**

- This repo is the canonical source of truth for all worker specs and skill packs
- Upstream repos are reference inputs, never runtime dependencies
- No automatic build-time syncing from upstream
- `references/upstream/` is for snapshots, notes, and source review only; nothing in this directory is loaded at runtime
- Initial specs are hand-authored (5 workers don't justify import tooling)

---

## 11. Shared Product Core

The industry-agnostic product that every trade and every client uses. Currently implemented as Express V2 (backend) + Next.js (dashboard) + Supabase (database).

**Contains:**

- Voice runtime (Retell AI — see Section 0)
- Web application (Next.js dashboard)
- Backend API (Express V2)
- Auth & permissions
- Billing
- Notifications (Twilio SMS)
- Logging (Pino)
- Booking (Cal.com)
- Reporting shell
- APIs
- Shared workflow framework

**Design principle:** This is the actual software product. Everything above it (harness, delivery, cockpit) makes it safe and smart. Everything below it (industry packs, tenant configs) makes it specific. The core stays trade-neutral. The core contains shared product capabilities, not trade logic, tenant policy, or worker-specific behavior.

---

## 12. Industry Pack Layer

The right abstraction for serving multiple trades from one platform.

**Current packs:** HVAC, Plumbing, Rooter

**Future:** Electrical, Roofing, Pest, etc.

**Each pack contains:**

- Terminology and service taxonomy
- Urgency logic
- Booking logic
- Scripts and objection handling
- Follow-up patterns
- Trade-specific reporting logic
- Trade-specific compliance nuances

**Pack format and directory structure:**

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
  plumbing/
    ...
  rooter/
    ...
```

**Pack manifest (`pack.yaml`) schema:**

```yaml
name: "hvac"
version: "1.0.0"
trade: "HVAC"
description: "Heating, ventilation, and air conditioning"
extends: []                # Other packs this one builds on (empty for base trades)
requires_compliance: true  # Whether this pack has trade-specific compliance rules
smart_tag_count: 117       # For the HVAC pack, migrated from V2
```

**Runtime loading:** The harness loads the active industry pack for a tenant by reading `tenant_config.industry_pack_id`, resolving the pack directory, and including relevant pack sections in the context assembly pipeline (Section 5d). Pack files are cached in Redis (Section 8) and invalidated on deploy.

**Design principle:** Industry packs are primarily configuration, knowledge, and bounded workflow variants — not separate codebases. They extend the shared core with trade-specific behavior. Adding a new trade should mean adding a new pack, not forking the product.

---

## 13. Tenant Config / Isolation

Each client gets a private config and namespace within the platform.

**Per tenant:**

| Category | Fields |
|----------|--------|
| Identity | `tenant_id`, `tenant_name`, `industry_pack_id`, brands served |
| Operations | Service area, pricing rules, hours, offers/promotions |
| Voice/Tone | Tone/brand instructions, disclosures |
| Governance | Allowed tools, escalation contacts |
| Isolation | Memory scope, trace namespace, eval namespace |

**Instance formula:**

> `shared product core` + `one industry pack` + `one tenant config` = client instance

**Data isolation mechanism:**

Defense-in-depth with two layers:

1. **Row-Level Security (RLS)** — Supabase RLS policies on all tenant-scoped tables enforce `tenant_id` filtering at the database level. This is the primary isolation boundary. RLS policies are applied even when using the service role key (harness operations), using `set_config('app.current_tenant', tenant_id)` at the start of each harness operation.
2. **Application-layer filtering** — All queries include explicit `WHERE tenant_id = ?` as a secondary safeguard. This catches cases where RLS is misconfigured or bypassed.

Cross-tenant data access is never permitted at the application layer. The only exception is the Cockpit's cross-tenant administrative view, which uses a dedicated admin role with explicit RLS bypass and audit logging.

| Scope | Isolation mechanism |
|-------|-------------------|
| Database (Supabase) | RLS policies + app-layer `tenant_id` filtering |
| Cache (Redis) | Tenant-namespaced cache keys (Section 8) |
| Traces (LangSmith) | Tenant-scoped trace tags and retention |
| Evals (LangSmith) | Tenant-scoped eval datasets and experiments |
| Artifacts | `tenant_id` metadata on all artifacts (Section 7) |
| Knowledge graphs | Shared graphs (company, product, compliance) are read-only for tenants; customer insight graphs are tenant-scoped |

**Design principle:** Tenants are lightweight configurations with isolated namespaces, not bespoke systems. If persistent memory is added later, it must be scoped tightly per tenant (using fields like `tenant_id`, `agent_id`, `run_id`) to prevent cross-tenant leakage.

---

## 14. Internal Workforce

Internal company workers used as specialist workflows/subgraphs, not wandering personalities.

**Initial workers:**

| Worker | Mission (brief) |
|--------|----------------|
| Product Manager | Prioritization, roadmap decisions, feature specs |
| Engineer | Implementation, code quality, technical decisions |
| Designer | UX/UI decisions, design system |
| Product Marketer | Positioning, messaging, go-to-market |
| Customer Analyst | Call patterns, churn signals, satisfaction insights |

**Pattern:** Supervisor + specialists (LangGraph multi-agent), not committee consensus.

**Supervisor:** The supervisor is a **harness-level routing construct**, not a sixth worker with a persona. It is implemented as the top-level LangGraph graph that receives tasks, determines which specialist worker(s) to invoke, and routes results. It does not have a worker spec, a mission statement, or a personality — it is the orchestration logic of the harness applied to the workforce. Its behavior is governed by the harness policy gate and traced via LangSmith like any other harness operation.

**Rules:**

- Each worker is defined by a Standard Worker Schema spec in `knowledge/worker-specs/`
- Workers may share skill packs, but may not share primary mission ownership
- No new worker is added without a clear mission that doesn't overlap existing workers
- No worker is promoted from spec to active use without eval coverage for its `success_metrics`
- Start with 5. Earn more through measured improvement, not role imagination.

---

## 15. Delegation & Job Layer

How workers dispatch and manage async and scheduled work.

**Three delegation modes:**

| Mode | Behavior | Implementation |
|------|----------|---------------|
| **Sync** | Do this and wait | LangGraph in-graph/subgraph |
| **Async** | Go do this and report back | Inngest durable functions |
| **Scheduled** | Do this later with fresh state | Inngest (`step.sleep()`, `step.sleepUntil()`, `step.sendEvent()`) |

Scheduled jobs execute against current state at run time, not the state that existed when they were scheduled.

**Job capabilities:**

- Task handles / status lookup
- Cancel
- Replace (first-class: mark old as superseded, create new, link together)
- Concurrency limits
- Budget limits
- Retry / retry policy
- **Idempotency keys** — required for all jobs that trigger external side effects (bookings via Cal.com, SMS alerts via Twilio, email sends, publish actions). Inngest supports idempotency keys natively. Without idempotency, a retried or duplicated job could create duplicate bookings or duplicate emergency alerts.
- Approval gates for user-facing or risky work

---

## 16. Decision: Job Ownership & Task Handles

**Job metadata:**

| Field | Purpose |
|-------|---------|
| `job_id` | Identity |
| `tenant_id` | Isolation |
| `origin_worker_id` | Ownership |
| `origin_run_id` | Provenance |
| `job_type` | Classification |
| `status` | Lifecycle |
| `supersedes_job_id` | Lineage (links replaced jobs) |
| `source_call_id` | Correlation — links to originating Retell voice call when applicable (enables tracing from call → job → artifact) |
| `created_at` | Temporal |
| `updated_at` | Temporal |

**Permission model:**

| Operation | Who can do it |
|-----------|--------------|
| **Status lookup** | Origin worker, Founder Cockpit, Tenant Ops, harness-granted readers |
| **Cancel** | Origin worker, Founder Cockpit, Tenant Ops |
| **Replace** | Origin worker, Founder Cockpit, Tenant Ops |

**Rules:**

- Job ownership is the default permission boundary
- Replace is a first-class operation, not manual cancel + create
- `supersedes_job_id` maintains audit trail across replacements
- Other workers can only inspect jobs if their worker spec includes `job_read` in `tools_allowed` and the harness grants it at runtime (this is what "harness-granted readers" means in the permission model above)
- Administrative override actions must be logged with actor identity and reason

---

## 17. Tenant Operations Layer

Sits between internal workforce and client instances. Tenant Operations is an **operational system managed by the Agent Harness**, not a worker agent. It is a set of harness-orchestrated workflows and automations, not an autonomous agent with a persona.

**Responsibilities:**

- Client onboarding
- Assigning industry packs
- Loading tenant configs
- Applying inherited policy rules
- Provisioning automations
- Monitoring client health
- Routing escalations
- Safe deployment/release controls per tenant

**Client onboarding workflow:**

```
  ONBOARDING STEPS:
  1. Create tenant record ──▶ Supabase (tenant_id, tenant_name, contact)
  2. Assign industry pack ──▶ Validate pack exists, set tenant_config.industry_pack_id
  3. Load tenant config    ──▶ Populate defaults from industry pack, allow overrides
  4. Apply RLS policies    ──▶ Ensure tenant_id RLS is active on all tenant-scoped tables
  5. Provision automations ──▶ Set up Inngest scheduled jobs (follow-ups, reports)
  6. Configure voice agent ──▶ Create/assign Retell agent with tenant-specific metadata
  7. Verify isolation      ──▶ Automated check: can this tenant see other tenants' data? (must fail)
  8. Cockpit notification  ──▶ Alert founder that new tenant is provisioned

  ON FAILURE AT ANY STEP:
  Roll back all completed steps. Tenant record marked as "onboarding_failed" with
  failure step and error. Cockpit alerted. No partial tenant state left active.
```

**Required inputs for onboarding:** `tenant_name`, `industry_pack_id`, `contact_email`, `service_area`. Missing any required input → reject onboarding and surface error.

**Governance:** Tenant Ops workflows execute under the harness with the same tool governance, policy gate, and tracing as any worker. Administrative actions (e.g., reassigning an industry pack, modifying tenant config) require Cockpit approval and are logged with actor identity and reason.

**Design principle:** It manages tenant lifecycle, provisioning, and operational health without becoming part of tenant-facing product behavior. It is infrastructure, not an agent role.

---

## 18. Evaluation Layer

Evals at three levels, powered by LangSmith datasets, evaluators, and experiments.

| Level | Question |
|-------|----------|
| **Core** | Does the shared product still work? |
| **Industry** | Does HVAC/Plumbing/Rooter still work? |
| **Tenant** | Does this specific client's configured behavior still work? |

**Eval targets:**

- Lead routing accuracy
- Booking logic correctness
- Tone compliance
- Objection handling quality
- Summary quality
- Publish/send safety
- Reporting quality
- Worker `success_metrics` (from Standard Worker Schema)

**Two testing concerns:**

| Concern | Tool | What it covers |
|---------|------|---------------|
| **Behavioral evals** | LangSmith datasets + evaluators | AI output quality: lead routing accuracy, tone compliance, summary quality, booking correctness, worker success_metrics |
| **Infrastructure tests** | Vitest (or equivalent) | Harness correctness: policy gate logic, context assembly priority ordering, tool governance pipeline, job lifecycle (create/cancel/replace), tenant isolation, idempotency key behavior, cache key scoping |
| **Resilience tests** | Vitest with mocked service failures | Degradable component fallback behavior (Redis down → file reads, LangSmith down → Pino fallback), blocking component error surfacing (LangGraph down → all work stops with visible error, LiteLLM down → immediate error), stale job detection when Inngest is unavailable |

Behavioral evals answer "does the AI do the right thing?" Infrastructure tests answer "does the harness machinery work correctly?" Resilience tests answer "does the system degrade gracefully when dependencies fail?" All three are required. Evals passing while harness infrastructure is broken is a silent failure.

**Eval data sourcing:**

| Source | Use | Notes |
|--------|-----|-------|
| **Synthetic test cases** | Infrastructure tests, policy gate logic, tenant isolation | Hand-written, deterministic, no PII concerns |
| **Anonymized production data** | Behavioral evals (lead routing, booking, summary quality) | Derived from real call transcripts via the customer content pipeline (Section 8). PII redacted before use in eval datasets. Subject to tenant consent and retention policies. |
| **Hand-curated golden examples** | Critical path evals, baseline comparisons | Founder-reviewed examples of correct behavior for each eval target. Minimum: 10 golden examples per eval target before first worker activation. |

**Minimum viable eval suite (for first worker activation):**

Before any worker is promoted from spec to active use, the following minimum coverage must exist:
- At least 10 golden examples per `success_metric` in the worker's spec
- Infrastructure tests covering the policy gate, context assembly, and tool governance for that worker's `tools_allowed`
- One resilience test per blocking dependency (LangGraph, LiteLLM) and one per degradable dependency the worker uses

**Design principle:** No worker is promoted to active use without eval coverage. No industry pack or tenant config change ships without passing its eval tier. Eval coverage should exist before promotion to active use, even if the initial suite is narrow. Evals are the gate between "this seems right" and "this works."

---

## 19. Improvement Lab

Offline or pre-production improvement harness for systematic product improvement. This is where Karpathy's autoresearch ideas belong — not in the live runtime.

**Process:**

1. Propose a small change
2. Mutate one bounded surface
3. Run a fixed-budget experiment
4. Score against a baseline metric **using the same LangSmith evaluators from the Evaluation Layer** (this ensures experiments and promotions are measured by the same standard)
5. Keep or discard the change
6. Log the result

**Good mutation targets:**

- Prompt files
- Workflow nodes
- Script variants
- Copy variants
- Threshold rules
- Industry-pack logic

**Experiment isolation:** Only one experiment may mutate a given surface at a time. If two experiments target the same prompt file or workflow node, they must run sequentially, not concurrently. This prevents conflicting mutations from producing meaningless results. The Lab should maintain a simple lock registry of surfaces currently under experiment. Locks must have a TTL or heartbeat to prevent stale locks from permanently blocking a surface (e.g., process crash after acquiring lock). The Cockpit can force-release stale locks.

**Design principle:** The Improvement Lab is a product improvement system, not part of the main app architecture. The Improvement Lab may propose changes, but it cannot directly promote them to production. Changes that survive experiments are promoted through the Safe Delivery Layer like any other change.

---

## 20. Governance Summary

| Principle | Rule |
|-----------|------|
| Tool access | Authored → Validated (CI) → Granted (runtime) |
| Approval boundaries | Same authored → validated → enforced pattern |
| Job ownership | Origin worker manages its own jobs; Cockpit/Ops have admin override |
| Worker creation | No new worker without non-overlapping mission + eval coverage |
| Knowledge authority | This repo owns all specs and skill packs; upstream is reference only |
| Deployment | All changes through Safe Delivery promotion gates |
| Tenant isolation | Scoped memory, traces, evals, configs — no cross-tenant leakage |
| Artifact governance | Persisted outputs inherit tenant/internal access controls and retention rules |
| Worker inter-visibility | Workers cannot read other workers' job status unless `job_read` is in their `tools_allowed` and granted by the harness |

---

## 21. What Is Explicitly Not Core

Do not make these foundational right now:

- **Symphony** — coding-work orchestration, optional later
- **Hermes Agent as production runtime** — useful as internal operator harness, not core
- **Broad multi-agent committee consensus** — use supervisor + specialists
- **Multiple memory systems at once** — one memory approach, well-scoped
- **A different flagship model per worker** — Claude Sonnet 4.6 is primary for all
- **Autonomous self-modification in production** — improvements go through the Lab
- **`agency-agents` as infrastructure** — reference material only
- **Automatic upstream sync from reference repos** — one-time distillation is fine, live sync is not
- **Dozens of specialist roles before evals prove they help**
- **Personality-first design over workflow-first design**

---

## 22. Stack Reference

| Category | Components |
|----------|-----------|
| **Voice runtime** | Retell AI (10-state FSM, LLM-driven transitions, GPT-4o) |
| **Agent harness** | LangGraph, LangSmith, Claude Sonnet 4.6 (or current best Anthropic model), Ollama, LiteLLM, Redis, Qdrant/semantic cache, E2B, Stagehand |
| **Application database** | Supabase (PostgreSQL + realtime) |
| **Product core** | Express V2 (Node.js/TypeScript), Next.js 16 (React 19) |
| **Integrations** | Cal.com (booking), Twilio (SMS alerts), Retell AI webhooks |
| **Safe delivery** | Vercel (dashboard), Render (backend), Retell API (voice agent config) |
| **Delegation/jobs** | LangGraph subgraphs (sync), Inngest (async/scheduled, handles, cancel/replace, idempotency) |
| **Knowledge** | Markdown/YAML graphs, MOCs, wiki links, frontmatter metadata, worker specs, skill packs |
| **Quality** | LangSmith evals (core/industry/tenant), Vitest (existing test suite), autoresearch-style Improvement Lab |

---

## 23. Open Questions

**Non-blocking for Phase 1** (resolve when needed):

1. **Persistent memory provider** — Mem0 or alternative? Deferred until tenant memory scope is needed.
2. **Semantic cache threshold** — When does repetition justify Qdrant over Redis? Needs usage data. When this is resolved, also evaluate multimodal embedding models (e.g., Gemini Embedding 2) for unified text + audio retrieval — call audio carries urgency/sentiment signal that transcripts drop. Not needed until vector search is justified.
3. **Skill pack granularity** — How large should a single skill pack be? TBD as first packs are authored.
5. **Improvement Lab cadence** — How often do experiment loops run? What's the fixed budget? Lab is Phase 3+.

**Resolved:**

4. **Minimum viable eval suite** — Resolved in Section 18: 10 golden examples per success_metric, infrastructure tests for policy gate / context assembly / tool governance, one resilience test per dependency the worker uses.
6. **Artifact registry of record** — Resolved in Section 7: Git for version-controlled outputs (code, configs, knowledge, plans); Supabase for structured data artifacts (reports, job results, eval scores); TBD object store (S3, Supabase storage) for binary/large-file artifacts.

---

## 24. Implementation Phasing

Build sequence organized by dependency. Each phase produces a deployable, testable increment.

```
  DEPENDENCY GRAPH:

  Phase 1 (Foundation)
  ├── Knowledge Substrate (graphs, worker specs, skill packs)
  ├── Industry Pack format + HVAC extraction from V2
  ├── Tenant Config schema + RLS isolation
  └── Harness infrastructure (LangGraph + LiteLLM + Redis on Render)

  Phase 2 (Core Harness)                    depends on Phase 1
  ├── Policy Gate + compliance graph
  ├── Context assembly pipeline
  ├── Tool governance (authored → validated → granted)
  ├── Harness triggering (Express V2 → Inngest → Harness)
  ├── Return path (Harness → Supabase + Inngest events)
  └── First worker activation (Customer Analyst) + minimum eval suite

  Phase 3 (Full Operations)                 depends on Phase 2
  ├── V&V pipeline
  ├── Delegation & Jobs (async/scheduled via Inngest)
  ├── Tenant Operations (onboarding workflow)
  ├── Artifact governance + persistence
  ├── Remaining workers (PM, Engineer, Designer, Marketer)
  └── Cockpit alerting + kill switches

  Phase 4 (Improvement)                     depends on Phase 3
  ├── Improvement Lab (experiment isolation, lock registry)
  ├── Full eval coverage (all three tiers)
  ├── Customer content pipeline (Raw → Sanitized → Structured)
  └── Founder Cockpit (portfolio KPIs, experiment oversight)
```

**Phase 1: Foundation**

Goal: Establish the knowledge substrate, industry pack format, tenant isolation, and base harness infrastructure. No agent work runs yet — this phase builds what agents need to run.

| Deliverable | Section | Acceptance criteria |
|-------------|---------|-------------------|
| Knowledge graph directory structure | 8 | Markdown/YAML graphs for company, product, HVAC industry, compliance. MOCs and wiki links working. |
| Knowledge retrieval engine | 8 | Evaluate QMD or equivalent for hybrid search over knowledge graphs. Decision: adopt, adapt, or build custom. Indexed search returning relevant graph nodes for a test query within latency budget. |
| Worker specs (5 initial) | 9, 10 | All 5 workers defined in Standard Worker Schema. CI validation passing. |
| HVAC industry pack | 12 | 117 smart tags, 3 emergency tiers, service taxonomy extracted from V2 into pack format. |
| Tenant config schema | 13 | Schema defined in Supabase. RLS policies active on all tenant-scoped tables. |
| Harness infrastructure | 5a | LangGraph, LiteLLM, Redis deployed on Render. Health checks passing. |

**Phase 2: Core Harness**

Goal: The harness can receive an event from Express V2, assemble context, run a worker through the policy gate, and persist results. One worker (Customer Analyst) is live.

| Deliverable | Section | Acceptance criteria |
|-------------|---------|-------------------|
| Policy Gate | 5c | Deny-by-default working. Compliance graph reads. Conflict resolution (most-restrictive-wins). |
| Context assembly | 5d | Priority ordering correct. Compaction working. Budget enforced. |
| Harness triggering | 5b | Express V2 → Inngest → Harness flow working end-to-end. |
| Return path | 5b | Harness → Supabase writes + Inngest notification events. |
| Customer Analyst worker | 14 | Activated with minimum eval suite (10 golden examples per metric). |
| Service authentication | 5b | All integration points authenticated per service auth table. |

**Phase 3: Full Operations**

Goal: All workers active, tenant onboarding automated, async jobs running, full artifact governance.

**Phase 4: Improvement**

Goal: Improvement Lab, full eval coverage, customer content pipeline, Cockpit fully operational.

**Phasing principles:**
- Each phase is deployable independently — no phase depends on a later phase
- Express V2 continues handling all production traffic throughout; harness work is additive
- Feature flags (Section 4) gate new harness capabilities; partial phase completion is safe
- Phase boundaries are not hard walls — work can start on Phase N+1 items once their dependencies in Phase N are complete
