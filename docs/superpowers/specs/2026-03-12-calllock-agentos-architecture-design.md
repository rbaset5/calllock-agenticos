# CallLock AgentOS Architecture Spec

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

---

## 2. Architecture Hierarchy

```
Founder Cockpit
├── Safe Delivery Layer
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
├── Durable Workspace / Artifact Layer
├── Knowledge Substrate
│   ├── Company Graph
│   ├── Product Graph
│   ├── Industry Graphs
│   ├── Compliance Graph
│   ├── Customer Insight Graph
│   ├── Worker Spec Library
│   └── Skill Packs
├── Shared Product Core
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
- Kill switches and pause controls

**Design principle:** The Cockpit observes and approves. It does not perform routine delivery work. Workers propose; the Cockpit decides. This is the only layer with cross-tenant administrative override.

---

## 4. Safe Delivery Layer

Keeps coding agents and automated changes from breaking production. This layer governs changes to product code, configs, prompts, and other production-affecting artifacts.

**Components:**

- Vercel preview deployments (non-production branches and PRs)
- Vercel Flags (feature flags)
- Vercel Deployment Protection (project-level)
- Instant rollback (production deployments)
- Promotion-based release flow (preview → production via approval gates)
- Branch-safe test environments / branchable data where supported

**Design principle:** No automated change reaches production without passing through preview, protection, and promotion gates. This layer matters more than orchestration sophistication — a broken deploy costs more than a slow workflow.

---

## 5. Agent Harness Layer

The runtime operating system for all agent work. Consolidates orchestration, delegation, policy, tooling, and observability into one named layer.

**Contains:**

| Capability | Implementation |
|------------|---------------|
| Orchestration & State | LangGraph (graphs, subgraphs, checkpoints) |
| Delegation & Jobs | LangGraph subgraphs (sync) + Inngest (async/scheduled, handles, cancel/replace) |
| Tool Registry / MCP | Harness-managed tool access |
| Sandboxed Execution | E2B |
| Browser Automation | Stagehand |
| Context Management | Compaction, windowing, progressive disclosure |
| Memory & Retrieval | Tenant-scoped retrieval, cache, and optional persistent memory services |
| Policy / Compliance Gate | Centralized; reads from compliance graph + industry pack + tenant config |
| Verification & Validation | Pre-execution checks, post-execution quality gates |
| Tracing / Observability | LangSmith |
| Model Gateway | LiteLLM → Claude Sonnet 4.6 (primary) + Ollama (cheap/local triage) |

**Design principle:** The harness is the runtime enforcement point for what agents can do. Worker specs declare intent; the harness grants or denies at runtime based on tenant config, global policy, environment state, and current feature flags.

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

Reusable domain method libraries organized by function (pm/, seo/, content/, research/, compliance/). These are *what workers invoke*, not who workers are. Skill packs are reusable across workers; they are not owned by a single role. Informed by reference material (e.g., `phuryn/pm-skills`), owned by this repo.

**Implementation:**

- Markdown files with YAML/frontmatter metadata
- Wiki links in prose for explicit relationships
- MOCs (Maps of Content) / index files for navigation
- Progressive disclosure (summary → detail)
- Ownership + freshness metadata on every node

**Design principle:** Knowledge graphs are the system's curated shared knowledge substrate. They are read by workers, the policy gate, industry packs, and the eval layer. They are not the orchestrator — they inform it.

---

## 9. Decision: Standard Worker Schema

Every internal worker is defined by a YAML spec in `knowledge/worker-specs/`.

**Schema:**

```yaml
# knowledge/worker-specs/{worker-name}.yaml

# --- Required ---
mission: ""          # What this worker exists to do
scope: ""            # Boundaries of responsibility
inputs: []           # What it receives to do its work
outputs: []          # What it produces
tools_allowed: []    # Tools this worker is designed to use
success_metrics: []  # How to measure if this worker is effective

# --- Recommended ---
approval_boundaries: []  # Actions requiring human/cockpit approval
                         # Valid: list of actions, "inherits_global_policy", or "not_yet_defined"

# --- Optional ---
escalation_rules: ""     # When/how to escalate
                         # Valid: description, "none", or omitted
linked_skill_packs: []   # Skill packs this worker can invoke
                         # Valid: list of pack paths, or omitted
```

**Field tiering:**

| Tier | Fields | Rule |
|------|--------|------|
| **Required** | mission, scope, inputs, outputs, tools_allowed, success_metrics | Absence makes the worker unsafe, ambiguous, or unusable by the eval layer |
| **Recommended** | approval_boundaries | Should exist; `inherits_global_policy` or `not_yet_defined` are valid |
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

The industry-agnostic product that every trade and every client uses.

**Contains:**

- Voice runtime
- Web application
- Auth & permissions
- Billing
- Notifications
- Logging
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
- Other workers can only inspect or act on jobs if explicitly granted that authority by the harness
- Administrative override actions must be logged with actor identity and reason

---

## 17. Tenant Operations Layer

Sits between internal workforce and client instances.

**Responsibilities:**

- Client onboarding
- Assigning industry packs
- Loading tenant configs
- Applying inherited policy rules
- Provisioning automations
- Monitoring client health
- Routing escalations
- Safe deployment/release controls per tenant

**Design principle:** It manages tenant lifecycle, provisioning, and operational health without becoming part of tenant-facing product behavior.

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

**Design principle:** No worker is promoted to active use without eval coverage. No industry pack or tenant config change ships without passing its eval tier. Eval coverage should exist before promotion to active use, even if the initial suite is narrow. Evals are the gate between "this seems right" and "this works."

---

## 19. Improvement Lab

Offline or pre-production improvement harness for systematic product improvement. This is where Karpathy's autoresearch ideas belong — not in the live runtime.

**Process:**

1. Propose a small change
2. Mutate one bounded surface
3. Run a fixed-budget experiment
4. Score against a baseline metric
5. Keep or discard the change
6. Log the result

**Good mutation targets:**

- Prompt files
- Workflow nodes
- Script variants
- Copy variants
- Threshold rules
- Industry-pack logic

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
| **Core platform** | LangGraph, LangSmith, Claude Sonnet 4.6, Ollama, LiteLLM, Redis, Qdrant/semantic cache, E2B, Stagehand |
| **Safe delivery** | Vercel previews, Vercel Flags, Deployment Protection, rollback, promotion-based release flow |
| **Delegation/jobs** | LangGraph subgraphs (sync), Inngest (async/scheduled, handles, cancel/replace) |
| **Knowledge** | Markdown/YAML graphs, MOCs, wiki links, frontmatter metadata, worker specs, skill packs |
| **Quality** | LangSmith evals (core/industry/tenant), autoresearch-style Improvement Lab |

---

## 23. Open Questions

1. **Persistent memory provider** — Mem0 or alternative? Deferred until tenant memory scope is needed.
2. **Semantic cache threshold** — When does repetition justify Qdrant over Redis? Needs usage data.
3. **Skill pack granularity** — How large should a single skill pack be? TBD as first packs are authored.
4. **Minimum viable eval suite** — What is the minimum viable eval suite for first worker activation?
5. **Improvement Lab cadence** — How often do experiment loops run? What's the fixed budget?
6. **Artifact registry of record** — What is the first persistent artifact registry: git, object storage, docs layer, or a combination?
