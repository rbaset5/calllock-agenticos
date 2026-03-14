---
id: growth-system-design
title: CallLock Persuasion Graph Platform Spec
graph: growth-system
owner: founder
last_reviewed: 2026-03-14
trust_level: curated
progressive_disclosure:
  summary_tokens: 500
  full_tokens: 15000
status: Draft - v5: Persuasion Graph Platform Spec
---

# CallLock Persuasion Graph Platform Spec

**Date:** March 14, 2026  
**Status:** Draft - v5  
**Owner:** Founder / GTM / Product / Platform

## Summary

CallLock should build a wedge-first persuasion platform, not a loose collection of GTM modules.

The platform exists to discover, explain, and repeat the persuasion paths that move the right home-service buyer from first signal to booked pilot, onboarding, retained usage, and referral. The system stays wedge-first in delivery, but it is cross-funnel in design: one canonical persuasion model should span acquisition, sales, onboarding, retention, and referral.

This revision fixes the platform shape:

- `persuasion_path` is a first-class persisted object, not only a reporting lens.
- canonical graph state is mutated only by deterministic, validated code.
- event capture is append-only; projections serve decisioning and operator views.
- founder and operator access happens through a separate internal control plane.
- founder decisions flow through one canonical `review_object` state machine.
- observability follows a full lineage chain from raw event to downstream effect.
- rollout follows a trust ladder: capture-only, advisory-only, assisted, then closed-loop.
- future cross-tenant learning is aggregate-only via federated benchmarks, never shared raw graph state.

The moat is not more automation volume. The moat is trustworthy persuasion memory with governed proof, decision, and founder-feedback loops.

## 1. Purpose

Design a persuasion platform that learns which paths create believable movement for the right buyer and turns that learning into safe, explainable operating decisions.

The platform should answer:

- which buyer shape is actually valuable
- which pain is activated
- which objection blocks motion
- which proof changes conviction
- which next action matches readiness
- which path produces booked pilots, successful onboarding, retained usage, and referrals

### 1.1 Wedge-First Thesis

CallLock should still prove one wedge before broadening execution.

Recommended initial wedge: **HVAC first**.

Wedge-first delivery does not mean GTM-only architecture. The system should be able to connect:

- acquisition signals
- sales interactions
- booked pilot outcomes
- onboarding progress
- retained product usage
- churn and win-back signals
- referral activity

The first rollout can be HVAC plus cold email, but the core model should already support the full persuasion loop.

### 1.2 Core Outcome

The goal is not generic "growth automation."

The goal is:

**finding and repeating the fastest believable path to "that is exactly my problem" for the right home-service buyer, then extending that path through pilot, onboarding, retention, and referral.**

### 1.3 What This System Is Not

This system is not:

- a broad content farm
- a freeform copy generator
- a dashboard-only analytics sidecar
- a second product core
- a shared raw cross-tenant memory pool

## 2. Fixed Decisions

These decisions are part of the spec, not open questions:

1. `persuasion_path` is a persisted canonical object.
2. The platform spans acquisition, sales, onboarding, retention, and referral.
3. Raw events are append-only source evidence.
4. Canonical graph mutation is deterministic and validated.
5. Models may propose annotations and recommendations, but they do not directly mutate canonical graph state.
6. Decisioning and operator surfaces read materialized projections, not live multi-join graph queries.
7. Founder decisions use one `review_object` state machine across packet, dashboard, and queues.
8. Founder/operator access is a separate internal control plane, not an extension of tenant-facing roles.
9. Cross-tenant learning is future aggregate benchmarking only.
10. Existing harness/product-core boundaries from the architecture spec remain intact.

## 3. System Boundary

The platform sits on top of the existing CallLock architecture. It does not replace the shared product core or the agent harness.

Existing boundaries remain:

- product core owns tenant-facing app behavior and shared operational workflows
- harness owns orchestration, policy, eval, observability, and async automation
- persuasion graph platform owns persuasion intelligence, review objects, scorecards, and operator projections

The platform reads from and writes back into those layers through controlled contracts.

```text
   PRODUCT CORE + HARNESSED WORKFLOWS
   ----------------------------------
   acquisition       sales         product         retention      referral
        \              |              |                |             /
         \             |              |                |            /
          +------------+--------------+----------------+-----------+
                                       |
                                       v
                     +---------------------------------------+
                     |   PERSUASION GRAPH PLATFORM           |
                     |   event spine -> graph -> projections |
                     +---------------------------------------+
                                       |
                      +----------------+----------------+
                      |                                 |
                      v                                 v
             decisioning surfaces               operator control plane
```

## 4. Canonical Model

### 4.1 Canonical Learning Object

The canonical learning object is still the persuasion path, but now it is an owned platform object:

`persuasion_path = segment x pain x objection x proof x conviction_shift x readiness_shift x outcome x lifecycle_context`

Every major metric, recommendation, scorecard, proof decision, and founder review should be explainable in this language.

### 4.2 Event Spine

`event_spine` is the append-only evidence layer.

It stores raw but validated events from:

- acquisition
- outbound and inbound sales
- page and demo engagement
- meetings and booked pilots
- onboarding events
- product usage outcomes
- churn and win-back events
- referral events
- founder/operator actions

The event spine is the highest truth for persuasion evidence. Nothing in a projection or packet is allowed to outrank the source evidence that generated it.

### 4.3 Canonical Graph State

Canonical graph state is derived from the event spine by deterministic mutation code.

Graph state includes:

- `persuasion_path` objects
- evidence links and counts
- proof coverage entries
- doctrine conflict records
- lifecycle path state
- review-object references

### 4.4 Projections

The graph is not queried directly for every operational question.

Instead, it feeds:

- `decisioning_projections`
- `operator_projections`
- scorecard projections
- audit and lineage projections

This keeps hot decision paths, founder views, and replay/recompute paths separate.

## 5. Durable Subsystems

The platform should be described through durable subsystems, not a sprawling catalog of adjacent engines.

### 5.1 Graph & Evidence

Responsibilities:

- ingest append-only evidence
- validate, normalize, and store event records
- deterministically mutate graph state
- maintain proof and path state
- preserve lineage and replayability

### 5.2 Decisioning

Responsibilities:

- choose the next bounded action using projections
- route approved proof, templates, and journeys
- adapt sequencing based on conviction and readiness
- remain bounded by doctrine, policy, and rollout mode

### 5.3 Governance Intelligence

Responsibilities:

- score evidence quality
- compute gates and scorecards
- generate path-level recommendations
- surface proof debt
- detect doctrine conflicts
- detect learning integrity issues

### 5.4 Operator Control Plane

Responsibilities:

- expose review objects
- render founder packet and dashboard views
- show lineage and investigation views
- enforce internal auth and action audit
- support pause, retry, replay, and rollback workflows

### 5.5 Outputs, Not Peer Subsystems

These are outputs or views over the platform, not independent engines:

- Founder Weekly Operating Packet
- Founder Dashboard
- Strategic Intelligence Briefing
- audit summaries
- scorecards
- recommendation queues
- proof debt queues
- doctrine conflict queues

## 6. Architecture Overview

```text
                                      EVENT SOURCES

   acquisition     sales calls      meetings/pilots     product usage    churn/referral
        |               |                 |                   |                |
        +---------------+-----------------+-------------------+----------------+
                                        |
                                        v
                              +----------------------+
                              |  EVENT SPINE         |
                              |  append-only evidence|
                              +----------------------+
                                        |
                           schema valid? |  no -> quarantine + audit
                                        v
                              +----------------------+
                              | GRAPH MUTATION       |
                              | deterministic only   |
                              +----------------------+
                                        |
                     +------------------+------------------+
                     |                                     |
                     v                                     v
         +--------------------------+         +---------------------------+
         | DECISIONING PROJECTIONS  |         | OPERATOR PROJECTIONS      |
         | routing / proof / journey|         | packet / dashboard / queue|
         +--------------------------+         +---------------------------+
                     |                                     |
                     v                                     v
            bounded execution surfaces             founder/operator control plane
                     |                                     |
                     +------------------+------------------+
                                        |
                                        v
                                 downstream effects
                                        |
                                        v
                                   event spine
```

### 6.1 Mutation Boundary

This boundary is strict:

- models may classify, summarize, score, and propose
- deterministic code validates those proposals
- only deterministic code writes canonical graph state

If a proposed mutation cannot be validated, it is not applied.

### 6.2 Cross-Funnel Coverage

Every supported funnel stage should resolve into the same graph:

- acquisition path discovery
- sales conversion motion
- booked pilot and onboarding transition
- retained usage and expansion evidence
- churn and recovery evidence
- referral inheritance and transfer paths

## 7. Public Interfaces and Core Types

This section defines the platform-critical interfaces that other layers should assume.

### 7.1 `persuasion_path`

Canonical persisted object describing one path shape and its current state.

Ownership:

- owner subsystem: Graph & Evidence
- allowed writers: deterministic graph mutation code only
- idempotency: path upsert by stable path key plus versioned mutation input
- visibility: readable via projections, auditable via lineage

Representative schema:

```json
{
  "persuasion_path_id": "ppath_01",
  "path_key": {
    "segment": "hvac_owner_operator_missed_calls",
    "pain": "missed_calls",
    "objection": "already_have_answering_service",
    "proof": "comparison_asset_v2",
    "conviction_shift": "up",
    "readiness_shift": "flat",
    "outcome": "meeting_booked",
    "lifecycle_context": "acquisition_to_evaluation"
  },
  "current_state": "active",
  "proof_coverage_status": "weak",
  "confidence": 0.78,
  "evidence_window": {
    "touchpoints": 84,
    "pilots": 6,
    "retained_customers": 2
  },
  "latest_projection_version": 12
}
```

### 7.2 `graph_mutation`

A deterministic mutation request generated from one or more validated events.

Ownership:

- owner subsystem: Graph & Evidence
- allowed writers: mutation planner and replay system
- idempotency: mutation key derived from lineage root plus mutation type
- visibility: mutation result logged and auditable

Representative schema:

```json
{
  "graph_mutation_id": "gmut_01",
  "mutation_type": "path_evidence_merge",
  "source_event_ids": ["evt_01", "evt_02"],
  "target_persuasion_path_id": "ppath_01",
  "planner_version": 3,
  "status": "applied",
  "applied_at": "2026-03-14T12:00:00Z"
}
```

### 7.3 `review_object`

Unified state machine for founder/operator decisions.

Ownership:

- owner subsystem: Operator Control Plane
- allowed writers: governance intelligence creates; control plane applies state transitions
- idempotency: one active review object per subject/version pair unless superseded
- visibility: packet, dashboard, queues, and audit surfaces all read this object

State machine:

```text
draft
  -> reviewable
  -> approved
  -> overridden
  -> deferred
  -> failed_apply
  -> superseded
```

Representative schema:

```json
{
  "review_object_id": "rev_01",
  "review_type": "proof_brief",
  "subject_type": "persuasion_path",
  "subject_id": "ppath_01",
  "subject_version": 12,
  "status": "reviewable",
  "recommended_action": "build_comparison_asset",
  "reasoning_summary": "High-volume objection with weak conviction movement",
  "lineage_chain_id": "lin_01"
}
```

### 7.4 `lineage_chain`

Stable end-to-end trace for one persuasion decision thread.

Ownership:

- owner subsystem: Graph & Evidence with Operator Control Plane hooks
- allowed writers: deterministic lineage assembler only
- idempotency: stable root chain per causal thread
- visibility: required for audit, debugging, packet drill-down, and replay

Representative schema:

```json
{
  "lineage_chain_id": "lin_01",
  "raw_event_ids": ["evt_01", "evt_02"],
  "graph_mutation_ids": ["gmut_01"],
  "persuasion_path_id": "ppath_01",
  "review_object_ids": ["rev_01"],
  "founder_action_ids": ["act_01"],
  "downstream_effect_ids": ["eff_01"]
}
```

### 7.5 `decisioning_projections`

Materialized views used for bounded runtime decisions.

Ownership:

- owner subsystem: Decisioning
- allowed writers: projection refresh pipeline only
- idempotency: projection version pinned to graph version
- visibility: decision logs must include projection version used

Representative contents:

- routing candidates
- proof sequencing recommendations
- journey next-step recommendations
- scorecard eligibility views
- safe fallback actions

### 7.6 `operator_projections`

Materialized views used for founder/operator interfaces.

Ownership:

- owner subsystem: Operator Control Plane
- allowed writers: projection refresh pipeline only
- idempotency: projection version pinned to graph and review-object versions
- visibility: packet and dashboard show snapshot/version metadata

Representative contents:

- weekly packet view
- daily health view
- review queue view
- investigation view
- doctrine conflict view
- proof debt ranking view

### 7.7 `control_plane_auth`

Separate internal authorization model for cross-tenant operator work.

Ownership:

- owner subsystem: Operator Control Plane
- allowed writers: internal auth administration only
- idempotency: role grants are versioned and audited
- visibility: every cross-tenant action must be audit logged with actor and reason

Principles:

- tenant-facing roles do not expand into internal control-plane roles
- cross-tenant reads are explicit
- cross-tenant writes are rarer, reasoned, and auditable
- approval and override actions are identity-bound

### 7.8 `federated_benchmark`

Future aggregate-only interface for cross-tenant learning.

Ownership:

- owner subsystem: Governance Intelligence
- allowed writers: benchmark aggregation jobs only
- idempotency: benchmarks versioned by cohort definition and time window
- visibility: only aggregate-safe results may be exposed

Principles:

- no raw tenant graph sharing
- no tenant-identifying output
- minimum cohort thresholds required
- benchmark generation is blocked if privacy thresholds are not met

## 8. Graph & Evidence Model

### 8.1 Source of Truth Hierarchy

1. event spine
2. graph mutations
3. canonical persuasion paths
4. projections
5. packets, dashboards, and summaries

### 8.2 Single-Writer Rules

- event ingestion owns event records
- mutation pipeline owns canonical graph writes
- governance intelligence owns scorecard and recommendation computation
- operator control plane owns review-object state transitions
- execution surfaces own downstream effect confirmation

### 8.3 Proof and Belief Semantics

Belief remains split:

- `conviction_shift`: did the prospect become more convinced the claim is true?
- `readiness_shift`: did the prospect become more ready to act now?

Proof is evaluated primarily through conviction movement. Journey timing can use both conviction and readiness when confidence is sufficient.

### 8.4 Proof Supply Chain

Proof gaps are not a dashboard-only artifact. They become reviewable work.

```text
objection detected
  -> persuasion path weak or gap state
  -> governance intelligence creates recommendation
  -> review_object created
  -> founder/operator approves, overrides, or defers
  -> proof asset work executes
  -> downstream effect recorded
  -> new evidence re-enters event spine
  -> proof coverage recomputed
```

### 8.5 Referral Inheritance

Referral paths are not a separate funnel. They are persuasion paths with inherited proof context.

Default referral rule:

- referred prospects may skip generic pain-recognition steps
- inherited trust should be explicit in the path context
- referral evidence must remain attributable and audit-safe

## 9. Decisioning Model

Decisioning reads projections, not raw graph joins.

### 9.1 Bounded Runtime Decisions

Decisioning can:

- select from approved templates
- choose approved proof order
- adapt journey sequence within allowed boundaries
- hold or queue risky actions when doctrine or health checks fail

Decisioning cannot:

- improvise new customer-facing claims
- bypass doctrine
- mutate canonical graph state directly
- treat low-confidence evidence as action-grade truth

### 9.2 Runtime Inputs

- decisioning projections
- doctrine state
- rollout mode
- feature flags
- lifecycle eligibility
- health and suppression gates

### 9.3 Runtime Outputs

- routing decision logs
- proposed downstream actions
- queued actions when blocked
- effect confirmations written back as events

## 10. Governance Intelligence

Governance intelligence is the analysis layer that keeps the platform legible and safe.

It computes:

- scorecards and gate eligibility
- proof coverage state
- doctrine conflicts
- learning integrity alerts
- path recommendations
- proof debt priorities
- benchmark candidates

### 10.1 Wedge Fitness Scorecard

The wedge fitness score remains a trend metric, not a permission slip.

Representative components:

- booked pilot rate
- attribution completeness
- proof coverage
- founder alignment
- learning velocity
- retention quality
- segment clarity
- cost efficiency
- conviction depth
- readiness quality

Gate floors remain binding:

| Gate | Trend requirement | Component floors that all must pass |
|---|---|---|
| Advisory eligibility | Trend above 30 | attribution completeness >= 0.7; doctrine stable for 1 week |
| Assisted eligibility | Trend above 45 | proof coverage >= 0.5; conviction confidence usable on top objections |
| Closed-loop eligibility | Trend above 60 | founder override rate < 0.4; readiness confidence usable in routing |
| Cross-funnel eligibility | Trend above 70 | onboarding attribution usable; retention quality >= 0.7 |
| Replication eligibility | Trend above 75 | at least one proven path repeated twice across qualified cohorts |

Hard kills remain outside the scorecard:

- sender reputation failure
- attribution collapse
- major data integrity failure
- doctrine unavailability on risky paths

### 10.2 Recommendation Types

Governance intelligence can emit review objects for:

- proof creation or improvement
- routing changes
- journey changes
- doctrine review prompts
- experiment proposals
- kill recommendations

## 11. Operator Control Plane

The founder/operator experience should feel like one control plane with multiple views, not many overlapping tools.

### 11.1 Core Views

- daily health glance
- weekly operating packet
- review queue
- proof debt queue
- doctrine conflict queue
- investigation view

### 11.2 Unified Review Model

All founder decisions should resolve through the same `review_object` state machine.

That means:

- packet items are review-object slices
- dashboard cards are review-object slices
- queue entries are review-object slices
- audit summaries reference review objects directly

This prevents stale-state divergence across surfaces.

### 11.3 Internal Control Plane Boundary

The operator control plane is a separate trust zone.

It should support:

- explicit cross-tenant read access
- narrow cross-tenant write access
- reason-required overrides
- replay and rollback actions
- approval history and actor identity

## 12. Failure Handling and Rescue Registry

General degraded-mode language is not sufficient. Failure handling must be codepath-specific.

### 12.1 Failure Policy

- silent drop is forbidden
- every failure has a named state
- every risky failure is either quarantined, held, retried, or failed closed
- every rescue path is observable in logs, metrics, and operator views

### 12.2 Error and Rescue Registry

| Codepath | Failure mode | Named failure | Rescue action | Resulting state | Visibility |
|---|---|---|---|---|---|
| event ingest | malformed payload | `EventSchemaValidationError` | reject and quarantine | `quarantined_event` | ingest failure counter + audit |
| event ingest | duplicate or late event | `IdempotencyConflictError` | merge or noop by idempotency key | `accepted_duplicate` | duplicate-event metric |
| graph mutation | missing path key | `MissingPathKeyError` | hold mutation; require reviewable repair path | `mutation_hold` | critical operator alert |
| graph mutation | conflicting merge target | `PathMergeConflictError` | do not apply; create conflict review object | `mutation_hold` | mutation conflict queue |
| belief inference | malformed model output | `BeliefInferenceParseError` | store analysis-only note; no graph mutation | `analysis_only` | inference failure counter |
| belief inference | low-confidence result | `BeliefInferenceLowConfidence` | exclude from decisioning | `analysis_only` | low-confidence metric |
| doctrine evaluation | registry unavailable | `DoctrineRegistryUnavailable` | fail closed; queue risky actions | `blocked_pending_doctrine` | critical alert |
| doctrine evaluation | hard-rule conflict | `DoctrineConflictError` | block or escalate through review object | `blocked_for_review` | doctrine conflict queue |
| review apply | stale snapshot | `ReviewSnapshotStaleError` | reject and require refresh or rebase | `reviewable` | stale-action warning |
| review apply | downstream change failed | `ReviewApplyFailedError` | mark failed_apply; preserve intent and retry path | `failed_apply` | review failure queue |
| packet assembly | projection stale or missing | `OperatorPacketAssemblyError` | render raw scorecard plus open review objects | `degraded_packet` | founder alert + metric |
| projection refresh | refresh job failed | `ProjectionRefreshError` | keep last good projection; mark stale | `stale_projection` | stale projection alert |

### 12.3 Four Shadow Paths

Every data flow should be traceable through four paths:

```text
happy path:
  valid event -> applied mutation -> refreshed projections -> visible output

nil path:
  missing required source fields -> quarantine -> no mutation

empty path:
  low-information event -> accepted into event spine -> no promotion

error path:
  upstream or mutation failure -> hold/fallback/fail-closed with visible state
```

## 13. Security, Privacy, and Tenant Safety

### 13.1 Tenant Isolation

Existing tenant isolation rules from the architecture spec remain in force.

Requirements:

- tenant-scoped evidence and graph state remain tenant-scoped
- cache and projection keys remain tenant namespaced where applicable
- internal control-plane actions are identity-bound and audited
- service-role machinery is never a substitute for human auth design

### 13.2 Data Classification

Four operating tiers:

- Tier 1: aggregate-safe metrics and scorecards
- Tier 2: pseudonymous prospect-linked operating data
- Tier 3: identifiable prospect or tenant data
- Tier 4: sensitive raw content that must be redacted, minimized, or discarded

Rules:

- raw transcripts and raw replies do not become durable persuasion memory
- dashboard and API views over Tier 2 must enforce minimum cohort safeguards
- benchmark outputs must satisfy privacy thresholds before release

### 13.3 Federated Benchmark Guardrails

Future benchmark aggregation must:

- operate over aggregate-safe cohorts
- reject undersized cohorts
- block tenant-identifying slices
- log benchmark generation lineage
- never expose raw event, path, or review-object data across tenants

## 14. Rollout Ladder

The platform should not launch as one large feature. It should earn trust layer by layer.

### Phase 1 - Capture-Only

Goal: establish the event spine, graph mutation pipeline, and lineage.

Enabled:

- event capture
- canonical path construction
- mutation logging
- replay tooling

Disabled:

- runtime decision influence
- founder recommendations
- automated downstream actions

Exit criteria:

- event schema coverage is stable
- graph mutation results are reproducible
- lineage chain is queryable end to end

### Phase 2 - Advisory-Only

Goal: make the graph visible to operators without letting it steer behavior.

Enabled:

- weekly packet
- dashboard and queue views
- proof debt recommendations
- doctrine conflict views

Disabled:

- runtime decision changes
- auto-applied founder actions
- closed-loop execution

Exit criteria:

- packet, dashboard, and queues stay consistent through shared review objects
- stale review actions are rejected correctly
- founder can explain the winning and decaying paths

### Phase 3 - Assisted Decisioning

Goal: let projections influence routing and proof sequencing with human approval.

Enabled:

- routing suggestions
- journey suggestions
- proof improvement recommendations
- approved action application through control plane

Disabled:

- fully automatic risky downstream actions

Exit criteria:

- assisted decisions outperform static defaults
- doctrine conflicts remain visible and reviewable
- founder override rate stays within scorecard bounds

### Phase 4 - Closed-Loop Actioning

Goal: allow bounded automatic actions once trust thresholds are met.

Enabled:

- bounded closed-loop routing and sequencing
- controlled downstream actions in approved domains
- fail-closed pauses when doctrine or health gates are unavailable

Exit criteria:

- replay, rescue, and lineage remain trustworthy under production load
- closed-loop behavior respects all scorecard floors

### Phase 5 - Cross-Funnel Expansion

Goal: extend the graph from acquisition and sales into onboarding, retention, and referral.

Enabled:

- onboarding and retained-usage evidence
- churn and win-back path analysis
- referral inheritance rules

Exit criteria:

- cross-funnel evidence improves proof and routing quality
- explanation quality survives broader scope

### Phase 6 - Federated Benchmark Layer

Goal: introduce aggregate-only cross-tenant learning.

Enabled:

- benchmark cohorts
- path-level aggregate comparisons
- benchmark-informed review objects

Exit criteria:

- privacy thresholds proven
- no tenant-identifying leakage in benchmark outputs

### Phase 7 - Wedge Replication Platform

Goal: replicate proven persuasion paths into new wedges using the same platform contracts.

Enabled:

- wedge transfer templates
- proof-transfer candidates
- replication scorecards

Exit criteria:

- new wedge setup reuses graph, governance, and control-plane primitives
- replication time drops materially versus the first wedge

## 15. Validation Strategy

This platform should ship only with replayable, deterministic confidence.

### 15.1 Required Test Layers

- unit tests for mutation planners, validators, and state machines
- integration tests for graph writes, projection refresh, and review-object application
- resilience tests for fail-closed and degraded paths
- replay tests for end-to-end graph evolution

### 15.2 Required Scenarios

1. deterministic replay of one week of mixed events, graph mutations, review decisions, and outcomes
2. duplicate and late event ingest with idempotent graph results
3. graph mutation conflict enters a visible hold state
4. stale review action is rejected or rebased explicitly
5. packet, dashboard, and queue stay consistent because they read the same `review_object` state
6. graph promotion is frozen while event capture remains live
7. doctrine unavailability causes fail-closed actioning
8. federated benchmark output proves no tenant-level raw data leakage

### 15.3 Shipping Confidence Test

The shipping-confidence test is not a single unit suite.

It is a deterministic replay that proves the same evidence set produces:

- the same path states
- the same proof debt
- the same blocked gates
- the same review-object queue
- the same founder packet output

### 15.4 Example Replay Scenario

```text
Monday:
  acquisition and outreach events arrive

Tuesday:
  objections and proof-consumption events create a weak path

Wednesday:
  governance intelligence emits a proof review object

Thursday:
  founder approves the proof action

Friday:
  downstream effect lands and new evidence improves the path

Replay requirement:
  same event set -> same lineage -> same path version -> same review state -> same packet summary
```

## 16. Immediate Spec Priorities

The next concept work should sharpen, not broaden:

1. define the stable `persuasion_path` key and versioning rules
2. define deterministic `graph_mutation` categories and merge rules
3. define `review_object` subject types and apply semantics
4. define projection versioning and staleness rules
5. define control-plane roles and audit requirements
6. define federated benchmark privacy thresholds

## 17. Assumptions and Defaults

- This remains concept/spec work only; no implementation starts in this step.
- Existing harness/product-core boundaries remain intact.
- Existing audit, resilience, and tenant-isolation ADRs are reused rather than replaced.
- The wedge-first thesis remains intact.
- Any concept that cannot justify itself through the canonical persuasion graph should be removed, merged, or moved to an appendix.

## Appendix A: Operating Diagrams

### A.1 Review Object Apply Flow

```text
review_object opened
  -> snapshot/version checked
  -> action approved or overridden
  -> downstream change attempted
      -> success -> applied and audited
      -> failure -> failed_apply + retry/replay path
      -> stale snapshot -> reject and refresh
```

### A.2 Rollback Flow

```text
incident detected
  -> freeze closed-loop actioning
  -> if needed, freeze graph promotion
  -> keep event spine live
  -> keep last good projections readable
  -> repair or replay from append-only evidence
  -> re-enable advisory
  -> re-enable assisted
  -> re-enable closed-loop last
```

### A.3 Projection Refresh Flow

```text
graph version committed
  -> decisioning projections refresh
  -> operator projections refresh
  -> stale marker cleared

failure:
  keep last good projection
  mark stale
  alert control plane
```

## Appendix B: Deferred Expansion Boundary

Only concepts that strengthen the canonical persuasion graph belong in the main body.

These remain deferred until graph quality, governance, and privacy prove them safe:

- portfolio-level strategic simulations
- broad channel mix optimization beyond proven wedge needs
- benchmark-heavy executive reporting beyond aggregate-safe cohorts
- new modules that do not materially improve path quality, proof quality, or founder trust
