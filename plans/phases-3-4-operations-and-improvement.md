# Phases 3-4: Operations and Improvement

Status: Blocked on Phase 2 completion  
Prerequisite: Phases 1-2 complete (Steps 1-16)  
Timeline: Weeks 8-16+

Shared context:

- Architecture spec: `docs/superpowers/specs/2026-03-12-calllock-agentos-architecture-design.md`
- Open TODOs: `TODOS.md`
- Key decision: Python harness (LangGraph Python SDK) as separate Render service
- V2 codebase: `/Users/rashidbaset/conductor/workspaces/calllock-app/hong-kong-v`

## Phase 3: Full Operations (Weeks 8-12)

Goal: all workers active, tenant onboarding automated, async jobs running, full artifact governance in place, and Cockpit alerting plus kill switches operational.

### Step 17: V&V Pipeline Expansion

Extend verification and validation beyond Customer Analyst to cover every worker output type and every production-affecting action.

Implement:

- Shared V&V contracts for structured outputs, factual checks, tone, and safety
- Factual accuracy checks against the knowledge graph for each worker's domain
- Tone compliance checks keyed by tenant config
- Safety checks for forbidden claims, policy violations, and PII leakage in outputs
- Deterministic outcomes for pass, retry, block, or escalate

Files:

- `harness/src/harness/nodes/verification.py`
- `harness/src/harness/verification/`
- LangSmith eval suites for worker-specific and multi-worker runs

Acceptance:

- Every active worker has an explicit V&V profile
- Each worker domain is checked against the relevant knowledge graph surface
- Tone and safety checks are tenant-aware
- Failures resolve through deterministic block, retry, or escalate paths

### Step 18: Delegation and Job Layer

Implement the full sync and async delegation model using LangGraph subgraphs for in-graph work and Inngest durable functions for externalized jobs.

Implement:

- Sync delegation through LangGraph in-graph and subgraph execution
- Async delegation through Inngest durable functions with task handles, status lookup, cancel, and replace
- Scheduled jobs using `step.sleep()`, `step.sleepUntil()`, and `step.sendEvent()` executing against current state
- Idempotency keys for all external side effects including bookings, SMS, email, and publish actions
- Job metadata: `job_id`, `tenant_id`, `origin_worker_id`, `origin_run_id`, `job_type`, `status`, `supersedes_job_id`, `source_call_id`
- Concurrency limits, budget limits, and retry policies
- Permission model where the origin worker manages its own jobs and Cockpit or Ops holds admin override

Files:

- Job dispatch logic in the harness
- Inngest function definitions
- `harness/src/harness/graphs/supervisor.py`
- `harness/src/harness/jobs/`
- `supabase/migrations/004_jobs.sql`

Acceptance:

- Async and scheduled jobs run durably through Inngest
- Cancel and replace semantics work for long-running jobs
- External actions are protected by idempotency keys
- Job ownership and admin override rules are enforced at runtime

### Step 19: Tenant Operations (Onboarding Workflow)

Automate tenant onboarding as one governed workflow with rollback semantics and Cockpit approval for administrative actions.

Workflow:

1. Create tenant
2. Assign industry pack
3. Load tenant config
4. Apply RLS
5. Provision automations
6. Configure voice agent
7. Verify isolation
8. Notify Cockpit

Requirements:

- Required inputs: `tenant_name`, `industry_pack_id`, `contact_email`, `service_area`
- Atomic behavior: if any step fails, roll back all completed steps and mark the tenant as `onboarding_failed`
- Same tool governance, policy gate, and tracing model as worker flows
- Administrative actions require Cockpit approval and actor identity logging

Files:

- `harness/src/harness/workflows/onboarding.py`
- `supabase/seed.sql`
- `knowledge/industry-packs/hvac/pack.yaml`

Acceptance:

- A tenant can be onboarded end-to-end from a single workflow run
- Failure at any step triggers rollback and a terminal `onboarding_failed` state
- Isolation verification is part of the workflow, not a manual follow-up
- All administrative approvals are logged with actor identity

### Step 20: Artifact Governance and Persistence

Define how artifacts are stored, versioned, retained, and accessed across workers, tenant operations, and Cockpit.

Implement:

- Tenant-scoped access control so artifacts are readable only by the originating tenant's workers, Tenant Ops, and Cockpit
- Retention rules where tenant artifacts follow tenant policy and internal artifacts follow global policy
- Registry split: git for version-controlled outputs, Supabase for structured data, and a TBD object store for binary or large files
- Explicit lifecycle states: `Created`, `Active`, `Archived`, `Deleted`
- Audit fields: `created_by`, `tenant_id`, `created_at`, `source_job_id`, `artifact_type`

Files:

- `harness/src/harness/artifacts/`
- `supabase/migrations/`
- `docs/decisions/`

Acceptance:

- Artifact access is tenant-scoped and role-aware
- Structured artifact lineage is queryable by tenant and job
- Artifact retention and lifecycle state are explicit
- No artifact is silently deleted

### Step 21: Remaining Workers (PM, Engineer, Designer, Marketer)

Activate the remaining four workers only after eval coverage exists and their missions remain clearly non-overlapping.

Workers:

- Product Manager: prioritize roadmap, write specs, track metrics
- Engineer: implement features, fix bugs, maintain infra
- Designer: create UI and UX designs, maintain design system
- Product Marketer: SEO content, landing pages, customer comms

Activation requirements:

- No worker activates without eval coverage for each `success_metric`
- Minimum eval coverage is 10 golden examples per `success_metric`
- Activation order is based on business value and eval readiness
- No worker is allowed without a non-overlapping mission
- Tool grants and approval boundaries remain worker-specific

Files:

- `harness/src/harness/graphs/workers/`
- `knowledge/worker-specs/*.yaml`
- LangSmith eval datasets

Acceptance:

- All 5 planned workers are active behind eval gates
- Each worker has mission boundaries that do not collapse into another worker's scope
- Worker activation order is documented and justified by value plus eval readiness
- No worker can execute without its eval gate passing

### Step 22: Cockpit Alerting and Kill Switches

Make Cockpit operational as the command layer for monitoring, approvals, and interruption.

Implement:

- Alerts for policy gate block rate, worker metric degradation, job failure spikes, and external service errors
- Thresholds derived from baseline data gathered during Phase 2 and early Phase 3
- Kill switches to pause an individual worker, all harness work, or a specific tenant
- Delivery channel still TBD across dashboard notification, email, and SMS

Files:

- `harness/src/harness/alerts/`
- `harness/src/harness/control_plane/`
- `docs/decisions/`

Acceptance:

- Cockpit can monitor the four alert categories
- Kill switches work at worker, tenant, and global scope
- Alert thresholds are based on observed baselines rather than arbitrary defaults
- Approval and pause actions are visible and auditable

### Phase 3 Acceptance

- All 5 workers are active with eval coverage
- Tenant onboarding is automated end-to-end
- Async and scheduled jobs run durably through Inngest
- Artifacts persist with correct governance and auditability
- Cockpit can monitor and kill-switch any worker or tenant

## Phase 4: Improvement (Weeks 13-16+)

Goal: Improvement Lab running experiments, full eval coverage in all three tiers, customer content pipeline live, and Cockpit providing full operational visibility and control.

### Step 23: Improvement Lab

Implement the bounded experimentation system with isolation, lock management, and promotion only through verified delivery rails.

Implement:

- One experiment per mutation surface at a time
- Lock registry with TTL and heartbeat to prevent stale locks
- Process: propose change -> mutate bounded surface -> run fixed-budget experiment -> score against baseline using the same LangSmith evaluators -> keep or discard -> log outcome
- Good mutation targets: prompt files, workflow nodes, script variants, copy variants, threshold rules, industry pack logic
- Cockpit force-release for stale locks
- Promotion of successful changes only through the Safe Delivery Layer

Files:

- `harness/src/harness/improvement_lab/`
- `docs/decisions/`

Acceptance:

- Concurrent experiments cannot touch the same mutation surface
- Stale locks expire or can be force-released by Cockpit
- Experiments are evaluated against the same baseline scoring system used elsewhere
- No experiment reaches production outside Safe Delivery promotion

### Step 24: Full Eval Coverage (Three Tiers)

Expand evals from minimum viable worker coverage to complete core, industry, and tenant coverage.

Implement:

- Core evals for shared product and harness behaviors
- Industry evals for HVAC, Plumbing, Rooter, and future pack-specific behavior as packs come online
- Tenant evals for client-specific configured behavior
- Eval data sources from synthetic test cases, anonymized production data with PII redacted, and hand-curated golden examples
- Coverage for every worker `success_metric`
- Resilience tests for every blocking and degradable dependency

Files:

- LangSmith eval datasets
- `harness/src/harness/evals/`

Acceptance:

- Core, industry, and tenant eval tiers all exist
- Promotion decisions require current eval evidence
- Every worker `success_metric` maps to dataset coverage
- Dependency resilience is tested across blocking and degraded modes

### Step 25: Customer Content Pipeline

Build the Raw -> Sanitized -> Structured pipeline for customer-derived content.

Implement:

- Intake for raw call transcripts and customer-derived signals
- PII redaction before any data is reused in eval datasets or downstream knowledge
- Consent-aware and retention-aware reuse rules per tenant
- Structured insight extraction from call patterns, aligned with spec Section 8 customer-derived content

Files:

- `knowledge/customer-insights/`
- `harness/src/harness/content_pipeline/`
- `harness/src/observability/pii_redactor.py`

Acceptance:

- Raw customer content never reaches downstream consumers without sanitization
- Sanitized content can feed eval datasets and customer insight graphs
- Structured insights remain tenant-scoped and policy-governed
- Reuse respects tenant consent and retention settings

### Step 26: Founder Cockpit (Full)

Complete the Cockpit as the founder control surface across portfolio, releases, experiments, and operations.

Implement:

- Portfolio KPIs and industry-by-industry performance views
- Client health monitoring
- Approvals for risky actions such as publish, send, and billing changes
- Budget and margin oversight
- Improvement Lab oversight
- Safe Delivery oversight
- Eval result visibility with promotion decisions tied to eval data
- Kill switches and pause controls from Step 22 with full UI support

Files:

- Cockpit application surface in the appropriate product codebase
- `docs/decisions/`

Acceptance:

- Cockpit provides complete operational visibility and control
- Approval, eval, experiment, release, and kill-switch actions are unified in one surface
- Promotion and risky-action decisions are backed by auditable data

### Phase 4 Acceptance

- Improvement Lab runs bounded experiments with isolation
- Full eval coverage exists at core, industry, and tenant tiers
- Customer content pipeline produces anonymized eval-ready data
- Cockpit provides complete operational visibility and control

## Phases 3-4 Execution Sequence

- Week 8-9: Steps 17-18 (V&V expansion plus Delegation and Jobs)
- Week 10: Step 19 (Tenant onboarding)
- Week 11: Steps 20-21 (Artifact governance plus remaining workers)
- Week 12: Step 22 (Cockpit alerting) plus Phase 3 end-to-end test
- Week 13-14: Step 23 (Improvement Lab)
- Week 15: Steps 24-25 (Full evals plus Customer content pipeline)
- Week 16: Step 26 (Full Cockpit) plus Phase 4 acceptance

## Phases 3-4 Cross-Cutting Concerns

- External Service Resilience (P2 TODO): define fallback behavior for Retell AI, Supabase, Cal.com, and Twilio outages
- Express V2 Scaling (P3 TODO): document the horizontal scaling story once tenant count requires it
- Cockpit alerting thresholds (P3 TODO): establish thresholds from baseline data gathered during Phase 2 deployment

## Phases 3-4 Verification

- Phase 3: onboard a test tenant end-to-end and run a test call through all 5 workers
- Phase 4: run one Improvement Lab experiment, verify baseline scoring, and confirm promotion only through Safe Delivery
