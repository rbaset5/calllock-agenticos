# Phase 1: Foundation — Implementation Plan

Historical planning snapshot only. Canonical sequencing, readiness gates, and dependency order now live in `plans/whole-system-executable-master-plan.md`.

**Type:** Feature (Greenfield)
**Branch:** `rbaset5/agent-arch-spec` → new branch `phase1/foundation`
**Spec:** `docs/superpowers/specs/2026-03-12-calllock-agentos-architecture-design.md` (Section 24)
**Status:** Planning
**Created:** 2026-03-12

---

## Overview

Phase 1 establishes the knowledge substrate, industry pack format, tenant isolation, and base harness infrastructure for CallLock AgentOS. No agent work runs yet — this phase builds what agents need to run in Phase 2.

**Current state:** This repository (`cahokia`) contains only the architecture spec (1041 lines, 24 sections) and review TODOs. No application code, no dependencies, no directory structure exists. The production V2 backend lives in a separate repository.

**End state:** A deployable foundation with knowledge graphs populated, 5 worker specs validated by CI, HVAC industry pack extracted from V2, tenant isolation enforced via Supabase RLS, and harness infrastructure (LangGraph + LiteLLM + Redis) health-checking on Render.

---

## Architectural Decision: Harness Runtime Language

**Decision required before implementation begins.**

The spec says "LangGraph: Self-hosted (Node.js process)" in Section 5a, but LangGraph's primary SDK is Python. The existing V2 backend and Inngest SDK are TypeScript/Node.js.

| Option | Pros | Cons |
|--------|------|------|
| **A: Python harness (separate Render service)** | Full LangGraph API (checkpointing, multi-agent, LangSmith native), largest ecosystem of agent tooling | Two runtimes to maintain, cross-service HTTP/event communication |
| **B: LangGraph.js (Node.js, same runtime as V2)** | Single runtime, simpler deploy, shared types with Express V2 | LangGraph.js historically lags Python SDK in features; verify current parity |

**Recommendation:** Option A (Python) — the harness is a separate service anyway (per spec), and LangGraph Python has the mature checkpointing and eval integration the architecture requires. Express V2 communicates with it via Inngest events, not direct imports.

**This plan assumes Option A (Python harness).** If Option B is chosen, adjust the harness deliverables to use `@langchain/langgraph` instead.

---

## Dependency Graph

```
Phase 1 Dependency Graph
========================

  1. Project Scaffolding (no deps)
     ├── 2. Knowledge Substrate (depends on 1)
     │   ├── 2a. Directory structure + MOCs
     │   ├── 2b. Company & Product graphs
     │   ├── 2c. Compliance graph (file-based + Supabase-backed)
     │   └── 2d. CI validation (frontmatter, wiki links, freshness)
     │
     ├── 3. Worker Specs (depends on 1)
     │   └── 3a. 5 YAML specs + CI schema validation
     │
     ├── 4. HVAC Industry Pack (depends on 2a for directory structure)
     │   ├── 4a. Extract smart tags from V2
     │   ├── 4b. Extract emergency tiers from V2
     │   ├── 4c. Extract service taxonomy from V2
     │   ├── 4d. Author pack.yaml manifest
     │   └── 4e. CI pack validation
     │
     ├── 5. Tenant Config + RLS (depends on 1)
     │   ├── 5a. Supabase migration: tenants + tenant_configs tables
     │   ├── 5b. RLS policies with FORCE + set_config pattern
     │   ├── 5c. Tenant isolation verification test
     │   └── 5d. Compliance conflict resolution rule (P1 TODO)
     │
     └── 6. Harness Infrastructure (depends on 1, 5a)
         ├── 6a. LangGraph supervisor graph skeleton
         ├── 6b. LiteLLM proxy config + Render deploy
         ├── 6c. Redis config + namespace-scoped key helpers
         ├── 6d. Health check endpoints
         └── 6e. Render Blueprint (render.yaml)
```

**Parallelizable work streams:** Steps 2, 3, 4, 5, and 6 can proceed in parallel once Step 1 (scaffolding) is complete. Steps 2 and 4 share a dependency (directory structure) but can be authored concurrently.

---

## Step 1: Project Scaffolding

**Goal:** Establish the monorepo structure, tooling, and CI foundation.

### 1.1 Directory Structure

```
cahokia/
  .gitignore
  CLAUDE.md                         # Project conventions for AI assistants
  TODOS.md                          # (existing)
  README.md                         # (existing, expand)

  # Knowledge Substrate
  knowledge/
    _moc.md                         # Root Map of Content
    company/
    product/
    compliance/
    customer-insights/
    worker-specs/
    skill-packs/
    industry-packs/
      hvac/
    graphs/                         # Reserved for future graph DB exports

  # Harness (Python)
  harness/
    pyproject.toml
    requirements.txt
    src/
      harness/
        __init__.py
        state.py                    # HarnessState schema
        server.py                   # Health check + Inngest serve
        graphs/
          supervisor.py
          workers/
        nodes/
          context_assembly.py
          policy_gate.py
          verification.py
          persist.py
      cache/
        keys.py
        redis_client.py
      db/
        tenant_scope.py
      observability/
        pii_redactor.py
        langsmith_tracer.py
      knowledge/
        file_reader.py
        frontmatter_parser.py
        wiki_link_resolver.py
        pack_loader.py
    tests/

  # LiteLLM Proxy
  infra/
    litellm/
      config.yaml
      Dockerfile

  # Inngest Integration (TypeScript — runs in Express V2 context)
  inngest/
    package.json
    tsconfig.json
    src/
      client.ts
      events/
        schemas.ts
      functions/
        process-call.ts

  # Supabase
  supabase/
    migrations/
    seed.sql

  # CI & Scripts
  scripts/
    validate-knowledge.ts           # Frontmatter, wiki links, freshness
    validate-packs.ts               # Industry pack integrity
    validate-worker-specs.ts        # Worker schema compliance
    invalidate-cache.ts             # Deploy hook

  # Render
  render.yaml

  # Existing
  docs/superpowers/specs/           # (existing)
  .context/                         # (existing, gitignored)
  plans/                            # (this file)
```

### 1.2 CLAUDE.md

Create `CLAUDE.md` with project conventions:
- Monorepo layout (knowledge/ is YAML/Markdown, harness/ is Python, inngest/ is TypeScript)
- Every knowledge file requires frontmatter with `id`, `title`, `graph`, `owner`, `last_reviewed`, `trust_level`
- Wiki links use `[[path]]` syntax resolving to `knowledge/{path}.md`
- Industry packs must pass `scripts/validate-packs.ts` before merge
- RLS policies use `set_config('app.current_tenant', tenant_id)` pattern with transaction-local scope
- Compliance graph nodes are database-backed (Supabase), not file-based

### 1.3 .gitignore

```
node_modules/
.env
.env.*
__pycache__/
*.pyc
.venv/
dist/
.context/
*.egg-info/
```

### 1.4 CI Configuration

Set up GitHub Actions (or equivalent) with:
- `validate-knowledge`: runs `scripts/validate-knowledge.ts` on every PR touching `knowledge/`
- `validate-packs`: runs `scripts/validate-packs.ts` on every PR touching `knowledge/industry-packs/`
- `validate-worker-specs`: runs `scripts/validate-worker-specs.ts` on every PR touching `knowledge/worker-specs/`
- `harness-lint`: runs `ruff` + `mypy` on `harness/`
- `harness-test`: runs `pytest` on `harness/tests/`

### Acceptance Criteria

- [ ] Directory structure created matching the layout above
- [ ] CLAUDE.md documents all project conventions
- [ ] .gitignore prevents secrets and build artifacts from being committed
- [ ] CI pipeline runs validation scripts on PR

---

## Step 2: Knowledge Substrate

**Goal:** Populate the knowledge graph directory with company, product, compliance, and customer insight graphs. Establish MOC navigation and wiki-link conventions.

**Spec references:** Sections 8, 10

### 2a. Directory Structure + MOCs

Create `_moc.md` files in every knowledge directory. Each MOC:
- Has required frontmatter (`id`, `title`, `graph`, `owner`, `last_reviewed`, `trust_level`)
- Links to all child nodes via `[[wiki-links]]`
- Serves as the entry point for both human navigation and agent context assembly

### 2b. Company & Product Graphs

**`knowledge/company/`** — Minimum viable nodes:

| File | Content Source |
|------|---------------|
| `mission.md` | CallLock mission, vision, values |
| `business-model.md` | Revenue model, pricing, target market |
| `team.md` | Team structure, roles, responsibilities |
| `goals-2026.md` | Current year goals and OKRs |

**`knowledge/product/`** — Minimum viable nodes:

| File | Content Source |
|------|---------------|
| `architecture.md` | Summary of the architecture spec (link to full spec) |
| `features/voice-agent.md` | Retell AI V10, 10-state FSM, capabilities |
| `features/dashboard.md` | Next.js 16 dashboard, what it shows |
| `features/booking.md` | Cal.com integration, booking flow |
| `features/alerts.md` | Twilio SMS alerting, trigger conditions |
| `roadmap.md` | Product roadmap (link to canonical source) |
| `dependencies.md` | External service dependency map |

Each file must include `progressive_disclosure` frontmatter:
```yaml
progressive_disclosure:
  summary_tokens: 200    # for context assembly compaction
  full_tokens: 1500      # approximate full size
```

### 2c. Compliance Graph

**Dual storage:** The compliance graph is the one graph that needs **database backing** (per spec recommendation and P1 TODO). File-based nodes serve as the authored source; Supabase tables enable indexed conflict detection.

**`knowledge/compliance/`** — File-based source of truth:

| File | Content |
|------|---------|
| `regulations/hvac-licensing.md` | State-level HVAC licensing requirements |
| `regulations/general-disclosures.md` | Industry-agnostic disclosure rules |
| `forbidden-claims.md` | Claims agents must never make |
| `required-disclosures.md` | Disclosures required per call type |

**`supabase/migrations/003_compliance_graph.sql`** — Database-backed indexed graph:

```sql
CREATE TABLE compliance_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id TEXT NOT NULL UNIQUE,           -- e.g., "forbidden-claims/pricing"
  source_file TEXT NOT NULL,              -- path to authoritative markdown file
  rule_type TEXT NOT NULL CHECK (rule_type IN ('forbidden', 'required', 'conditional')),
  scope TEXT NOT NULL CHECK (scope IN ('global', 'industry', 'tenant')),
  industry_pack_id TEXT,                  -- null for global rules
  tenant_id UUID REFERENCES tenants(id),  -- null for non-tenant rules
  condition JSONB DEFAULT '{}',           -- when this rule applies
  action JSONB NOT NULL,                  -- what the rule requires/forbids
  priority INTEGER NOT NULL DEFAULT 0,    -- for conflict resolution ordering
  conflicts_with TEXT[] DEFAULT '{}',     -- explicit conflict declarations
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_compliance_scope ON compliance_rules(scope, industry_pack_id);
CREATE INDEX idx_compliance_type ON compliance_rules(rule_type);
CREATE INDEX idx_compliance_conflicts ON compliance_rules USING GIN(conflicts_with);
```

**Compliance conflict resolution rule (P1 TODO):**

When the compliance graph returns contradictory rules, apply **most-restrictive-wins**:
1. Query all applicable rules for the current context (scope + industry + tenant)
2. Check `conflicts_with` array for explicit contradictions
3. If conflicts exist: apply the rule with the highest `priority` value
4. If priority is equal: apply the most restrictive rule (forbidden > required > conditional)
5. Log the conflict resolution decision to LangSmith trace for audit
6. Surface to Cockpit if more than 3 conflicts detected in a single policy gate evaluation

### 2d. CI Validation

**`scripts/validate-knowledge.ts`:**

```typescript
// Validates:
// 1. All .md files in knowledge/ have required frontmatter fields
// 2. All [[wiki-links]] resolve to existing files
// 3. All _moc.md files exist in every directory
// 4. All last_reviewed dates are within 90 days (warn) or 180 days (error)
// 5. No orphan files (files not linked from any MOC)
```

### Acceptance Criteria

- [ ] Markdown/YAML graphs for company, product, HVAC industry, compliance populated
- [ ] MOCs and wiki links working (validated by CI)
- [ ] All frontmatter fields present and valid
- [ ] Compliance rules seeded in Supabase table with conflict detection indexes
- [ ] Conflict resolution rule documented and queryable

---

## Step 3: Worker Specs

**Goal:** Define all 5 initial workers in Standard Worker Schema format with CI validation.

**Spec references:** Sections 9, 10, 14

### 3a. Standard Worker Schema (YAML)

Create 5 worker spec files in `knowledge/worker-specs/`:

| Worker | File | Mission (from spec Section 14) |
|--------|------|------|
| Product Manager | `product-manager.yaml` | Prioritize roadmap, write specs, track metrics |
| Engineer | `engineer.yaml` | Implement features, fix bugs, maintain infra |
| Designer | `designer.yaml` | Create UI/UX designs, maintain design system |
| Product Marketer | `product-marketer.yaml` | SEO content, landing pages, customer comms |
| Customer Analyst | `customer-analyst.yaml` | Analyze calls, route leads, detect churn signals |

**Schema structure (Section 9):**

```yaml
# knowledge/worker-specs/customer-analyst.yaml
---
schema_version: "1"
worker_id: "customer-analyst"
version: "1.0.0"

# Required fields
mission: "Analyze completed calls to extract customer insights, route leads by urgency, and detect churn signals"
scope:
  can_do:
    - "Classify call outcomes (lead, support, complaint, emergency)"
    - "Route leads to appropriate booking flow based on urgency tier"
    - "Extract customer sentiment and satisfaction signals"
    - "Detect churn risk indicators from call patterns"
  cannot_do:
    - "Make outbound calls"
    - "Modify pricing or promotions"
    - "Access other tenants' call data"
    - "Override emergency tier classifications"

execution_scope:
  max_steps: 10
  timeout_seconds: 120
  model: "primary"            # LiteLLM model alias

inputs:
  - name: "transcript"
    type: "string"
    required: true
    description: "Redacted call transcript"
  - name: "smart_tags"
    type: "string[]"
    required: true
    description: "Smart tags matched from industry pack"
  - name: "emergency_tier"
    type: "enum(none, tier1, tier2, tier3)"
    required: true
  - name: "tenant_config"
    type: "TenantConfig"
    required: true

outputs:
  - name: "classification"
    type: "enum(lead, support, complaint, emergency, information)"
  - name: "routing_decision"
    type: "object"
    schema:
      destination: "enum(booking, dispatcher, owner_alert, no_action)"
      urgency: "enum(standard, urgent, emergency)"
      reasoning: "string"
  - name: "insights"
    type: "CustomerInsight[]"
  - name: "churn_risk_score"
    type: "float(0-1)"

tools_allowed:
  - "supabase_read"           # Read tenant's call history
  - "supabase_write"          # Write insights and classifications
  - "inngest_send"            # Emit follow-up events

success_metrics:
  - metric: "routing_accuracy"
    target: 0.95
    eval_dataset: "customer-analyst-lead-routing"
  - metric: "emergency_detection"
    target: 1.0               # zero tolerance for missed emergencies
    eval_dataset: "customer-analyst-emergency-detection"
  - metric: "churn_prediction_precision"
    target: 0.80
    eval_dataset: "customer-analyst-churn-signals"

approval_boundaries:
  auto_approve:
    - "classification"
    - "insights"
  requires_review:
    - "routing_decision where urgency=emergency"
  escalate_to_cockpit:
    - "churn_risk_score > 0.9"

# Recommended fields
dependencies:
  industry_pack: true         # requires active industry pack
  compliance_graph: true      # must check forbidden claims
  tenant_config: true         # needs tenant-specific routing rules
```

### 3b. CI Schema Validation

**`scripts/validate-worker-specs.ts`:**

```typescript
// Validates:
// 1. All required fields present (mission, scope, execution_scope, inputs, outputs, tools_allowed, success_metrics, approval_boundaries)
// 2. Schema version matches expected version
// 3. All tool references exist in the tool registry
// 4. All eval dataset references are valid dataset names
// 5. success_metrics targets are within valid ranges
// 6. No duplicate worker_ids
```

### Acceptance Criteria

- [ ] All 5 workers defined in Standard Worker Schema
- [ ] CI validation passing for all worker specs
- [ ] Each worker has at least 2 success_metrics with eval dataset references
- [ ] Approval boundaries defined for all output types

---

## Step 4: HVAC Industry Pack

**Goal:** Extract the 117 smart tags, 3 emergency tiers, and service taxonomy from the V2 backend into the industry pack format.

**Spec references:** Section 12
**P1 TODO:** "Extract HVAC logic from V2 backend into industry pack format" (Effort: L)

### 4a–4c. Extract from V2

**Prerequisite:** Access to the V2 Express.js codebase (separate repository). The hardcoded HVAC logic is expected in:
- Smart tag definitions (likely in a constants file, service, or database seed)
- Emergency tier logic (likely in a routing/classification module)
- Service taxonomy (likely in a constants or config file)

**Extraction process:**

1. **Audit V2 codebase** — Locate all HVAC-specific logic:
   - Search for smart tag arrays, enums, or constants
   - Search for emergency/urgency tier definitions
   - Search for service type categorizations
   - Search for booking rule logic tied to service types
   - Search for compliance/disclosure logic

2. **Map V2 structures to pack format:**
   - Smart tags → `knowledge/industry-packs/hvac/taxonomy.yaml`
   - Emergency tiers → `knowledge/industry-packs/hvac/urgency.yaml`
   - Compliance rules → `knowledge/industry-packs/hvac/compliance.yaml`
   - Booking logic → `knowledge/industry-packs/hvac/booking-rules.yaml`
   - Reporting templates → `knowledge/industry-packs/hvac/reporting.yaml`

3. **Author call scripts** — Convert V2 conversation flows to markdown:
   - `scripts/inbound-call.md` — Standard inbound call handling
   - `scripts/emergency-dispatch.md` — Emergency tier response
   - `scripts/booking-confirmation.md` — Booking confirmation flow

### 4d. Pack Manifest

```yaml
# knowledge/industry-packs/hvac/pack.yaml
name: "hvac"
version: "1.0.0"
trade: "HVAC"
description: "Heating, ventilation, and air conditioning"
extends: []
requires_compliance: true
smart_tag_count: 117            # must match actual count in taxonomy.yaml

files:
  - taxonomy.yaml
  - urgency.yaml
  - compliance.yaml
  - booking-rules.yaml
  - reporting.yaml
  - scripts/_moc.md
  - scripts/inbound-call.md
  - scripts/emergency-dispatch.md
  - scripts/booking-confirmation.md

schema_version: "1"
```

### 4e. CI Pack Validation

**`scripts/validate-packs.ts`:**

```typescript
// Validates:
// 1. pack.yaml exists and has all required fields
// 2. All files listed in pack.yaml exist on disk
// 3. smart_tag_count matches actual tag count in taxonomy.yaml
// 4. All emergency tiers have required fields (label, response_target, actions)
// 5. All smart tags have at least one alias
// 6. All markdown files have required frontmatter
// 7. No duplicate tag IDs within a pack
// 8. urgency tiers reference valid booking_types
```

### Acceptance Criteria

- [ ] 117 smart tags extracted and structured in taxonomy.yaml
- [ ] 3 emergency tiers defined with response targets and actions
- [ ] Service taxonomy organized by category (heating, cooling, IAQ, etc.)
- [ ] Pack manifest validates — all declared files exist, tag count matches
- [ ] CI pack validation passing
- [ ] Extraction provenance documented (`migrated_from: "express-v2-hardcoded"` in frontmatter)

---

## Step 5: Tenant Config + RLS

**Goal:** Define the tenant configuration schema in Supabase with Row Level Security policies enforcing tenant isolation.

**Spec references:** Sections 13, 17

### 5a. Supabase Migrations

**`supabase/migrations/001_tenants.sql`:**

```sql
CREATE TABLE tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_name TEXT NOT NULL,
  industry_pack_id TEXT NOT NULL,
  contact_email TEXT NOT NULL,
  service_area JSONB NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'onboarding'
    CHECK (status IN ('onboarding', 'active', 'suspended', 'onboarding_failed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**`supabase/migrations/002_tenant_configs.sql`:**

```sql
CREATE TABLE tenant_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  tone_instructions TEXT DEFAULT '',
  required_disclosures TEXT[] DEFAULT '{}',
  pricing_rules JSONB DEFAULT '{}',
  business_hours JSONB DEFAULT '{}',
  promotions JSONB DEFAULT '{}',
  allowed_tools TEXT[] DEFAULT '{}',
  escalation_contacts JSONB DEFAULT '{}',
  trace_namespace TEXT NOT NULL,
  eval_namespace TEXT NOT NULL,
  monthly_llm_budget_cents INTEGER DEFAULT 10000,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(tenant_id)
);

CREATE INDEX idx_tenant_configs_tenant ON tenant_configs(tenant_id);
```

**`supabase/migrations/004_jobs.sql`:**

```sql
CREATE TABLE jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  origin_worker_id TEXT NOT NULL,
  origin_run_id TEXT NOT NULL,
  job_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'superseded')),
  supersedes_job_id UUID REFERENCES jobs(id),
  source_call_id TEXT,
  idempotency_key TEXT,
  payload JSONB DEFAULT '{}',
  result JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_jobs_idempotency ON jobs(idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX idx_jobs_tenant_status ON jobs(tenant_id, status);
CREATE INDEX idx_jobs_source_call ON jobs(source_call_id) WHERE source_call_id IS NOT NULL;
```

### 5b. RLS Policies

**`supabase/migrations/005_rls_policies.sql`:**

```sql
-- Enable and FORCE RLS on all tenant-scoped tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_rules ENABLE ROW LEVEL SECURITY;

ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant_configs FORCE ROW LEVEL SECURITY;
ALTER TABLE jobs FORCE ROW LEVEL SECURITY;
ALTER TABLE compliance_rules FORCE ROW LEVEL SECURITY;

-- RLS function for setting tenant context
CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id UUID)
RETURNS void AS $$
BEGIN
  PERFORM set_config('app.current_tenant', p_tenant_id::text, true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Tenant isolation policies (transaction-local via set_config)
CREATE POLICY tenant_isolation ON tenants
  FOR ALL USING (id = current_setting('app.current_tenant', true)::uuid);

CREATE POLICY tenant_isolation ON tenant_configs
  FOR ALL USING (tenant_id = current_setting('app.current_tenant', true)::uuid);

CREATE POLICY tenant_isolation ON jobs
  FOR ALL USING (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- Compliance rules: global rules visible to all, tenant-scoped rules isolated
CREATE POLICY compliance_global_read ON compliance_rules
  FOR SELECT USING (scope IN ('global', 'industry'));

CREATE POLICY compliance_tenant_read ON compliance_rules
  FOR SELECT USING (
    scope = 'tenant'
    AND tenant_id = current_setting('app.current_tenant', true)::uuid
  );

-- Cockpit admin bypass
CREATE POLICY admin_bypass_tenants ON tenants
  FOR ALL USING (current_setting('app.role', true) = 'cockpit_admin');

CREATE POLICY admin_bypass_configs ON tenant_configs
  FOR ALL USING (current_setting('app.role', true) = 'cockpit_admin');

CREATE POLICY admin_bypass_jobs ON jobs
  FOR ALL USING (current_setting('app.role', true) = 'cockpit_admin');
```

### 5c. Tenant Isolation Verification Test

```python
# harness/tests/test_tenant_isolation.py
#
# Creates two test tenants, inserts data for each, verifies:
# 1. Tenant A cannot read Tenant B's rows
# 2. Tenant A cannot write to Tenant B's tables
# 3. Admin bypass can read all tenants
# 4. Without set_config, all queries return empty (deny-by-default)
```

### 5d. Compliance Conflict Resolution (P1 TODO)

Implement as a Supabase function:

```sql
-- supabase/migrations/006_compliance_conflict_resolution.sql

CREATE OR REPLACE FUNCTION resolve_compliance_conflicts(
  p_scope TEXT,
  p_industry_pack_id TEXT DEFAULT NULL,
  p_tenant_id UUID DEFAULT NULL
)
RETURNS TABLE (
  rule_id TEXT,
  rule_type TEXT,
  action JSONB,
  conflicts_resolved TEXT[],
  resolution_method TEXT
) AS $$
-- 1. Gather all applicable rules for scope + industry + tenant
-- 2. Detect conflicts via conflicts_with arrays
-- 3. Apply most-restrictive-wins: forbidden > required > conditional
-- 4. Within same type: highest priority value wins
-- 5. Return resolved rule set with conflict audit trail
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### Acceptance Criteria

- [ ] Supabase migrations create tenants, tenant_configs, jobs, compliance_rules tables
- [ ] RLS policies active with FORCE on all tenant-scoped tables
- [ ] `set_tenant_context()` function sets transaction-local tenant scope
- [ ] Isolation verification test passes (tenant A cannot see tenant B's data)
- [ ] Deny-by-default verified (no set_config → empty results)
- [ ] Compliance conflict resolution function returns resolved rules with audit trail

---

## Step 6: Harness Infrastructure

**Goal:** Deploy LangGraph, LiteLLM, and Redis on Render with health checks passing. No agent logic yet — just the skeleton.

**Spec references:** Section 5a

### 6a. LangGraph Supervisor Graph Skeleton

```python
# harness/src/harness/state.py
from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END

class HarnessState(TypedDict):
    tenant_id: str
    run_id: str
    worker_id: str
    messages: Annotated[Sequence, operator.add]  # append reducer
    policy_decision: str       # "allowed" | "blocked" | "escalated"
    context_budget_remaining: int
    verification_passed: bool
```

```python
# harness/src/harness/graphs/supervisor.py
# Phase 1: skeleton only — nodes are stubs that pass through
# Phase 2 will implement actual context assembly, policy gate, workers

graph = StateGraph(HarnessState)
graph.add_node("context_assembly", stub_context_assembly)
graph.add_node("policy_gate", stub_policy_gate)
graph.add_node("worker_execute", stub_worker)
graph.add_node("verification", stub_verification)
graph.add_node("persist", stub_persist)

graph.set_entry_point("context_assembly")
graph.add_edge("context_assembly", "policy_gate")
graph.add_conditional_edges("policy_gate", policy_router, {
    "allowed": "worker_execute",
    "blocked": END,
})
graph.add_edge("worker_execute", "verification")
graph.add_edge("verification", "persist")
graph.add_edge("persist", END)

app = graph.compile(checkpointer=postgres_checkpointer)
```

### 6b. LiteLLM Proxy

**`infra/litellm/config.yaml`:**

```yaml
model_list:
  - model_name: "primary"
    litellm_params:
      model: "anthropic/claude-sonnet-4-6"
      api_key: "os.environ/ANTHROPIC_API_KEY"
      max_tokens: 4096
      timeout: 120

  - model_name: "triage"
    litellm_params:
      model: "ollama/llama3.1:8b"
      api_base: "os.environ/OLLAMA_BASE_URL"
      timeout: 30

router_settings:
  num_retries: 2
  timeout: 120
  allowed_fails: 3
  cooldown_time: 60

litellm_settings:
  drop_params: true
  set_verbose: false
  request_timeout: 120

general_settings:
  master_key: "os.environ/LITELLM_MASTER_KEY"
  database_url: "os.environ/LITELLM_DB_URL"
```

**`infra/litellm/Dockerfile`:**

```dockerfile
FROM ghcr.io/berriai/litellm:main-latest
COPY config.yaml /app/config.yaml
EXPOSE 4000
CMD ["--config", "/app/config.yaml", "--port", "4000", "--num_workers", "2"]
```

### 6c. Redis Configuration

```python
# harness/src/cache/redis_client.py
import redis
import os

redis_client = redis.Redis.from_url(
    os.environ["REDIS_URL"],
    decode_responses=True,
    retry_on_timeout=True,
    socket_connect_timeout=5,
    socket_timeout=5,
)

# Namespace-scoped key helpers
def tenant_key(tenant_id: str, category: str, identifier: str) -> str:
    return f"t:{tenant_id}:{category}:{identifier}"

def global_key(category: str, identifier: str) -> str:
    return f"g:{category}:{identifier}"
```

### 6d. Health Check Endpoints

```python
# harness/src/harness/server.py
from fastapi import FastAPI
import redis

app = FastAPI()

@app.get("/health")
async def health():
    checks = {}
    # Check Redis
    try:
        redis_client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "degraded"

    # Check Supabase (simple query)
    try:
        await db_pool.execute("SELECT 1")
        checks["supabase"] = "ok"
    except Exception:
        checks["supabase"] = "down"

    # Check LiteLLM
    try:
        resp = await httpx.get(f"{LITELLM_URL}/health")
        checks["litellm"] = "ok" if resp.status_code == 200 else "down"
    except Exception:
        checks["litellm"] = "down"

    status = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
```

### 6e. Render Blueprint

**`render.yaml`:**

```yaml
services:
  - type: web
    name: calllock-harness
    runtime: python
    plan: standard
    buildCommand: cd harness && pip install -r requirements.txt
    startCommand: cd harness && uvicorn src.harness.server:app --host 0.0.0.0 --port 8000
    healthCheckPath: /health
    envVars:
      - key: SUPABASE_DB_URL
        sync: false
      - key: LITELLM_URL
        value: http://calllock-litellm:4000
      - key: REDIS_URL
        fromService:
          name: calllock-redis
          type: redis
          property: connectionString
      - key: LANGSMITH_API_KEY
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
    autoDeploy: false

  - type: web
    name: calllock-litellm
    runtime: docker
    dockerfilePath: infra/litellm/Dockerfile
    plan: starter
    healthCheckPath: /health
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: LITELLM_MASTER_KEY
        sync: false
      - key: LITELLM_DB_URL
        sync: false

  - type: redis
    name: calllock-redis
    plan: starter
    maxmemoryPolicy: allkeys-lru
```

### Acceptance Criteria

- [ ] LangGraph supervisor graph compiles and runs with stub nodes
- [ ] PostgreSQL checkpointer connects to Supabase
- [ ] LiteLLM proxy starts and responds to `/health`
- [ ] Redis connects and responds to PING
- [ ] Harness health check endpoint returns status of all dependencies
- [ ] Render Blueprint deploys all three services
- [ ] All services health-checking green on Render dashboard

---

## Step 7: Phase 1 Integration Smoke Test

**Goal:** Verify all Phase 1 deliverables compose correctly — the "Phase 1 done" criterion.

Individual deliverables can pass their acceptance criteria but fail to work together. This step validates integration before declaring Phase 1 complete.

**Smoke test checklist:**

```python
# tests/integration/test_phase1_smoke.py

# 1. Knowledge graph → Retrieval engine
#    Retrieval engine can find HVAC pack nodes by query
#    Expected: "HVAC emergency tiers" returns urgency.yaml content

# 2. Tenant config → Industry pack reference
#    tenant_configs.industry_pack_id resolves to a valid pack manifest
#    Expected: pack.yaml exists and validates for the referenced pack

# 3. Compliance graph → Conflict resolution
#    resolve_compliance_conflicts() returns resolved rules for HVAC scope
#    Expected: no unresolved conflicts in the seeded compliance data

# 4. Harness → LiteLLM
#    Harness health check reports LiteLLM as reachable
#    LiteLLM proxies a test prompt to Claude and returns a response

# 5. Harness → Redis
#    Cache a knowledge graph node, retrieve it, verify content matches
#    Verify tenant-scoped key isolation (tenant A's cache ≠ tenant B's)

# 6. Harness → Supabase
#    Checkpointer can write and read a checkpoint
#    RLS prevents cross-tenant reads (tenant A cannot see tenant B's jobs)

# 7. Worker spec → Tool registry (soft check)
#    All tools_allowed values in worker specs are documented strings
#    (Full registry validation deferred to Phase 2)
```

### Acceptance Criteria

- [ ] All 7 integration checks pass
- [ ] Smoke test runs in CI as a post-deploy verification step
- [ ] Test uses 2 seeded test tenants with different industry packs

---

## Retrieval Engine Evaluation Criteria

**Gap identified by SpecFlow analysis:** The spec says "within latency budget" but no budget is defined, and no golden query set exists.

### Evaluation Framework

**Golden query set (minimum 10 queries):**

| Query | Expected top result | Graph |
|-------|-------------------|-------|
| "HVAC emergency tiers" | `industry-packs/hvac/urgency.yaml` | industry |
| "carbon monoxide response" | `industry-packs/hvac/urgency.yaml` (tier3) | industry |
| "forbidden pricing claims" | `compliance/forbidden-claims.md` | compliance |
| "required disclosures" | `compliance/required-disclosures.md` | compliance |
| "CallLock business model" | `company/business-model.md` | company |
| "voice agent capabilities" | `product/features/voice-agent.md` | product |
| "customer analyst mission" | `worker-specs/customer-analyst.yaml` | worker |
| "booking confirmation script" | `industry-packs/hvac/scripts/booking-confirmation.md` | industry |
| "furnace repair tags" | `industry-packs/hvac/taxonomy.yaml` | industry |
| "tenant isolation policy" | compliance or product architecture | compliance |

**Latency budget (proposed):** <500ms per query for indexed search on a corpus of <1000 nodes. Baseline to be measured in Phase 1 and formalized.

**Evaluation criteria for adopt/adapt/build decision:**

| Criterion | Adopt | Adapt | Build |
|-----------|-------|-------|-------|
| YAML frontmatter parsed as structured metadata | Yes | Partially | No |
| Wiki-link resolution | Yes | No | No |
| Tenant-scoped filtering | Yes | Partially | No |
| Latency <500ms on test corpus | Yes | Yes | N/A |
| 8/10+ golden queries return correct top result | Yes | 6-7/10 | <6/10 |

**Output:** Architecture Decision Record at `docs/decisions/001-retrieval-engine.md`

---

## HVAC Extraction: Behavioral Validation

**Gap identified by SpecFlow analysis:** Extracted data could be structurally correct (117 entries) but semantically wrong. V2 smart tag logic may be procedural (regex, conditional), not purely declarative.

### Validation approach:

1. **During extraction:** Document whether each tag is declarative (static label + aliases) or procedural (computed from transcript analysis). If procedural, note the logic in a `_migration-notes.md` file in the pack directory.

2. **Cross-validation test:** If V2 has existing tests that validate tag classification, extract the test inputs/expected outputs as a golden dataset. Run the same inputs against the extracted pack's alias matching to verify behavioral equivalence.

3. **Acceptance criterion addition:** At least 90% of V2's tag classification test cases (if they exist) should produce the same result when matched against the extracted taxonomy.yaml aliases.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| V2 codebase access needed for HVAC extraction | Medium | High (blocks Step 4) | Coordinate access early; can proceed with other steps in parallel |
| LangGraph Python vs JS decision delays | Low | Medium | Plan assumes Python; if JS chosen, only Step 6 changes |
| Supabase RLS complexity with connection pooling | Medium | High | Use transaction-local `set_config` only; test with PgBouncer in staging |
| Knowledge graph schema evolves during authoring | High | Low | Schema version field allows migration; CI catches breaking changes |
| 117 smart tags may not map cleanly to YAML | Medium | Medium | Allow iterative extraction; pack validation catches structural issues |
| Render inter-service networking | Low | Medium | Use internal URLs; test connectivity before deploying logic |
| V2 smart tags are procedural, not declarative | Medium | High | Discovery session before extraction; document procedural logic in migration notes |
| Retrieval engine eval yields "build custom" | Low | High (blocks Phase 2) | Evaluate 2-3 candidates; "adapt" is acceptable if "adopt" fails |
| RLS `set_config` forgotten in a harness query | Medium | Critical (cross-tenant leak) | Enforce via `withTenantScope()` wrapper; never use raw DB client |
| No integration test catches composition failures | High | Medium | Step 7 (Integration Smoke Test) added to this plan |

---

## Open Questions (Resolve Before or During Implementation)

1. **V2 codebase access** — Is the V2 repo accessible from this workspace, or does extraction happen separately?
2. **Supabase project** — Use the existing production Supabase instance (with new tables) or create a separate staging instance?
3. **Ollama on Render** — Is Ollama deployed on Render, or is the triage model a future concern?
4. **Knowledge graph initial content** — Who authors the company/product graph content? Is there existing documentation to extract from?
5. **Compliance rules** — Are the initial compliance rules HVAC-specific only, or are there general rules to seed?
6. **Worker spec `tools_allowed`** — Should CI validate tool names against a registry (none exists yet), or just validate the field is non-empty? Recommend: validate as non-empty strings in Phase 1, defer registry validation to Phase 2.
7. **Skill packs** — Worker specs can reference `linked_skill_packs`. Should empty skill pack directories be created in Phase 1, or should worker specs omit this field until Phase 2?
8. **Retrieval engine evaluation scope** — Does "evaluate" include proving MCP server integration with the harness, or just search quality over the knowledge corpus?

---

## Implementation Sequence (Recommended)

```
Week 1:  Step 1 (Scaffolding) — all other steps unblocked
         Step 3 (Worker Specs) — independent, can start immediately after scaffolding
         Step 5a-5b (Supabase migrations + RLS) — independent

Week 2:  Step 2 (Knowledge Substrate) — content authoring
         Step 4 (HVAC Pack extraction) — requires V2 access
         Step 5c-5d (Isolation tests + conflict resolution)

Week 3:  Step 6 (Harness Infrastructure) — deploy to Render
         Step 7 (Integration Smoke Test) — validates all deliverables compose
         CI pipeline validation end-to-end
```

**Total estimated effort:** 3 weeks with 1-2 engineers working in parallel.

---

## References

### Internal
- Architecture spec: `docs/superpowers/specs/2026-03-12-calllock-agentos-architecture-design.md`
- Open TODOs: `TODOS.md`
- CEO review transcripts: `.context/attachments/`

### External
- LangGraph docs: https://langchain-ai.github.io/langgraph/
- LiteLLM docs: https://docs.litellm.ai/
- Inngest docs: https://www.inngest.com/docs
- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
- Render Blueprints: https://docs.render.com/blueprint-spec

### Related Architecture Decisions
- Compliance graph database-backed (not file-based): Spec Section 8, TODOS.md P1
- Harness runtime Python (not Node.js): This plan, "Architectural Decision" section
- Most-restrictive-wins conflict resolution: Spec Section 5, TODOS.md P1
