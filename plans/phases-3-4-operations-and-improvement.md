# Phases 3-4: Operations and Improvement

Status: Drafted for execution  
Branch: `phase1/foundation` -> follow-on phase branches  
Timeline: After Phase 2 completion

Shared context:

- Architecture spec: `docs/superpowers/specs/2026-03-12-calllock-agentos-architecture-design.md`
- Open TODOs: `TODOS.md`
- Depends on all Phase 1-2 acceptance criteria completing first

## Phase 3: Full Operations

Goal: all planned workers are active, tenant onboarding is automated, async jobs are durable, artifacts are governed, and the Cockpit can monitor and interrupt the system safely.

### Step 17: Full V&V Pipeline

Expand the Phase 2 verification node into a reusable pipeline across all workers and external actions.

Create or extend:

- Shared verification contracts for structured outputs, factual checks, policy conformance, tone, and safety
- Retry and escalation paths for external action failures
- Worker-specific verification profiles keyed by worker spec
- Resilience tests for dependencies each worker uses

Files:

- `harness/src/harness/nodes/verification.py`
- `harness/src/harness/verification/`
- LangSmith eval suites for multi-worker runs

Acceptance:

- Every active worker has a verification profile
- Each worker has at least one resilience test per external dependency
- Failed validations produce deterministic block, retry, or escalate outcomes

### Step 18: Delegation and Jobs

Implement durable async and scheduled execution via Inngest and LangGraph subgraphs.

Create or extend:

- Job orchestration for async, scheduled, cancel, replace, and retry flows
- Idempotency enforcement using the `jobs` table
- Supervisor-to-worker delegation patterns for sync and async work
- Job status tracking and re-entry from persisted state

Files:

- `inngest/src/functions/`
- `harness/src/harness/graphs/supervisor.py`
- `harness/src/harness/jobs/`
- `supabase/migrations/004_jobs.sql`

Acceptance:

- Async and scheduled jobs run through Inngest with idempotency keys
- Cancel/replace semantics work for long-running jobs
- Interrupted jobs can be resumed or failed cleanly

### Step 19: Tenant Operations Onboarding

Automate tenant onboarding from config creation to operational readiness.

Create:

- An onboarding workflow that provisions tenant records, config, industry pack linkage, baseline feature flags, and compliance defaults
- Validation gates for required config completeness
- Audit logging for onboarding actions and operator approvals
- Seed templates for at least HVAC tenants

Files:

- `harness/src/harness/workflows/onboarding.py`
- `supabase/seed.sql`
- `knowledge/industry-packs/hvac/pack.yaml`

Acceptance:

- A new tenant can be provisioned end-to-end from a single onboarding run
- Missing required inputs fail early with actionable errors
- Onboarding is fully tenant-scoped and auditable

### Step 20: Artifact Governance and Persistence

Define where outputs live and how they are versioned, traced, and recovered.

Create or extend:

- Artifact metadata schema for job results, reports, eval outputs, and generated assets
- Git-backed versioning for code, configs, knowledge, and plans
- Supabase-backed persistence for structured operational artifacts
- Retention and retrieval rules for artifacts referenced by the Cockpit

Files:

- `harness/src/harness/artifacts/`
- `supabase/migrations/`
- `docs/decisions/`

Acceptance:

- Each worker run produces traceable artifact records
- Structured artifacts can be retrieved by tenant and job
- Artifact lineage from input to persisted output is queryable

### Step 21: Remaining Worker Activation

Bring the remaining four workers online after Customer Analyst.

Activate:

- Product Manager
- Engineer
- Designer
- Product Marketer

Requirements:

- Load each worker from its YAML spec
- Define worker-specific tool grants
- Add minimum eval suites and resilience tests
- Respect approval boundaries before any external or production-affecting action

Files:

- `harness/src/harness/graphs/workers/`
- `knowledge/worker-specs/*.yaml`
- LangSmith eval datasets

Acceptance:

- All 5 initial workers can execute through the supervisor graph
- Approval boundaries are enforced at runtime
- Each worker passes its minimum eval gate before activation

### Step 22: Cockpit Alerting and Kill Switches

Make the Cockpit operational as the command layer for production oversight.

Create:

- Alert emission for policy gate block rate, worker metric degradation, job failure spikes, and external service errors
- Kill switches to pause workers, disable jobs, or stop tenant-level execution
- Operator approval flows for risky actions
- Admin override paths limited to Cockpit-level permissions

Files:

- `harness/src/harness/alerts/`
- `harness/src/harness/control_plane/`
- `docs/decisions/`

Acceptance:

- Alerts fire for the four spec-defined categories
- Kill switches can pause execution without redeploying
- Risky actions require explicit approval when configured

### Phase 3 Acceptance

- All workers are active behind eval and approval gates
- Onboarding, jobs, and artifact persistence work end-to-end
- Cockpit alerting and pause controls are functional
- Tenant operations can run without manual database intervention

## Phase 4: Improvement

Goal: the system can evaluate itself safely, run bounded experiments, ingest customer content into durable knowledge, and give the founder a complete control surface for portfolio management.

### Step 23: Improvement Lab

Implement the experiment layer with isolation and lock control.

Create:

- Experiment registry with scope, budget, owner, and rollback metadata
- Lock registry to prevent conflicting experiments
- Sandboxed execution paths for candidate changes
- Promotion rules that require eval evidence before rollout

Files:

- `harness/src/harness/improvement_lab/`
- `docs/decisions/`

Acceptance:

- Concurrent experiments cannot mutate the same protected target without a lock decision
- Experiments can be promoted, rejected, or rolled back with audit history
- No experiment reaches production without passing its eval gate

### Step 24: Full Eval Coverage

Expand evaluation from minimum viable coverage to all three tiers defined in the spec.

Create:

- Core eval suites for shared harness behaviors
- Industry eval suites for HVAC pack logic
- Tenant eval suites for tenant-specific configurations and policies
- Budgeted recurring eval runs with regression alerts

Files:

- LangSmith eval datasets
- `harness/src/harness/evals/`

Acceptance:

- Core, industry, and tenant eval tiers all exist
- Promotion decisions reference current eval results
- Regressions trigger Cockpit-visible alerts

### Step 25: Customer Content Pipeline

Build the Raw -> Sanitized -> Structured pipeline for customer-derived knowledge.

Create:

- Intake for raw transcripts, notes, and feedback
- Sanitization and PII handling before reuse
- Structured extraction into customer insight graphs and operational records
- Governance around what content is reusable by workers

Files:

- `knowledge/customer-insights/`
- `harness/src/harness/content_pipeline/`
- `harness/src/observability/pii_redactor.py`

Acceptance:

- Raw customer content is never exposed to downstream workers without sanitization
- Structured outputs can be linked back to their sanitized source
- Customer insight knowledge stays tenant-scoped

### Step 26: Founder Cockpit

Complete the portfolio control surface described in the spec.

Create:

- Portfolio KPIs and tenant health views
- Experiment oversight and promotion controls
- Budget, margin, and risk monitoring
- Release oversight across dashboard, backend, and voice deployments

Files:

- Cockpit application surface, implemented in the appropriate product codebase
- `docs/decisions/`

Acceptance:

- Founders can inspect tenant health, experiments, and release posture from one place
- Approval and kill-switch actions are visible and auditable
- Cockpit surfaces alert history and current system posture

### Phase 4 Acceptance

- Improvement Lab is operational with isolation and rollback
- Full eval coverage gates promotions
- Customer content pipeline is safe and durable
- Founder Cockpit provides portfolio-level oversight and controls

## Phases 3-4 Execution Sequence

- Sequence 1: Step 17 and Step 18 establish multi-worker execution safety and durable jobs
- Sequence 2: Step 19 and Step 20 establish operational onboarding and artifact governance
- Sequence 3: Step 21 and Step 22 bring the full worker set online behind Cockpit controls
- Sequence 4: Step 23 through Step 26 add bounded experimentation, full evals, customer content ingestion, and founder controls

## Phases 3-4 Open Questions

- External service resilience patterns for Retell AI, Supabase, Cal.com, and Twilio remain a P2 TODO
- Inngest event validation schema remains a P2 TODO and should land before broad async expansion
- Harness -> Supabase write failure handling remains a P2 TODO and is critical before large artifact volumes
- PII redaction implementation detail remains a P2 TODO and should be resolved before full LangSmith rollout
- Express V2 horizontal scaling remains a P3 TODO
- Cockpit alert thresholds and delivery channels remain a P3 TODO

## Phases 3-4 Verification

- Phase 3: verify onboarding, multi-worker execution, async jobs, and Cockpit controls in a staging environment with multiple seeded tenants
- Phase 4: verify experiment isolation, tiered eval coverage, customer content sanitation, and Cockpit promotion flows
- Continuous verification: retain CI from Phases 1-2 and add recurring eval runs plus dependency resilience tests
