---
id: growth-system-design
title: CallLock Agentic Growth Loop - Expanded Design Doc
graph: growth-system
owner: founder
last_reviewed: 2026-03-14
trust_level: curated
progressive_disclosure:
  summary_tokens: 500
  full_tokens: 15000
status: Draft - v6: Ambitious Authority Restore
---

# CallLock Agentic Growth Loop - Expanded Design Doc

**Date:** March 14, 2026  
**Status:** Draft - v6: Ambitious authority restore  
**Owner:** Founder / GTM / Product / Platform

## Summary

CallLock should treat growth as a governed learning system, not a loose set of GTM automations.

The system exists to learn, with evidence:

- which wedge to prioritize
- which pain angle to lead with
- which page to route to
- which proof creates belief
- which objections block motion
- which product outcomes should feed messaging
- which channel converts best per dollar

The core loop is:

**channel -> segment -> message -> page -> proof -> CTA -> sales outcome -> product outcome**

This is not an AI SDR project. It is a wedge-discovery, persuasion, and conversion system for home-service businesses, built to become a reusable institutional growth brain.

This restore intentionally replaces the narrower persuasion-graph-only framing. The repo-level meaning of this document is now broader again: it is the main authority for growth-system behavior, object model, learning loops, approval doctrine, and future growth modules.

## 1. Purpose

Design a self-improving growth system for CallLock that learns:

- who converts
- why they convert
- what proof they need
- what language resonates
- what real product behavior creates booked jobs
- what it costs to acquire each segment
- how those learnings should change future routing and prioritization

The goal is not generic automation volume. The goal is:

**finding the fastest believable path to "that is exactly my problem" for the right home-service buyer, then extending that path through pilot, onboarding, retention, and referral.**

## 2. Strategic Context

### 2.1 Positioning anchor

CallLock wins when positioned as the system that **turns missed calls into booked jobs** for home-service businesses.

### 2.2 Initial wedge

Start with one trade where:

- urgency is obvious
- missed calls are expensive
- live response matters
- booking speed matters

Recommended starting wedge: **HVAC first**.

### 2.3 GTM implication

The system should route buyers into simple, believable stories such as:

- missed calls become booked jobs
- answers live when you cannot
- books while you work
- better than voicemail or message-taking

## 3. Authority and Companion Artifacts

This document is the authoritative source for the CallLock growth system:

- Growth Memory and its write-ownership model
- wedge taxonomy, segment taxonomy, angle taxonomy, and asset taxonomy
- routing and learning components
- belief, doctrine, proof coverage, anti-patterns, and wedge fitness
- delegation tiers, founder review semantics, and phase gates
- future growth modules, including pricing, channel mix, geographic intelligence, and aggregate intelligence

The authority split is deliberate:

- [2026-03-12-calllock-agentos-architecture-design.md](/Users/rashidbaset/Documents/calllock-agenticos/docs/superpowers/specs/2026-03-12-calllock-agentos-architecture-design.md) owns shared runtime boundaries, tenancy, deployment posture, harness constraints, and ADR-backed platform rules.
- [whole-system-executable-master-plan.md](/Users/rashidbaset/Documents/calllock-agenticos/plans/whole-system-executable-master-plan.md) owns sequencing, dependency order, readiness gates, and execution order.
- [phases-1-2-foundation-and-core-harness.md](/Users/rashidbaset/Documents/calllock-agenticos/plans/phases-1-2-foundation-and-core-harness.md) provides early implementation detail only.
- [hold-scope-review.md](/Users/rashidbaset/Documents/calllock-agenticos/knowledge/growth-system/hold-scope-review.md) remains a historical review artifact describing the narrowed persuasion-graph phase and the contract-hardening rationale that led into this restore.
- [TODOS.md](/Users/rashidbaset/Documents/calllock-agenticos/TODOS.md) tracks unresolved follow-up work and implementation gaps.

If this document conflicts with the architecture spec on a shared platform constraint, the architecture spec wins. If a phase plan conflicts with this document on growth-system behavior or object semantics, this document wins. If sequencing conflicts arise, the master plan wins.

This authority is intentionally split into two speeds:

- **Implementation-blocking contract authority (Stages 0-2):** identity, lifecycle, failure semantics, auth boundaries, projection coherence, observability, and rollback posture for the core growth contracts. These sections are normative before Stage 2-4 work proceeds.
- **Directional later-stage authority (Stages 3-7):** system-shape modules and future growth capabilities remain authoritative, but they do not override stage gates or force implementation before the master plan enables them.

## 4. Compatibility Bridge for Legacy Contract Terms

The repo currently contains narrowed persuasion-platform vocabulary from the immediately preceding rewrite. Those terms are not silently dropped. They are mapped here explicitly.

| Legacy term | Status | Canonical meaning after restore |
|---|---|---|
| `persuasion_path` | Superseded as primary object; retained as reporting view | Use the canonical growth path `channel -> segment -> message -> page -> proof -> CTA -> sales outcome -> product outcome`, materialized from `touchpoint_log`, `routing_decision_log`, `belief_events`, and attribution views. |
| `graph_mutation` | Mapped | Deterministic Growth Memory writes through the Event Bus, single-writer ownership, Signal Quality gating, and versioned quarantine/rollback protocol. |
| `review_object` | Mapped | Founder Review workflow for recommendations, overrides, doctrine conflicts, asset approvals, and phase-gate decisions. |
| `lineage_chain` | Mapped | End-to-end evidence chain across `touchpoint_log`, `routing_decision_log`, attribution views, `source_version`, and quarantined write lineage. |
| `decisioning_projections` | Mapped | Decision-read views such as `segment_performance`, `angle_effectiveness`, `proof_effectiveness`, `experiment_history`, `belief_events`, and `wedge_fitness_snapshots`. |
| `operator_projections` | Mapped | Founder Dashboard levels, Growth Advisor digest, objection heat map, empathy maps, queue views, and recommendation surfaces. |
| `control_plane_auth` | Mapped | Delegation tiers, Founder Review authority, doctrine enforcement, scope-limited delegate actions, and audit-backed override policy. |
| `federated_benchmark` | Mapped | Phase 7 Aggregate Intelligence Layer: aggregate-only, privacy-governed, cohort-thresholded cross-tenant intelligence. |

Compatibility rule: older plans may continue using the legacy labels, but those labels must be interpreted through this bridge rather than treated as a separate competing contract model.

## 5. Core Thesis

CallLock should not optimize for broad autonomous outreach or arbitrary page volume.

The growth system should optimize for one thing:

**finding the fastest path to "that is exactly my problem" for the right home-service buyer.**

Business value comes from learning faster than competitors:

- who converts
- why they convert
- what proof they need
- what language resonates
- what product behavior creates booked jobs
- what it costs to acquire each segment

The growth loop becomes stronger when GTM learns from real call outcomes and product retention signals.

## 6. Design Principles

### 6.1 Workflow-led outside, agentic inside

Externally the system should feel simple and operational. Internally it can be highly agentic.

### 6.2 Customer path is bounded

Customer-facing behavior is governed by templates, policies, doctrine, and review gates. The LLM is a selector or analyzer, not an unconstrained writer of customer-facing copy.

### 6.3 Strategy remains founder-owned

The system may recommend wedges, messages, proof, and prioritization. Final strategy, pricing, positioning, and claims remain human-controlled.

### 6.4 Structured assets beat freeform sprawl

Pages, outbound assets, proof assets, and experiments should be generated from schemas and templates, not from ad hoc content drift.

### 6.5 Learning must be trustworthy

Every data point is scored before it influences routing or analytics. The system should not confidently learn the wrong thing.

### 6.6 Observability is in scope

The founder should be able to understand what the system learned and why in fifteen minutes per week.

### 6.7 Universal Rescue Doctrine

Every component follows five rules:

1. Never silently swallow.
2. Degrade, do not crash.
3. Escalate on pattern.
4. Every error has a budget.
5. Unrecoverable events go to a dead-letter queue.

### 6.8 Idempotency by default

Every handler is idempotent. Duplicate processing must produce the same result as single processing.

### 6.9 Fail-closed safety systems

Outbound safety, doctrine enforcement, and other risk-bearing gates fail closed.

### 6.10 Channel-aware from day one

Cold email is first, but channel is present in event payloads, schemas, attribution, and experiments from the start.

### 6.11 Single-writer ownership

Each Growth Memory table has one write owner unless it is append-only by construction.

### 6.12 Universal input sanitization

Untrusted text is sanitized before LLM processing. Outputs are validated against schemas and enums.

## 7. System Goal

Build a closed-loop engine that:

1. identifies promising prospects
2. classifies them into useful segments
3. selects the best pain angle and message
4. routes them to the best page
5. selects the best proof
6. measures outcomes end to end
7. scores learning quality
8. synthesizes insights and recommends actions
9. updates future routing and prioritization
10. feeds product outcomes back into messaging
11. tracks cost per acquisition and conversion per dollar
12. guides prospects through a lifecycle journey, not isolated touches

## 8. System Architecture

### 8.1 Architecture overview

The growth system is organized around four interacting layers:

- **Operational layer:** Growth Memory, Event Bus, routing, lifecycle, outbound, attribution
- **Learning layer:** experiments, advisor, scoring, content intelligence, wedge discovery, causal learning
- **Self-awareness layer:** signal quality, integrity monitoring, decision audit, regression monitoring, adversarial resilience
- **Strategic layer:** founder review, doctrine, delegation, dashboard, phase gates, strategic briefing

### 8.2 Existing infrastructure reused

The design builds on current repo and production assets rather than pretending greenfield:

- existing HVAC logic and industry-pack extraction work
- call outcome data from the current harness and metrics emission
- Inngest event infrastructure
- Supabase RLS and tenant isolation
- existing jobs-table patterns for idempotency and superseding
- current observability and alerting patterns

### 8.3 Cross-doc relationship

This document assumes the current shared platform split:

- product core owns tenant-facing behavior and shared operational workflows
- harness owns orchestration, policy, eval, observability, and async automation
- growth system owns persuasion intelligence, routing and learning state, founder review semantics, and strategic GTM memory

### 8.4 Implementation-blocking contract set

Stages 0-2 depend on the following contracts being explicit here rather than inferred in code:

- deterministic `event_spine` append, quarantine, idempotency, and replay behavior
- canonical growth-path reporting plus legacy `persuasion_path` compatibility
- single-writer Growth Memory categories, lineage, and rollback semantics
- shared snapshot lineage, freshness, and skew handling for operator and decision reads
- `review_object` lifecycle, uniqueness, CAS apply, stale snapshot rejection, and failed-apply posture
- `control_plane_auth` role, scope, reason, audit, and fail-closed semantics
- dual-axis `conviction_shift` and `buying_readiness` semantics
- day-1 observability pack and data-plane rollback drill
- federated benchmark privacy thresholds and suppression contract

### 8.5 Directional later-stage modules

Later-stage modules remain in this document because they define the intended system shape, but they are not implementation-blocking until their stage gates are active:

- cross-funnel expansion
- growth intelligence platform modules
- network-effects and aggregate-intelligence modules
- advanced intelligence modules listed in Section 12

### 8.6 Canonical failure taxonomy

The Stage 0 exception vocabulary is part of the contract. Implementations may wrap platform-specific exceptions, but they should preserve these names and outcomes:

| Codepath | Canonical exception | Required rescue posture |
|---|---|---|
| `EventSpineIngest.validate` | `EventSchemaValidationError` | reject, quarantine, and audit |
| `EventSpineIngest.append` | `EventAppendWriteError` | bounded retry, visible backlog or hold state, fail closed for promotion |
| `EventSpineIngest.append` | `IdempotencyConflictError` | merge or no-op by idempotency key, audit duplicate path |
| `GraphMutationPlanner.plan` | `MissingPathKeyError` | hold mutation and open repair queue |
| `GraphMutationPlanner.plan` | `ConvictionReadinessInferenceParseError` | preserve analysis-only output, block canonical write |
| `GraphMutationApplier.apply` | `PathMergeConflictError` | no apply, open visible conflict review |
| `GraphMutationApplier.apply` | `ReplayDeterminismMismatchError` | freeze promotion, alert operator, replay before unfreeze |
| `ProjectionRefresher.refresh*` | `ProjectionRefreshError` | keep last good snapshot, mark stale, alert |
| `ProjectionRefresher.refresh*` | `ProjectionVersionSkewError` | pin both families to last good or mark both stale |
| `ReviewObjectService.create` | `ActiveReviewConflictError` | dedupe or supersede atomically |
| `ReviewObjectService.apply` | `ReviewSnapshotStaleError` | reject, refresh, preserve reviewable state |
| `ReviewObjectService.apply` | `ReviewApplyFailedError` | mark `failed_apply`, preserve intent, retry or replay |
| `ControlPlaneAuth.authorize` | `ControlPlaneAuthorizationError` | fail closed and audit |
| `DoctrineEvaluator.evaluate` | `DoctrineRegistryUnavailable` | fail closed, block risky actions, page operator |
| `BenchmarkAggregator.publish` | `UnsafeBenchmarkCohortError` | suppress output, log reason, expose privacy hold |

## 9. Growth Memory

Growth Memory is the shared knowledge base that makes learning compound rather than remain isolated inside campaigns.

### 9.1 Core tables

Primary Growth Memory tables include:

- `segment_performance`
- `angle_effectiveness`
- `proof_effectiveness`
- `objection_registry`
- `touchpoint_log`
- `prospect_lookalikes`
- `seasonal_patterns`
- `segment_transitions`
- `insight_log`
- `founder_overrides`
- `experiment_history`
- `asset_effectiveness`
- `competitor_mentions`
- `cost_per_acquisition`
- `routing_decision_log`
- `journey_assignments`
- `loss_records`
- `churn_records`
- `referral_links`
- `geographic_market_density`
- `conviction_shift_events`
- `buying_readiness_events`
- `founder_doctrine`
- `doctrine_conflict_log`
- `proof_coverage_map`
- `anti_pattern_registry`
- `wedge_fitness_snapshots`
- `product_usage_correlation`
- `aggregate_intelligence`

Derived compatibility views include:

- `belief_events` as a compatibility projection over `conviction_shift_events` and `buying_readiness_events`
- `persuasion_path` as a reporting view over the canonical growth path contracts

### 9.2 Write ownership

Single-writer ownership is a hard rule:

- Experiment Allocator writes experiment, segment, angle, proof, and asset performance tables
- Sales Insight Layer writes objections and competitor mentions
- Segmentation Engine writes segment assignments and transitions
- Cost Layer writes acquisition and budget views
- Journey Orchestrator writes journey assignments
- Conviction and Readiness Layer writes `conviction_shift_events` and `buying_readiness_events`
- Founder Review UI writes doctrine and overrides
- Growth Advisor writes strategic insights, lookalikes, anti-patterns, and wedge fitness snapshots
- Aggregate Intelligence Layer writes cross-tenant benchmarks in Phase 7

Exceptions are append-only by design:

- `touchpoint_log`
- `insight_log`

### 9.3 Deterministic write contract

Canonical write categories:

- `append_event`
- `normalize_touchpoint`
- `record_routing_decision`
- `derive_conviction_shift`
- `derive_buying_readiness`
- `apply_segment_transition`
- `apply_proof_coverage`
- `apply_wedge_fitness`
- `open_review_object`
- `refresh_projection_snapshot`
- `publish_benchmark`

Every write attempt carries:

- `tenant_id`
- `write_category`
- `idempotency_key`
- `source_event_id` or `source_snapshot_id`
- `source_version`
- `lineage_root_id`
- `applied_at`

Determinism rules:

- one write owner per canonical table or projection family
- same ordered input set produces the same write plan and same snapshot lineage
- duplicate or late inputs merge or no-op by idempotency key rather than forking state
- replay may recompute derived state, but it may not mutate append-only evidence

### 9.4 Projection and read contract

Operator and decisioning reads are projection-only. Request paths do not join across raw Growth Memory tables.

Each projection family must publish:

- `snapshot_lineage_id`
- `snapshot_version`
- `source_high_watermark`
- `generated_at`
- `fresh_until`
- `stale_after`

Coherence rules:

- operator and decisioning projections pin to the same `snapshot_lineage_id`
- skew exists whenever either family advances without the other for the same high-watermark window
- on skew or partial refresh failure, both families either stay on the same last-good snapshot or both render stale
- stale-but-coherent reads are acceptable within the published freshness budget; mixed-freshness reads are not

### 9.5 Data hygiene

- performance data decays over time rather than disappearing
- seasonal patterns preserve year-over-year comparability
- all writes include version metadata
- stale or suspect writes can be quarantined without destroying source evidence

### 9.6 Quarantine and rollback

Every Growth Memory write is tagged with `source_version`. If a component writes bad data:

1. quarantine the affected writes
2. exclude them from downstream decisions
3. review or purge them
4. recompute derived state from append-only touchpoints and source evidence

Data-plane rollback is separate from code rollback:

1. freeze closed-loop actions
2. freeze derived-state promotion if corruption risk exists
3. keep event capture live
4. keep last-good coherent projections readable
5. replay from append-only evidence before unfreezing

### 9.7 Data classification

All data is classified:

- Tier 1: aggregate-safe
- Tier 2: pseudonymous
- Tier 3: identifiable
- Tier 4: sensitive raw inputs that should be redacted at write time

The growth system must preserve these classifications across tables, queries, and future aggregate intelligence.

### 9.8 Aggregate-intelligence privacy contract

Federated benchmark outputs remain aggregate-only and are blocked unless all of the following are true:

- minimum cohort size is at least 20 tenants for any published slice
- no slice may use more than 3 dimensions at once
- no slice may include raw identifiers, tenant names, or replayable event payloads
- any slice that would expose more than 20 percent contribution from a single tenant is suppressed
- suppressed outputs remain auditable through lineage and reason codes

Benchmark outputs must publish:

- `cohort_definition_id`
- `cohort_size`
- `suppression_reason` when blocked
- lineage back to the aggregate-safe inputs used

## 10. Core Components

### 10.1 Prospect Enrichment Pipeline

Purpose: turn raw leads into useful GTM segments.

Outputs include:

- trade
- likely buyer type
- pain profile
- urgency likelihood
- call-volume likelihood
- wedge fit score
- per-field confidence

Key rules:

- sanitize web data before LLM use
- validate outputs against enums
- cache enrichment at the company-domain level
- cap costs and concurrency
- degrade to partial enrichment instead of blocking the whole pipeline

### 10.2 Segmentation Engine

Purpose: map prospects into buckets that determine messaging, routing, and experiments.

Key behavior:

- initial assignment at enrichment time
- event-driven re-segmentation as new signals arrive
- primary and secondary segment support
- explicit `unclassified` fallback
- circuit breaker to stop oscillation

### 10.3 Message Router

Purpose: choose the best pain angle and template family.

Hard rule: the LLM is a selector, not a freeform copywriter for outbound.

Inputs:

- prospect profile
- segment
- lifecycle state
- experiment assignment
- historical performance
- seasonal context
- channel

Outputs:

- selected template
- slot values
- primary angle
- backup angle
- experiment assignment

### 10.4 Template + Slot system

Customer-facing copy is assembled from approved assets:

- template family
- angle library
- proof library
- CTA library
- validated slot values

Each slot has:

- source field
- validation rule
- fallback value
- staleness threshold

### 10.5 Asset Inventory System

Purpose: maintain a structured library of:

- outbound templates
- landing pages
- comparison pages
- calculators
- demo pages
- FAQ assets
- intro-call CTAs
- pilot offers

Every asset carries target trade, pain angle, stage, proof type, status, version, and amortized cost.

### 10.6 Page Router

Purpose: choose where the prospect goes next.

Possible destinations:

- homepage
- wedge page
- comparison page
- calculator
- demo page
- use-case page
- direct intro-call page

### 10.7 Proof Selector

Purpose: choose evidence that creates belief for the specific objection and stage.

Proof assets include:

- demo calls
- workflow walkthroughs
- comparison tables
- calculators
- FAQs
- pilot summaries
- jobs-booked or calls-answered stats
- win stories

### 10.8 Experiment Allocator

Purpose: own experiment creation, allocation, winner declaration, and retirement.

Experiments are combinations of:

- channel
- segment
- lifecycle stage
- angle
- template
- destination page
- proof asset

Allocation method: **cost-weighted Thompson sampling**.

Winner declaration uses a three-gate protocol:

1. minimum sample per arm
2. statistical significance
3. temporal stability

Feedback horizons are tiered:

- Tier 1 fast signals for exploration
- Tier 2 medium signals for confident allocation
- Tier 3 slow signals for winner authority

Pricing experiments are supported but founder-gated.

### 10.9 Sales Insight Layer

Purpose: turn sales calls, transcripts, and notes into structured objections, blockers, competitor mentions, and talk-track improvements.

Outputs feed:

- objection taxonomy
- FAQ candidates
- page recommendations
- competitor battlecards

### 10.10 Product-to-Growth Bridge

Purpose: feed real CallLock product behavior back into GTM learning.

Signals include:

- calls answered
- calls missed
- booking completion rate
- after-hours performance
- trade-specific booking performance
- caller satisfaction proxies

This is how the growth system learns from actual product outcomes rather than only top-of-funnel proxies.

### 10.11 Signal Quality Layer

Purpose: score every event before it influences Growth Memory.

Canonical thresholds:

- full weight: above 0.7
- reduced weight and review flag: 0.3 to 0.7
- quarantine: below 0.3

Phase 1-2 scoring stays rule-based in the write path for latency and auditability.

### 10.12 Learning Integrity Monitor

Purpose: answer three questions continuously:

1. is data flowing?
2. is data connecting?
3. is data trustworthy?

It also tracks component error budgets and DLQ depth.

### 10.13 Outbound Health Gate

Purpose: mandatory compliance and reputation checkpoint between routing and send.

Hard invariant: **fail closed**.

Checks include:

- suppress list
- bounce and complaint rate thresholds
- volume caps
- duplicate-send windows
- required compliance fields
- domain reputation
- idempotency
- lifecycle eligibility

### 10.14 Growth Advisor

Purpose: synthesize all Growth Memory into founder-actionable recommendations.

Outputs include:

- weekly digest
- asset-gap alerts
- angle decay warnings
- experiment proposals
- wedge readiness signals
- competitor pulse
- cost-efficiency alerts
- strategic briefings

### 10.15 Founder Review UI and delegation

Every recommendation has three actions:

- Approve
- Override
- Defer

Delegation tiers:

- Tier 1 founder only: pricing, wedge expansion, kill criteria, legal and strategy overrides
- Tier 2 trusted delegate: asset approvals, experiment tuning, template approval within doctrine scope
- Tier 3 system autonomous: bounded allocation, winner declaration, re-segmentation, signal scoring, dead-zone detection

Overrides are training signal. Doctrine constrains what can be proposed before it reaches review.

`review_object` is the durable workflow primitive behind this surface.

Canonical uniqueness key:

- `tenant_scope`
- `review_type`
- `subject_type`
- `subject_id`
- `subject_version`

Lifecycle states:

- `proposed`
- `blocked_pending_doctrine`
- `approved`
- `deferred`
- `superseded`
- `applying`
- `applied`
- `failed_apply`
- `cancelled`

Apply rules:

- only one active `review_object` may exist for the uniqueness key at a time
- new competing proposals must supersede or dedupe atomically
- apply requires compare-and-set against the current `subject_version`
- every apply carries an idempotency token so double-submit or retry does not double-apply
- downstream side-effect failure moves the object to `failed_apply` and preserves retry or replay context

### 10.15A Control-plane authorization matrix

Delegation tiers describe product posture. `control_plane_auth` is the authorization contract that constrains the implementation.

| Role | Allowed actions | Tenant scope | Reason required | Audit required | Failure posture |
|---|---|---|---|---|---|
| Founder | approve, override, replay, benchmark-read, emergency freeze | all tenants | yes for override, replay, and cross-tenant reads | always | fail closed |
| Trusted delegate | asset approval, experiment tuning, packet triage, benchmark-read | assigned tenants only | yes for override-like actions | always | fail closed |
| System autonomous | bounded allocation, winner declaration, re-segmentation, projection refresh | scoped tenant only | machine reason code required | always | fail closed |
| Auditor / ops | read audit, review failures, replay diagnostics | approved support scope only | yes | always | fail closed |

Authorization checks must bind actor, action, tenant scope, reason, and current subject version before state changes or replay begin.

### 10.16 Founder Dashboard

The dashboard has four levels:

- Level 1: Is it working?
- Level 2: What is winning?
- Level 3: What should I do?
- Level 4: What happened?

Key surfaces include:

- system narrative
- momentum score
- learning score
- objection heat map
- empathy maps
- prove-it reasoning chains
- growth memory changelog
- experiment graveyard

### 10.17 Touchpoint Log and attribution

`touchpoint_log` is the immutable source of truth for:

- sends
- replies
- clicks
- page views
- demo plays
- meetings
- call completions
- referrals

Attribution is derived as computed views:

- last-touch
- first-touch
- positional

Signed attribution tokens protect against parameter tampering.

### 10.18 Routing Decision Log

Every routing decision records:

- inputs
- scores
- seasonal context
- selected assets
- fallback use
- gate results

This enables full explainability and the "Prove It" feature.

### 10.19 Cost and unit economics layer

Track:

- enrichment cost
- asset creation cost
- send cost
- human review cost
- cost per meeting
- cost per pilot
- budget allocation

Optimization target is value per dollar, not raw conversion rate.

## 11. Journeys, Lifecycle, and Prospect Intelligence

### 11.1 Prospect Lifecycle State Machine

Canonical path:

- UNKNOWN
- REACHED
- ENGAGED
- EVALUATING
- IN PIPELINE
- PILOT STARTED
- CUSTOMER

Extended states:

- DORMANT
- LOST
- NO-SHOW
- EXPANDING
- AT_RISK
- CHURNED
- ADVOCATE

Lifecycle state gates experiment eligibility and gives the system a concept of stalled prospects.

### 11.2 Journey Orchestrator

Purpose: move from single-touch optimization to narrative-arc optimization.

Journeys sequence:

- pain recognition
- proof
- social proof
- urgency

Adaptive rules let the system insert comparison, calculator, battlecard, or counter-proof steps based on responses and objections.

### 11.3 Prospect Scoring Model

Prospects are scored at enrichment time for resource prioritization.

Signals include:

- segment conversion rate
- enrichment confidence
- lookalike match
- intent strength
- geographic market density
- seasonal alignment

The score determines enrichment depth, experiment priority, and cadence.

### 11.4 Intent Signal Detector

Detect prospect timing signals such as:

- hiring
- review-volume surges
- website expansion changes
- being in peak seasonal demand

These signals boost scoring and help pick urgency-appropriate journeys.

## 12. Advanced Intelligence Modules

These modules remain in the main body because they define the system shape, even when implemented later.

### 12.1 Combination Discovery Engine

Weekly batch analysis that finds promising combinations never explicitly tested as experiments.

### 12.2 Content Intelligence Engine

Transforms outbound learning into inbound and organic content strategy.

### 12.3 LLM Output Regression Monitor

Uses a golden set to detect silent drift in selector quality and can fall back to rule-based selection.

### 12.4 Shadow Mode

Bridges human-approved routing to autonomous routing by logging what the system would have done in parallel.

### 12.5 Wedge Discovery Engine

Detects emergent trades from unclassified prospects, inbound demand, cross-sell, and adjacent data.

### 12.6 Causal Hypothesis Engine

Generates and tests hypotheses about why winning combinations work, so learning can transfer across wedges.

### 12.7 Channel Mix Optimizer

Optimizes portfolio allocation across cold email, paid, inbound, referral, and product-led loops.

### 12.8 Geographic Intelligence Layer

Adds market density, weather-demand correlation, competitive proximity, and geographic arbitrage signals.

### 12.9 Decision Audit Engine

Audits the system's own decision patterns for drift, exploration collapse, blind spots, and local optima.

### 12.10 Loss Analysis Engine

Turns loss and churn reasons into pricing, positioning, proof, and qualification improvements.

### 12.11 Growth Simulator

Runs Monte Carlo style scenario analysis for wedge launches, pricing moves, and budget shifts.

### 12.12 Adversarial Resilience

Detects gaming, list poisoning, and behavior patterns that can corrupt learning.

### 12.13 Referral Mechanism

Activates ADVOCATE customers through signed referral links and attribution-aware referral loops.

## 13. Belief, Doctrine, Proof, and Wedge Fitness

### 13.1 Conviction and Readiness Layer

The system should learn not just what converted, but what created conviction and whether the buyer was ready to act.

Canonical derived signals:

- `conviction_shift`: did the evidence increase or decrease belief that CallLock solves the buyer's problem?
- `buying_readiness`: did the evidence increase or decrease willingness to take the next commercial step now?

These are derived over observable behavior. They are not raw truth claims about human psychology.

Illustrative signal map:

- email open without click -> conviction `flat`, readiness `flat`
- demo watched deeply -> conviction `up`, readiness `flat` or `up`
- comparison page dwell -> conviction `up`, readiness `flat`
- objection reply -> conviction `down`, readiness `flat`
- meeting booked -> conviction `up`, readiness `up`
- pilot cancelled -> conviction `down`, readiness `down`

Compatibility rule: legacy `belief_events` remain a derived compatibility view for older plans, but canonical writes and analytics use `conviction_shift` and `buying_readiness`.

### 13.2 Founder Doctrine Registry

Doctrine codifies founder strategy and operating rules before the system makes decisions.

Doctrine strengths:

- hard: cannot be violated
- soft: can be challenged by evidence, but only through explicit review

Doctrine precedence:

- hard doctrine beats experiment data
- hard doctrine beats delegate approval
- soft doctrine creates friction, not walls
- evidence can trigger doctrine review but cannot silently override it

### 13.3 Proof coverage

Proof coverage is tracked per segment x objection x lifecycle stage:

- `gap`: no proof asset exists
- `weak`: proof exists but does not shift belief enough
- `covered`: proof exists and shifts belief convincingly

This prevents the system from treating mere asset existence as proof readiness.

### 13.4 Anti-pattern registry

Known-bad combinations are recorded and suppressed from future experiment generation until review criteria are met.

### 13.5 Wedge Fitness Score

Composite score measuring whether a wedge is mature enough for more automation or expansion.

Components:

- booked pilot rate
- attribution completeness
- proof coverage
- founder alignment
- learning velocity
- retention quality
- segment clarity
- cost efficiency
- conviction depth
- readiness progression

### 13.6 Hard kill criteria

Certain conditions pause operation regardless of wedge fitness:

- sender reputation collapse
- attribution collapse
- zero pilots after large enough sample in early phases
- repeated critical integrity alerts

## 14. Phase Plan

### Phase 0 - Foundation and Instrumentation

Define schemas, event catalog, attribution, template system, quality rules, lifecycle, doctrine, belief map, proof coverage, and wedge fitness.

### Phase 1 - Manual Wedge Proof

Prove HVAC with one channel, founder-reviewed templates, and Growth Memory foundations in place.

### Phase 2 - Assisted Routing and Asset Selection

System recommends routing, proof, and experiments while humans still own strategic decisions.

### Phase 3 - Closed-Loop GTM Optimization

Automate bounded routing and experiment lifecycle with doctrine, quality, and health gates in place.

### Phase 4 - Product Feedback Integration

Make product outcomes directly shape proof, messaging, and page creation.

### Phase 5 - Wedge Replication Engine

Clone the winning system into adjacent wedges through configuration rather than bespoke rebuilds.

### Phase 6 - Growth Intelligence Platform

Use Growth Memory for product roadmap, pricing, and market expansion intelligence.

### Phase 7 - Network Effects and Aggregate Intelligence

Turn aggregate-safe cross-tenant learning into a privacy-governed moat.

## 15. Rollout and Trust Model

The trust ladder still exists, but it is now part of the broader growth-system authority rather than the whole definition of the doc:

- manual proof
- advisory-only
- assisted routing
- closed-loop bounded automation
- wedge replication
- aggregate intelligence

Each phase requires:

- observability
- rollback posture
- doctrine compliance
- safety gates
- explicit acceptance criteria

### 15.1 Day-1 observability pack

Every implementation-blocking contract must ship with:

- structured logs for entry, branch, and exit on write, apply, and refresh paths
- counters: ingest accepted/quarantined/duplicate, mutation applied/held/conflict, replay mismatch, review apply success/stale/failed, doctrine blocked-action count, benchmark suppression count
- gauges: projection stale age, projection skew duration, DLQ depth
- dashboards: trust ladder readiness, event-spine health, projection freshness/skew, review queue/apply failures, benchmark suppression
- runbooks: append failure backlog, mutation hold explosion, stale projection recovery, failed review apply replay, doctrine outage, benchmark suppression investigation

### 15.2 Data-plane rollback drill

Before assisted or closed-loop modes ship, the team must rehearse:

1. freezing closed-loop actions
2. freezing derived-state promotion while event capture stays live
3. serving last-good coherent projections
4. replaying from append-only evidence
5. restoring advisory, then assisted, then closed-loop behavior in order

## 16. Validation Strategy

The validation suite should cover at least the following families:

- full-loop simulation
- time-travel seasonal tests
- poisoning and tampering tests
- learning-correctness tests
- feedback-horizon tests
- quarantine and recovery tests
- journey coherence tests
- prospect scoring calibration tests
- causal isolation tests
- adversarial resilience tests
- belief shift tests
- proof coverage tests
- doctrine conflict tests
- anti-pattern suppression tests
- wedge-fitness gate tests

These are not optional polish. They are what keeps the growth system from learning the wrong lesson at scale.

### 16.1 Stage-gated contract matrix

| Contract | Earliest gate | Required coverage |
|---|---|---|
| event ingest, quarantine, duplicate and late handling | Stage 2 | unit + integration + chaos replay |
| deterministic write planning and lineage | Stage 2 | integration + replay determinism |
| shared projection snapshot lineage and skew fallback | Stage 2 | integration + system coherence |
| `review_object` uniqueness, stale apply, failed apply | Stage 3 | integration + system double-submit |
| `control_plane_auth` | Stage 3 | unit + integration + audit-path coverage |
| doctrine fail-closed behavior | Stage 3 | integration + outage scenario |
| dual-axis conviction and readiness semantics | Stage 2 | unit + integration against routing and proof logic |
| federated benchmark suppression | Stage 6 prerequisites locked in Stage 0 | integration + privacy threshold tests |
| data-plane rollback drill | Stage 4 | operational drill + replay recovery verification |

Promotion rule: no stage advances unless its required coverage is green and its rollback and observability expectations are demonstrated.

## 17. Immediate Priorities

The immediate repo priority is not "invent more vision." It is to keep the ambitious vision and surrounding execution artifacts aligned.

Near-term spec and implementation focus:

- finalize the HVAC wedge configuration
- define the event catalog and Growth Memory subset for Phase 1
- define touchpoint and routing decision logs
- define doctrine enforcement semantics in implementation-ready form
- keep the implementation-blocking contract set explicit and separate from later-stage directional modules
- preserve dual-axis conviction and readiness semantics across schemas and analytics
- define proof coverage computation and ownership loop
- define confidence rules for conviction and readiness signals
- define wedge fitness computation and phase-gate thresholds
- keep master plan, phase plans, and TODOs synchronized with this authority model

## 18. Assumptions and Defaults

- HVAC remains the first wedge.
- Cold email remains the first channel.
- Founder remains the only Tier 1 approver in early phases.
- Shared platform constraints remain owned by the architecture spec.
- Sequencing remains owned by the master plan.
- Legacy persuasion-platform terms remain compatibility labels only.

## Appendix A: Initial Asset Inventory

Phase 1 page inventory:

- `/`
- `/hvac/`
- `/hvac/ai-receptionist`
- `/hvac/missed-call-booking-system`
- `/compare/hvac-answering-service-vs-ai-receptionist`
- `/tools/missed-call-revenue-calculator`
- `/demo/hvac-booking-call`
- `/use-cases/when-your-team-is-on-jobs-all-day`

Initial proof assets:

- HVAC demo call
- workflow visual
- calculator
- FAQ pack
- voicemail comparison asset

Initial outbound template families:

- missed calls
- after-hours
- interruption
- better-than-voicemail

## Appendix B: Repo Realignment Notes

This restore intentionally changes the meaning of [design-doc.md](/Users/rashidbaset/Documents/calllock-agenticos/knowledge/growth-system/design-doc.md):

- before: narrowed persuasion-platform contract spec
- now: ambitious growth-system authority

Adjacent docs should describe it accordingly. When they still reference narrower legacy terms, they should explicitly rely on the compatibility bridge in Section 4 rather than restating the old authority model.
