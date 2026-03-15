# Phases 1-2: Foundation and Core Harness

Status: Ready for execution  
Branch: `rbaset5/agent-arch-spec` -> `phase1/foundation`  
Timeline: Weeks 1-7

Shared context:

- Architecture spec: `docs/superpowers/specs/2026-03-12-calllock-agentos-architecture-design.md`
- Open TODOs: `TODOS.md`
- Key decision: Python harness (LangGraph Python SDK) as separate Render service
- V2 codebase: `/Users/rashidbaset/conductor/workspaces/calllock-app/hong-kong-v`

## Phase 1: Foundation (Weeks 1-3)

Goal: establish the knowledge substrate, industry pack format, tenant isolation, and base harness infrastructure. No agent work runs yet.

### Step 1: Project Scaffolding

Create the monorepo structure, tooling, and CI foundation.

Create:

- Full directory tree: `knowledge/`, `harness/`, `infra/`, `inngest/`, `supabase/`, `scripts/`, `.github/`
- `CLAUDE.md` with project conventions: frontmatter requirements, wiki-link syntax, RLS pattern, compliance graph DB-backing
- `.gitignore` for Node, Python, `.env`, `.context/`, and build artifacts
- `.github/workflows/validate.yml` with CI jobs for knowledge, packs, worker specs, and harness lint/test
- `harness/pyproject.toml` and `harness/requirements.txt` with `langgraph`, `litellm`, `redis`, `fastapi`, `uvicorn`, `httpx`, `pydantic`, `langsmith`
- `inngest/package.json` and `inngest/tsconfig.json` with strict TypeScript and `inngest`
- `render.yaml` for 3 services: harness, LiteLLM, Redis
- `infra/litellm/config.yaml` and `infra/litellm/Dockerfile`
- Validation script stubs in `scripts/`
- Expanded `README.md` project overview

Files to modify:

- `README.md`

Acceptance:

- Directory structure matches the plan
- `pip install -e .` works in `harness/`
- CI YAML is valid
- `.gitignore` is correct

### Step 2: Knowledge Substrate

Populate knowledge graphs with company, product, compliance, and customer insight content.

Create:

- `knowledge/_moc.md` as the root map of content with wiki links to all sub-graphs
- `knowledge/company/`: `mission.md`, `business-model.md`, `team.md`, `goals-2026.md`, `_moc.md`
- `knowledge/product/`: `architecture.md`, `features/voice-agent.md`, `features/dashboard.md`, `features/booking.md`, `features/alerts.md`, `roadmap.md`, `dependencies.md`, `_moc.md`
- `knowledge/compliance/`: `regulations/hvac-licensing.md`, `regulations/general-disclosures.md`, `forbidden-claims.md`, `required-disclosures.md`, `_moc.md`
- `knowledge/customer-insights/_moc.md` as a placeholder
- Required frontmatter on all files: `id`, `title`, `graph`, `owner`, `last_reviewed`, `trust_level`, `progressive_disclosure`
- `scripts/validate-knowledge.ts` with real validation logic for frontmatter, wiki links, MOCs, freshness, and orphan detection
- `supabase/migrations/003_compliance_graph.sql` for `compliance_rules` with scope/type indexes and a GIN index on `conflicts_with`

Acceptance:

- All frontmatter is valid
- Wiki links resolve
- MOCs link to all children
- Compliance rules are seeded in Supabase

### Step 3: Worker Specs

Define 5 initial workers in Standard Worker Schema YAML.

Create:

- `knowledge/worker-specs/product-manager.yaml`
- `knowledge/worker-specs/engineer.yaml`
- `knowledge/worker-specs/designer.yaml`
- `knowledge/worker-specs/product-marketer.yaml`
- `knowledge/worker-specs/customer-analyst.yaml`
- `knowledge/worker-specs/_moc.md`
- `scripts/validate-worker-specs.ts` with checks for required fields, schema version, non-empty tool refs, eval dataset refs, and duplicate `worker_id` values

Required schema per worker:

- `schema_version`
- `worker_id`
- `version`
- `mission`
- `scope` with `can_do` and `cannot_do`
- `execution_scope`
- `inputs`
- `outputs`
- `tools_allowed`
- `success_metrics` with eval datasets
- `approval_boundaries`
- `dependencies`

Acceptance:

- All 5 workers pass CI validation
- Each has 2+ success metrics with eval datasets
- Approval boundaries are defined

### Step 4: HVAC Industry Pack

Extract 117 smart tags, 3+1 emergency tiers, and service taxonomy from the V2 backend.

V2 extraction map:

| Pack file | V2 source | Extract |
| --- | --- | --- |
| `taxonomy.yaml` | `classification/tags.ts` (lines 43-321) | 117 tags across 9 categories: HAZARD(7), URGENCY(8), SERVICE_TYPE(23), REVENUE(9), RECOVERY(10), LOGISTICS(20), CUSTOMER(15), NON_CUSTOMER(12), CONTEXT(13+) |
| `urgency.yaml` | `types/retell.ts` (149-153), `classification/call-type.ts` (15-49), `extraction/urgency.ts` | 4 tiers: LifeSafety -> emergency, Urgent -> high, Routine -> medium, Estimate -> low |
| `compliance.yaml` | `extraction/post-call.ts` (37-42), `services/alerts.ts` (34-94) | Safety emergency detection regex, SMS alert format, callback promise rules |
| `booking-rules.yaml` | `functions/booking.ts`, `functions/calendar.ts` | Urgency-based availability routing, Cal.com event type ID `3877847`, booking params |
| `service-types.yaml` | `types/retell.ts` (137-147), `extraction/hvac-issue.ts` | 9 HVAC issue types with regex detection patterns |
| `scoring.yaml` | `extraction/call-scorecard.ts` (46-80) | Quality scorecard: 7 fields, weighted scoring (0-100) |
| `priority-detection.yaml` | `services/priority-detection.ts` | RED/GREEN/BLUE/GRAY triage with keyword patterns |
| `revenue-estimation.yaml` | `services/revenue-estimation.ts` | Revenue tier classification |
| `reporting.yaml` | New | Reporting templates based on V2 dashboard data |
| `scripts/inbound-call.md` | `types/retell.ts` (258-310) | 53-field `ConversationState` as call script template |
| `scripts/emergency-dispatch.md` | `services/alerts.ts` | Emergency dispatch flow |
| `scripts/booking-confirmation.md` | `functions/booking.ts` | Booking confirmation flow |

Key extraction notes:

- Tags use negation-aware phrase matching with a 40-character lookback, so part of the logic is procedural and must be documented in `_migration-notes.md`
- `classifyCall()` in `tags.ts` lines 326-531 contains the full classification logic
- V2 has 4 urgency tiers, not 3
- Booking rules are tightly coupled to Cal.com and need declarative extraction

Create:

- All pack files listed above
- `knowledge/industry-packs/hvac/pack.yaml` with the actual extracted smart tag count
- `knowledge/industry-packs/hvac/scripts/_moc.md`
- `knowledge/industry-packs/hvac/_migration-notes.md`
- `scripts/validate-packs.ts` with real validation

Acceptance:

- All tags are extracted with aliases
- 4 urgency tiers are defined
- Pack manifest validates
- CI passes
- Provenance is documented

### Step 5: Tenant Config + RLS

Define tenant schema in Supabase with Row Level Security.

Create:

- `supabase/migrations/001_tenants.sql`
- `supabase/migrations/002_tenant_configs.sql`
- `supabase/migrations/004_jobs.sql` with idempotency keys
- `supabase/migrations/005_rls_policies.sql` with `ENABLE`, `FORCE RLS`, `set_tenant_context()`, tenant isolation policies, and admin bypass
- `supabase/migrations/006_compliance_conflict_resolution.sql` with `resolve_compliance_conflicts()` using most-restrictive-wins
- `supabase/seed.sql` with 2 test tenants, sample configs, and compliance rules
- `harness/tests/test_tenant_isolation.py` for cross-tenant isolation, deny-by-default, and admin bypass

Acceptance:

- Migrations create all tables
- RLS is active with `FORCE`
- Isolation tests pass
- Deny-by-default is verified

### Step 6: Harness Infrastructure

Deploy LangGraph, LiteLLM, and Redis on Render with health checks.

Create:

- `harness/src/harness/state.py` with `HarnessState`
- `harness/src/harness/graphs/supervisor.py` with a `StateGraph` skeleton and stub nodes
- `harness/src/harness/server.py` with a FastAPI `/health` endpoint
- `harness/src/cache/redis_client.py`
- `harness/src/cache/keys.py`
- `harness/src/db/tenant_scope.py`
- Stub files for the remaining `harness/src/` modules

Acceptance:

- Supervisor graph compiles
- LiteLLM `/health` responds
- Redis `PING` works
- Harness `/health` is green

### Step 7: Integration Smoke Test

Create `tests/integration/test_phase1_smoke.py` with 7 checks:

- Knowledge graph retrieval finds HVAC pack nodes
- `tenant_configs.industry_pack_id` resolves to a valid pack manifest
- `resolve_compliance_conflicts()` returns no unresolved HVAC conflicts
- Harness -> LiteLLM -> Claude test prompt succeeds
- Redis cache/retrieve works with tenant key isolation
- Checkpointer write/read works and RLS blocks cross-tenant access
- Worker spec `tools_allowed` fields are documented strings

Acceptance:

- All 7 checks pass
- Runs in CI post-deploy
- Uses 2 seeded test tenants

### Phase 1 Retrieval Engine Evaluation

Evaluate QMD or an equivalent for hybrid search with a 10-query golden set and latency under 500ms.

Output:

- `docs/decisions/001-retrieval-engine.md`

## Phase 2: Core Harness (Weeks 4-7)

Goal: the harness receives events from Express V2, assembles context, runs workers through the policy gate, and persists results. Customer Analyst is the first live worker.

### Step 8: Policy Gate Implementation

- Replace `stub_policy_gate` with a real implementation
- Read the compliance graph from Supabase, plus industry pack rules, tenant config, and feature flags
- Enforce deny-by-default: if no matching allow exists, block and log
- Resolve conflicts via `resolve_compliance_conflicts()` using most-restrictive-wins
- On violation, block and log by default or escalate to Cockpit if configured

Files:

- `harness/src/harness/nodes/policy_gate.py`

Tests:

- Infrastructure tests for gate logic
- Conflict resolution tests
- Deny-by-default tests

### Step 9: Context Assembly Pipeline

- Replace `stub_context_assembly` with a real implementation
- Apply priority ordering: worker spec > task context > tenant config > industry pack > knowledge graph > memory > history
- Drop lower-priority sources first during compaction
- Use progressive disclosure: summaries first, full content on demand
- Enforce budget by model context window

Files:

- `harness/src/harness/nodes/context_assembly.py`
- `harness/src/knowledge/*.py`

Tests:

- Priority ordering
- Compaction behavior
- Budget enforcement

### Step 10: Tool Governance Pipeline

- Build the Authored -> Validated -> Granted pipeline
- Resolve available tools per run, tenant, and environment
- Make runtime policy authoritative over authored specs

Files:

- `harness/src/harness/tool_registry.py`

Tests:

- Tool grant/deny by tenant config
- Runtime override behavior

### Step 11: Harness Triggering (Express V2 -> Inngest -> Harness)

- Define Inngest event schemas for harness trigger events
- Emit events from Express V2 after Retell webhook processing
- Subscribe in the harness and dispatch to the supervisor graph

Files:

- `inngest/src/events/schemas.ts`
- `inngest/src/functions/process-call.ts`
- `inngest/src/client.ts`

Requires:

- Inngest Cloud account
- Event key

### Step 12: Return Path (Harness -> Supabase + Inngest)

- Replace `stub_persist` with a real implementation
- Write directly to Supabase via `withTenantScope`
- Emit Inngest events back to Express V2
- Route external actions through the tool registry, subject to Policy Gate and V&V

Files:

- `harness/src/harness/nodes/persist.py`

### Step 13: Verification & Validation (V&V)

- Replace `stub_verification` with a real implementation
- Validate output format, factual accuracy, tone compliance, and safety post-execution
- On failure, block, retry once, and escalate to Cockpit if the retry fails

Files:

- `harness/src/harness/nodes/verification.py`

### Step 14: Customer Analyst Worker Activation

- Activate the first live worker from `customer-analyst.yaml`
- Support call outcome classification, lead routing, sentiment extraction, and churn detection
- Build a minimum eval suite with 10 golden examples per success metric
- Add infrastructure and resilience tests

Files:

- `harness/src/harness/graphs/workers/customer_analyst.py`
- LangSmith eval datasets

### Step 15: Service Authentication

- Authenticate all integration points per spec Section 5b
- Store secrets in Render environment variables
- Support secret rotation without code deploys

### Step 16: Observability (LangSmith + PII Redaction)

- Add LangSmith tracing with tenant-scoped namespaces
- Redact PII before trace submission
- Keep local Pino logging as fallback when LangSmith is degraded

Files:

- `harness/src/observability/langsmith_tracer.py`
- `harness/src/observability/pii_redactor.py`

Phase 2 acceptance:

- End-to-end flow works: Retell webhook -> Express V2 -> Inngest -> Harness -> context assembly -> policy gate -> Customer Analyst -> V&V -> persist -> Inngest notification
- All traces appear in LangSmith with PII redacted

## Phases 1-2 Execution Sequence

- Week 1: Step 1, plus Step 3 and Step 5a-b once scaffolding lands
- Week 2: Step 2 and Step 4, plus Step 5c-d
- Week 3: Step 6 and Step 7
- Week 4: Steps 8-9
- Week 5: Steps 10-12
- Week 6: Steps 13-14
- Week 7: Steps 15-16 and the Phase 2 end-to-end test

## Phases 1-2 Open Questions

- V2 codebase access: resolved to `/Users/rashidbaset/conductor/workspaces/calllock-app/hong-kong-v`
- Supabase project: use the existing production instance or separate staging?
- Ollama on Render: deploy now or defer?
- Knowledge content authoring: resolved to author from spec + V2 context, then review
- Initial compliance rules: HVAC-only or general rules too?
- Retrieval engine evaluation scope: search quality only or full MCP integration?

## Phases 1-2 Verification

- Phase 1: the integration smoke test in Step 7 proves the 6 foundation deliverables compose
- Phase 2: an end-to-end test proves webhook -> harness -> worker -> persist -> notification
- Continuous verification: CI validates knowledge, packs, and worker specs on every PR, and runs `ruff`, `mypy`, and `pytest` on the harness
