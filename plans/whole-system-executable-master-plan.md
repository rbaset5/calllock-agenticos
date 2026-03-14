# CallLock AgentOS Whole-System Executable Master Plan

Status: Canonical execution plan  
Last updated: 2026-03-14  
Audience: implementers, reviewers, and handoff LLMs

## Purpose

This is the single source of truth for execution order, stage gates, dependency order, and acceptance criteria across the full system.

If you are starting with no context, read `plans/start-here-no-context.md` before this file.

Document authority remains split intentionally:

- `docs/superpowers/specs/2026-03-12-calllock-agentos-architecture-design.md` owns shared platform boundaries, runtime split, tenant isolation, deployment posture, and ADR-backed constraints.
- `knowledge/growth-system/design-doc.md` owns the CallLock growth-system authority: Growth Memory, routing and learning behavior, doctrine, lifecycle, phase gates, and future growth modules.
- `knowledge/growth-system/hold-scope-review.md` preserves the historical narrowed-phase review findings and rationale that still inform implementation rigor.
- This plan owns program sequencing, stage dependencies, readiness gates, and implementation order.

Older phase plans under `plans/` are supporting detail only. If they conflict with this document on sequencing, readiness gates, or execution priority, this document wins.

## Stage Map

| Master stage | Architecture layer focus | Growth phase | Primary outcome |
|---|---|---|---|
| Stage 0 Contract Lock | Shared platform + growth-system contracts | Pre-build | Remove implementation ambiguity |
| Stage 1 Shared Platform Foundation | Knowledge, packs, tenancy, harness infra | Pre-build | Shared execution substrate ready |
| Stage 2 Capture-Only | Growth-memory foundations | Phase 1 | Event spine, deterministic writes, attribution, replay |
| Stage 3 Advisory-Only | Operator review + projections | Phase 2 | Founder-visible insight without runtime steering |
| Stage 4 Assisted + Closed-Loop | Decisioning + control plane apply path | Phases 3-4 | Approved steering, then bounded automation |
| Stage 5 Cross-Funnel Expansion | Product + growth-system breadth | Phase 5 | Onboarding, retention, referral coverage |
| Stage 6 Federated Benchmarks | Governance intelligence | Phase 6 | Aggregate-only cross-tenant learning |
| Stage 7 Wedge Replication | Platform leverage | Phase 7 | Reusable wedge transfer system |

## Core Growth-System Contracts

These interfaces and subsystems must not be silently redefined in phase plans or implementation notes:

- Growth Memory table ownership and quality gates
- touchpoint logging, routing decision logging, and attribution views
- experiment allocator, conviction/readiness semantics, doctrine enforcement, proof coverage, and wedge-fitness semantics
- founder review workflow and delegation tiers
- control-plane authorization and projection coherence semantics
- Phase 7 aggregate-intelligence privacy thresholds
- compatibility treatment for legacy narrowed terms from the prior persuasion-platform rewrite

Legacy labels such as `persuasion_path`, `graph_mutation`, `review_object`, `lineage_chain`, `decisioning_projections`, `operator_projections`, `control_plane_auth`, and `federated_benchmark` remain valid only through the compatibility bridge in `knowledge/growth-system/design-doc.md`.

Stages 0-4 must lock the following qualities before downstream implementation depends on them:

- stable identity and versioning
- single-writer ownership
- idempotency and deduplication rules
- stale-state handling
- replay behavior
- failure visibility
- rollout and rollback gates

## Stage 0 Contract Lock

**Objective:** make the whole system executable by removing growth-system contract ambiguity before buildout proceeds.

**Prerequisites:**

- architecture spec authority boundary is accepted
- growth-system spec authority boundary is accepted
- HOLD SCOPE review is the active findings reference

**Scope:**

- lock the Growth Memory Phase 1 subset, write ownership, and deterministic write path
- lock touchpoint, routing-decision, attribution, and lineage semantics
- lock founder review workflow, doctrine enforcement, and delegate scope rules
- lock the canonical error taxonomy and rescue posture for each stateful growth contract
- lock projection versioning, freshness, and skew behavior
- lock the shared snapshot lineage contract and projection-only read posture
- lock dual-axis `conviction_shift` and `buying_readiness` semantics
- lock `control_plane_auth` role/action/scope/reason/audit rules
- lock compatibility meaning for legacy narrowed terms that still appear in plans and code notes
- lock aggregate-benchmark privacy thresholds and suppression rules
- lock the day-1 observability pack and data-plane rollback drill

**Concrete deliverables:**

- implementation-safe sections in the growth-system authority doc for the critical Phase 0-2 objects
- named failure states and rescue posture for each stateful growth contract
- one explicit split between implementation-blocking contracts and later-stage directional modules
- one projection coherence contract covering shared lineage, freshness budgets, and skew fallback
- one `review_object` contract covering uniqueness, CAS apply, and failed-apply semantics
- one `control_plane_auth` matrix for cross-tenant reads, writes, replay, and benchmark access
- one dependency graph showing which contracts unblock which later stages
- one explicit compatibility mapping for legacy persuasion-platform labels
- one canonical stage-gated test matrix
- one canonical day-1 observability and rollback package

**Owned contracts:**

- the core growth-system contracts at specification level
- the legacy compatibility bridge

**Dependencies:**

- architecture spec
- growth-system spec
- HOLD SCOPE review
- existing ADRs: resilience, event validation, audit logging, tenant-aware scheduling, compliance conflict resolution

**Acceptance criteria:**

- no implementer has to invent meanings for the core growth-system contracts
- every Stage 2-4 build item can point to a specific authority section
- duplicate/late ingest, replay determinism, stale review handling, projection skew, doctrine fail-closed behavior, and benchmark suppression are all explicitly covered
- operator and decisioning reads have one shared snapshot-lineage contract
- dual-axis conviction and readiness semantics are canonical rather than implied
- legacy narrowed terms are mapped rather than left ambiguous

**Verification suite:**

- contract consistency pass across architecture spec, growth-system spec, phase plans, and TODOs
- reviewer confirmation that each critical growth contract has identity, lifecycle, and failure semantics
- stage-gated matrix review for required unit, integration, system, and drill coverage
- terminology pass confirming old narrowed labels only appear through compatibility context

**Observability requirements:**

- each contract names the metrics, logs, or audit signals needed to detect silent failure
- advisory/assisted rollout gates include a data-plane freeze/replay drill, not just code rollback

**Rollout gate:**

- Stage 2-4 execution does not begin until Stage 0 artifacts are complete enough to remove guesswork

**Rollback posture:**

- no runtime rollback; unresolved contracts stay blocked from implementation

**Not yet enabled:**

- any runtime behavior beyond current repo foundations

## Stage 1 Shared Platform Foundation

**Objective:** establish the shared platform substrate that all later stages depend on.

**Prerequisites:**

- Stage 0 contract lock complete for any Stage 2-4 dependency

**Scope:**

- knowledge substrate
- worker specs
- HVAC industry pack extraction
- tenant config and RLS
- harness infrastructure
- CI and repository validation
- recovery, audit, and resilience baselines already established in ADRs

**Concrete deliverables:**

- validated `knowledge/` tree with MOCs and frontmatter
- validated worker-spec YAMLs
- extracted HVAC pack with provenance
- Supabase tenant/RLS schema and seed data
- harness + LiteLLM + Redis baseline deployment shape
- CI for knowledge, packs, worker specs, and harness tests

**Owned contracts:**

- shared platform foundation only; no persuasion runtime steering yet

**Dependencies:**

- current production V2 reference
- architecture spec shared-platform sections

**Acceptance criteria:**

- validation scripts pass
- tenant isolation is enforced and tested
- harness infrastructure is health-checking
- industry pack and worker-spec assets are buildable inputs for later stages

**Verification suite:**

- repository validators
- tenant-isolation tests
- integration smoke test for shared platform composition

**Observability requirements:**

- health checks for harness and LiteLLM
- audit logs for admin/setup actions
- local recovery visibility for degraded persistence paths already defined by ADR

**Rollout gate:**

- foundation assets are stable enough for Stage 2 event ingest and persistence work

**Rollback posture:**

- git revert for docs/config
- migration rollback or forward-fix where safe

**Not yet enabled:**

- growth-system decisioning
- operator projections
- runtime decision influence

## Stage 2 Capture-Only

**Objective:** build the growth-memory capture substrate without allowing it to steer behavior.

**Prerequisites:**

- Stage 0 contract lock complete for `persuasion_path`, `graph_mutation`, `lineage_chain`, and projection scaffolding
- Stage 1 shared platform foundation accepted

**Scope:**

- append-only `event_spine`
- deterministic Growth Memory write planning and apply
- canonical growth-path reporting view plus legacy `persuasion_path` compatibility
- end-to-end lineage linkage
- replay tooling
- projection refresh scaffolding with explicit stale markers
- shared snapshot lineage ids and projection-only read contract

**Concrete deliverables:**

- typed validated ingest with quarantine path
- duplicate/late event idempotency
- mutation logging and hold states
- replayable graph evolution over a bounded sample window
- graph/projection snapshot versioning scaffold
- shared-lineage fallback that keeps operator and decisioning reads coherent under refresh failure

**Owned contracts:**

- touchpoint and attribution substrate
- deterministic write and lineage semantics
- growth-path reporting compatibility
- projection snapshot identifiers

**Dependencies:**

- event validation contract
- audit logging and degraded persistence ADRs
- tenant isolation and RLS

**Acceptance criteria:**

- event schema coverage is stable
- deterministic write results are reproducible
- lineage chain is queryable end to end
- derived-state promotion can freeze while event capture remains live

**Verification suite:**

- duplicate/late ingest tests
- deterministic replay tests
- mutation conflict hold tests
- lineage reconstruction tests
- projection skew fallback tests

**Observability requirements:**

- ingest accepted/quarantined/duplicate counters
- mutation applied/held/conflict counters
- replay mismatch signal
- stale projection marker visibility

**Rollout gate:**

- no advisory surfaces until replay and lineage confidence are demonstrated

**Rollback posture:**

- freeze derived-state promotion
- keep event spine live
- repair via replay from append-only evidence

**Feature-flag posture:**

- capture-only enabled
- decision influence disabled
- founder recommendations disabled
- downstream actioning disabled

**Not yet enabled:**

- packet or queue surfaces
- runtime decisioning
- founder apply path

## Stage 3 Advisory-Only

**Objective:** make growth insight visible and reviewable without letting it change runtime behavior.

**Prerequisites:**

- Stage 2 acceptance complete
- Stage 0 contract lock complete for `review_object` and projections

**Scope:**

- founder and operator projections
- weekly digest or packet
- review queue
- proof debt, doctrine conflict, and asset-gap queues
- founder-readable explanations
- stale snapshot rejection semantics for review actions
- shared review/apply idempotency semantics

**Concrete deliverables:**

- operator packet and queue projection refresh
- `review_object` creation and durable state representation
- packet/dashboard/queue consistency around shared review state
- explicit stale review action handling
- active-review uniqueness and supersede behavior

**Owned contracts:**

- `review_object`
- `operator_projections`

**Dependencies:**

- Stage 2 graph snapshots
- audit logs
- control-plane read surfaces

**Acceptance criteria:**

- packet, dashboard, and queue remain consistent through shared `review_object` state
- stale review actions are rejected or rebased explicitly
- founder can explain winning and decaying paths using projections

**Verification suite:**

- projection stale fallback tests
- stale snapshot rejection tests
- cross-surface consistency tests

**Observability requirements:**

- review-object counts by state
- projection freshness and skew
- founder packet assembly fallback visibility

**Rollout gate:**

- no runtime decision changes until advisory views stay coherent under stale/failure scenarios

**Rollback posture:**

- disable advisory surfaces
- keep capture-only running
- fall back to last good projection snapshots where allowed

**Feature-flag posture:**

- advisory views enabled
- runtime decision influence disabled
- auto-apply disabled

**Not yet enabled:**

- approved action application
- automated downstream actions

## Stage 4 Assisted + Closed-Loop

**Objective:** first allow human-approved steering, then bounded automation once trust thresholds are met.

**Prerequisites:**

- Stage 3 acceptance complete
- Stage 0 contract lock complete for `control_plane_auth`
- feature-flag and doctrine/health gating paths implemented

**Scope:**

- `decisioning_projections`
- control-plane apply path
- approval/resume semantics
- bounded routing/proof sequencing influence
- closed-loop actioning guarded by doctrine and health gates

**Concrete deliverables:**

- assisted routing and journey suggestions
- apply/retry/failed_apply semantics for `review_object`
- approval-bound resumable actions
- bounded closed-loop execution behind feature flags
- freeze/rollback procedures for doctrine or health outages

**Owned contracts:**

- `decisioning_projections`
- `control_plane_auth`
- `review_object` apply semantics

**Dependencies:**

- Stage 3 operator state
- policy gate and V&V
- alerting, kill switches, and control-plane operations

**Acceptance criteria:**

- assisted decisions outperform static defaults
- doctrine conflicts remain visible and reviewable
- founder override rate stays within scorecard bounds
- closed-loop behavior respects scorecard floors and fails closed on doctrine/health outage

**Verification suite:**

- stale apply/double-submit tests
- doctrine outage fail-closed tests
- projection skew under runtime reads
- bounded closed-loop freeze and rollback drill

**Observability requirements:**

- review apply success/stale/failed counters
- doctrine blocked-action count
- decisioning projection freshness
- closed-loop pause/freeze visibility

**Rollout gate:**

- assisted mode first
- closed-loop only after replay, rescue, and visibility are proven under load

**Rollback posture:**

- freeze closed-loop actions first
- freeze assisted influence if necessary
- keep event capture and advisory views live
- replay or retry from lineage and event spine

**Feature-flag posture:**

- assisted mode behind explicit flags
- closed-loop behind separate, narrower flags

**Not yet enabled:**

- cross-funnel path expansion
- benchmark-informed actions
- wedge replication flows

## Stage 5 Cross-Funnel Expansion

**Objective:** extend the same persuasion platform from acquisition/sales into onboarding, retention, churn, and referral.

**Prerequisites:**

- Stage 4 stable in production-like conditions
- path identity and lineage confirmed reusable across funnel stages

**Scope:**

- onboarding events
- retained-usage evidence
- churn and recovery evidence
- referral inheritance rules

**Concrete deliverables:**

- expanded event taxonomy and mutation coverage
- lifecycle-context coverage beyond acquisition and sales
- reused projections updated for cross-funnel explanation

**Owned contracts:**

- no new core contracts; reuses `persuasion_path`, `graph_mutation`, `lineage_chain`, and projections

**Dependencies:**

- Stage 2-4 graph, projections, and review flow
- product-core signals beyond acquisition/sales

**Acceptance criteria:**

- cross-funnel evidence improves proof or routing quality
- explanations remain legible after broader scope
- no new funnel-specific parallel memory system is introduced

**Verification suite:**

- cross-funnel replay scenarios
- referral inheritance correctness tests
- lifecycle explanation tests

**Observability requirements:**

- stage-coverage metrics by lifecycle context
- cross-funnel mutation hold/conflict counters

**Rollout gate:**

- cross-funnel expansion must reuse existing contracts, not redefine them

**Rollback posture:**

- disable new event sources and derived views
- preserve acquisition/sales pathing

**Feature-flag posture:**

- funnel-stage flags by source and tenant cohort

**Not yet enabled:**

- cross-tenant benchmarks
- wedge transfer templates

## Stage 6 Federated Benchmarks

**Objective:** introduce aggregate-only cross-tenant learning without leaking tenant-identifying data.

**Prerequisites:**

- Stage 5 stable
- benchmark privacy thresholds locked in Stage 0
- cohort safety and suppression rules implemented

**Scope:**

- cohort definitions
- aggregate path comparisons
- benchmark-informed review objects

**Concrete deliverables:**

- benchmark aggregation jobs
- suppression path for undersized or identifying slices
- benchmark lineage and audit visibility

**Owned contracts:**

- `federated_benchmark`

**Dependencies:**

- tenant isolation
- data classification
- lineage

**Acceptance criteria:**

- privacy thresholds are proven
- no tenant-identifying leakage appears in outputs
- benchmarks augment existing review flows rather than creating parallel decision surfaces

**Verification suite:**

- privacy-safe benchmark suppression tests
- cohort threshold tests
- lineage coverage tests

**Observability requirements:**

- suppressed benchmark count
- cohort eligibility metrics
- benchmark generation lineage/audit

**Rollout gate:**

- benchmark publication blocked unless suppression and privacy checks are proven

**Rollback posture:**

- disable benchmark publication
- preserve tenant-local persuasion graph and projections

**Feature-flag posture:**

- aggregation and publication flags separated

**Not yet enabled:**

- raw cross-tenant sharing
- benchmark-led automated actions

## Stage 7 Wedge Replication

**Objective:** reuse the platform to transfer proven persuasion patterns into new wedges without rebuilding the system.

**Prerequisites:**

- at least one wedge shows repeated proven paths
- Stages 1-6 stable enough to be reused without redesign

**Scope:**

- wedge transfer templates
- proof-transfer candidates
- replication scorecards

**Concrete deliverables:**

- new-wedge bootstrap workflow built from existing contracts
- replication readiness scorecard
- explicit separation between reusable platform primitives and wedge-specific content

**Owned contracts:**

- no new core contracts; uses existing platform primitives unchanged

**Dependencies:**

- benchmark and cross-funnel evidence where useful
- industry-pack extraction and tenant config patterns

**Acceptance criteria:**

- a new wedge reuses graph, governance, and control-plane primitives
- replication time drops materially versus the first wedge
- no wedge-specific fork of the platform architecture is introduced

**Verification suite:**

- wedge bootstrap dry run
- platform-reuse checklist
- regression comparison versus the first wedge

**Observability requirements:**

- wedge setup lead time
- reuse-versus-customization ratio

**Rollout gate:**

- replication starts only after one wedge proves repeatable path quality

**Rollback posture:**

- disable new wedge onboarding while preserving the original wedge

**Feature-flag posture:**

- wedge enablement by pack and tenant cohort

**Not yet enabled:**

- bespoke per-wedge platform forks

## Dependency Graph

```text
Stage 0 Contract Lock
  -> Stage 1 Shared Platform Foundation
  -> Stage 2 Capture-Only

Stage 1 Shared Platform Foundation
  -> Stage 2 Capture-Only

Stage 2 Capture-Only
  -> Stage 3 Advisory-Only

Stage 3 Advisory-Only
  -> Stage 4 Assisted + Closed-Loop

Stage 4 Assisted + Closed-Loop
  -> Stage 5 Cross-Funnel Expansion

Stage 5 Cross-Funnel Expansion
  -> Stage 6 Federated Benchmarks

Stage 6 Federated Benchmarks
  -> Stage 7 Wedge Replication
```

Core contracts reused unchanged after they are introduced:

- `persuasion_path`: Stages 2-7
- `graph_mutation`: Stages 2-7
- `lineage_chain`: Stages 2-7
- `review_object`: Stages 3-7
- `operator_projections`: Stages 3-7
- `decisioning_projections`: Stages 4-7
- `control_plane_auth`: Stages 4-7
- `federated_benchmark`: Stages 6-7

## Master Acceptance Scenarios

The program is not considered executable unless these scenarios are concretely covered in the stage plans and referenced contracts:

- duplicate and late event ingest remain idempotent
- graph mutation conflict enters a visible hold state
- stale review action is rejected or explicitly rebased
- projection stale fallback preserves coherent reads
- doctrine outage causes fail-closed behavior
- bounded closed-loop can freeze and roll back without losing event capture
- privacy-safe benchmark suppression blocks unsafe outputs

## Consistency Requirements

- Every execution-critical instruction previously unique to the old phase plans must either appear in this master plan or be explicitly referenced from it.
- The architecture spec and growth-system spec should not carry independent execution order after this plan lands.
- The HOLD SCOPE review remains a rationale artifact, not the active sequencing document.
