# TODOS

Stage 0 contract-lock and follow-through items after the authority restore (2026-03-14).

Items marked `Status: Contract locked in docs` now have an implementation-safe spec shape in the authoritative docs. They remain here until code, tests, and operational rollout satisfy that contract.

## P1 — Stage 0 Contract Lock Before Stage 2-4

### Extract HVAC logic from V2 backend into industry pack format
**What:** The existing V2 backend has hardcoded HVAC logic (117 smart tags, emergency tiers, service taxonomy, urgency rules). This needs to be extracted into the spec's industry pack format.
**Why:** This is the bridge from current state to target architecture for the industry pack layer. Without it, the industry pack concept remains theoretical.
**Effort:** L
**Depends on:** Section 0 (Current State) being finalized, Industry Pack format being stable.
**Source:** CEO review, Section 1A (Bridge Gap).

### Implement canonical growth-path reporting view and legacy persuasion_path compatibility
**What:** Define the canonical growth-path reporting lens `channel x segment x message x page x proof x CTA x sales outcome x product outcome`, plus the legacy `persuasion_path` compatibility view derived from touchpoints, routing decisions, belief events, and attribution.
**Why:** The main growth doc is ambitious again, but implementation artifacts still need one atomic reporting unit and one explicit backward-compatible mapping for older terminology.
**Effort:** M
**Depends on:** Growth system authority restore being stable, especially Growth Memory, attribution, and compatibility-bridge sections.
**Source:** Ambitious authority restore, 2026-03-14.

### Define proof supply chain and owner loop
**What:** Specify the operational loop from objection seen to proof brief creation, owner assignment, approval, deployment, and conviction re-measurement.
**Why:** Proof gaps are only useful if they produce owned work and measurable proof quality improvement.
**Effort:** M
**Depends on:** Proof coverage schema and Founder Weekly Operating Packet format being stable.
**Source:** CEO mega-review v2, missing proof supply chain loop.

### ~~Assign runtime ownership for growth-system components~~
**Resolved by:** ADR 010 (`docs/decisions/010-growth-system-runtime-placement.md`). All growth system code in `harness/src/growth/` as Python, Inngest functions as thin TypeScript handlers. Sales Machine Operating Manual spec aligns explicitly.

### Define attribution-token lifecycle and tenant-bound validation
**What:** Specify the token payload, expiry window, tenant binding, validation steps, replay posture, and key-rotation strategy for signed attribution tokens and referral links.
**Why:** The current docs say tokens are signed, but they do not yet lock the expiry duration, tenant-scope check, or dual-key rotation window. That leaves cross-tenant replay and secret-rotation behavior underspecified.
**Effort:** M
**Depends on:** touchpoint and attribution semantics remaining stable.
**Source:** 2026-03-14 HOLD SCOPE audit follow-up.

### Define deterministic Growth Memory write and lineage contracts
**Status:** Contract locked in docs on 2026-03-14 across `knowledge/growth-system/design-doc.md`, `plans/whole-system-executable-master-plan.md`, and `plans/phases-1-2-foundation-and-core-harness.md`. Implementation and tests still need to follow the named write categories, shared lineage fields, replay invariants, and projection-only read posture.
**What:** Specify the stable write categories, idempotency keys, single-writer rules, merge precedence, replay invariants, and lineage linkage rules from source event through downstream effect. Keep explicit mapping back to the legacy `graph_mutation` and `lineage_chain` labels where those still appear.
**Why:** Without deterministic writes and lineage contracts, the event spine cannot support replayable growth memory or trustworthy operator investigation.
**Effort:** M
**Depends on:** Growth-path reporting semantics and event-spine ingest contracts being stable.
**Source:** HOLD SCOPE review, Sections 1-2, plus authority restore translation work.

### Define review_object lifecycle and apply semantics
**Status:** Contract locked in docs on 2026-03-14. The authoritative docs now define the uniqueness key, lifecycle states, compare-and-set apply rule, idempotency token requirement, and `failed_apply` posture. Code and tests still need to implement those semantics.
**What:** Specify legal `review_object` transitions, terminal states, duplicate/supersede rules, stale snapshot handling, and the apply contract when downstream effects partially fail.
**Why:** The founder/operator control plane depends on `review_object` being a durable workflow object, not just an audit event or UI state.
**Effort:** M
**Depends on:** Proof supply chain framing and operator control-plane boundaries being stable.
**Source:** HOLD SCOPE review, Sections 1-6.

### Define projection versioning and stale-read behavior
**Status:** Contract locked in docs on 2026-03-14. Operator and decisioning reads now share a canonical snapshot-lineage, freshness, skew, and fallback contract. Runtime materialization and tests still need to enforce it.
**What:** Specify how decision and operator views version against Growth Memory state, what counts as stale, how skew is detected, and what users see when refresh fails. Preserve explicit mapping back to legacy `decisioning_projections` and `operator_projections`.
**Why:** Advisory-only and assisted modes are unsafe if digest, queue, and runtime reads can silently diverge.
**Effort:** M
**Depends on:** deterministic write contracts and operator surface requirements being stable.
**Source:** HOLD SCOPE review, Sections 2, 4, 6, and 9.

### Split belief into conviction_shift and buying_readiness
**Status:** Contract locked in docs on 2026-03-14. `belief_events` is now a compatibility view; canonical semantics are dual-axis. Schema, routing, proof, and analytics code still need to adopt the new vocabulary.
**What:** Replace single-axis belief modeling with dual-axis conviction and readiness semantics across schemas, routing logic, and proof analysis.
**Why:** A single belief axis hides the difference between "I believe it" and "I am ready to act," which weakens proof analysis and journey adaptation.
**Effort:** S
**Depends on:** dual-axis conviction/readiness framing and schema updates being stable.
**Source:** CEO mega-review v2, critical gap on belief precision.

### Keep the ambitious growth-system authority synchronized across execution artifacts
**Status:** Partially resolved in docs on 2026-03-14. The growth authority, architecture spec, master plan, and Phases 1-2 plan are aligned again; future contract changes still need a consistency pass.
**What:** Ensure the master plan, phase plans, architecture cross-references, and implementation notes continue to describe the restored ambitious growth authority rather than drifting back to the narrowed persuasion-graph framing.
**Why:** The current risk is spec drift, not lack of vision. A split between ambitious authority and narrow execution docs will recreate ambiguity quickly.
**Effort:** S
**Depends on:** authority split and compatibility bridge remaining stable.
**Source:** Ambitious authority restore, 2026-03-14.

### Adopt 4-plane architecture framing
**Status:** Resolved in docs on 2026-03-14. The growth authority now frames the system through four layers and the remaining work is to keep downstream implementation language consistent with that framing.
**What:** Frame the growth system as four planes: Capture, Interpret, Decide, and Govern. This supersedes the older five-core narrative concept.
**Why:** The 4-plane model keeps the system legible and ties every component back to the repeatable persuasion path loop.
**Effort:** S
**Depends on:** Core growth system vocabulary and phase framing being stable.
**Source:** CEO mega-review v2, fundamental reframing.

### Implement founder review workflow data model from the compatibility bridge
**Status:** Partially resolved in docs on 2026-03-14. The doc now defines the canonical `review_object` contract; implementation still needs storage shape, transactional boundaries, and cross-surface projection behavior.
**What:** Define the durable workflow object and state transitions that bridge the legacy `review_object` term to the restored Founder Review UI, doctrine conflicts, recommendation approvals, overrides, and asset approval flows.
**Why:** The documentation now maps the old review-object term to a broader founder-review workflow, but implementation cannot rely on prose-only translation.
**Effort:** M
**Depends on:** doctrine registry semantics and operator surface requirements being stable.
**Source:** Ambitious authority restore, 2026-03-14.

### Define compliance graph conflict resolution rule
**Status:** Resolved in code and ADR 009. Compliance rules now resolve by explicit conflict grouping (`metadata.conflict_key` / `metadata.disclosure_key` / `target`), mixed-effect matches always escalate, pure restrictions follow `deny > escalate > allow`, and tool execution remains deny-by-default when no explicit allow matches.
**What:** Define what happens when the compliance graph returns contradictory rules (e.g., one rule requires a disclosure, another forbids it for the same context). Resolution principle (most-restrictive-wins) is now in Section 5; this TODO covers the full rule set.
**Why:** Without a conflict resolution strategy, the policy gate could silently apply the wrong rule or block everything. Promoted from P2: the policy gate depends on this to function correctly.
**Implementation consideration:** Cross-graph queries ("which compliance rules contradict each other?") require scanning all compliance graph nodes. With markdown/YAML files this is a full-text scan — consider whether the compliance graph specifically should be database-backed (Supabase table with typed relationships) rather than file-based, to enable indexed conflict detection. The rest of the Knowledge Substrate can remain file-based; compliance rules are the highest-stakes query surface.
**Effort:** S
**Depends on:** Policy Gate detail (Section 5) being finalized.
**Source:** CEO review, Section 2 (Error & Rescue Map). Promoted by eng review.

### Define control_plane_auth role matrix
**Status:** Contract locked in docs on 2026-03-14. The authoritative docs now define roles, actions, tenant scope, reason requirements, audit expectations, and fail-closed posture. Enforcement code and permission tests still need to land.
**What:** Specify the internal roles, permitted actions, reason requirements, and audit expectations for cross-tenant reads, writes, overrides, replay, and benchmark access.
**Why:** Audit logging exists, but audit is not authorization. The control plane is unsafe until its access model is explicit and testable.
**Effort:** M
**Depends on:** Cockpit surface boundaries and tenant-isolation rules remaining stable.
**Source:** HOLD SCOPE review, Sections 1 and 3.

### Define federated benchmark privacy thresholds
**Status:** Contract locked in docs on 2026-03-14. The authoritative docs now define minimum cohort size, slice-width guardrails, dominance suppression, and lineage requirements. Aggregation jobs and privacy tests still need to implement that contract.
**What:** Specify minimum cohort sizes, allowed slice dimensions, suppression behavior, and lineage requirements for aggregate-only benchmark outputs.
**Why:** The growth spec keeps benchmarks aggregate-only, but without concrete privacy thresholds later phases could leak tenant-identifying patterns.
**Effort:** S
**Depends on:** Data classification rules and `federated_benchmark` semantics being stable.
**Source:** HOLD SCOPE review, Sections 3, 6, and 10.

### Define event-specific idempotency formulas and DLQ backing store
**What:** For each canonical ingest and derived-write path, name the exact idempotency key formula and the durable dead-letter queue storage location, retention, and replay path.
**Why:** The docs require idempotency and DLQ depth, but they do not yet pin event-level key construction or where unrecoverable events live. That leaves duplicate-delivery behavior and observability implementation ambiguous.
**Effort:** M
**Depends on:** deterministic write contracts and event catalog remaining stable.
**Source:** 2026-03-14 HOLD SCOPE audit follow-up.

### Implement canonical error and rescue taxonomy across runtime boundaries
**What:** Carry the canonical Stage 0 exception vocabulary into event ingest, deterministic apply, projection refresh, founder review apply, control-plane auth, doctrine evaluation, and benchmark publish flows, including logs, counters, and test cases for each named failure.
**Why:** The docs now name the failure contract. If runtime code invents different names or swallows these paths, the contract lock fails and silent errors return.
**Effort:** M
**Depends on:** deterministic write contracts, `review_object` contract, projection coherence contract, and alerting surfaces.
**Source:** Hold Scope follow-up implementation pass, 2026-03-14.

### Implement the Stage 0 observability pack and data-plane rollback drill
**What:** Ship the required counters, gauges, dashboards, alerts, runbooks, and freeze/replay drill for ingest, mutation, projection, review apply, doctrine outage, and benchmark suppression paths.
**Why:** The docs now define observability and rollback as scope. Until the runtime and operating workflow implement them, advisory and assisted rollout remain under-defended.
**Effort:** M
**Depends on:** canonical error taxonomy, projection freshness contract, and control-plane operations.
**Source:** Hold Scope follow-up implementation pass, 2026-03-14.

### Define wedge fitness computation and phase-gate thresholds
**What:** Turn the named Wedge Fitness components into a canonical formula with weights, normalization rules, minimum sample sizes, and the exact thresholds that gate advisory, assisted, and closed-loop promotion.
**Why:** The docs list the score inputs and mention thresholded phase decisions, but they still stop short of a computation that can be implemented or tested consistently.
**Effort:** M
**Depends on:** proof coverage, attribution completeness, retention quality, and conviction/readiness semantics remaining stable.
**Source:** 2026-03-14 HOLD SCOPE audit follow-up.

### Implement the Phase 1 Growth Memory schema and migration set
**What:** Write the initial Supabase migrations for the Phase 1 Growth Memory subset, including canonical tables, compatibility views, indexes, and any required partitioning or projection scaffolding.
**Why:** The authority doc names the table families, but the repo migration set still stops at harness-era foundations. Phase 1 growth work cannot start until the storage contract exists in SQL.
**Effort:** L
**Depends on:** event catalog, deterministic write contract, and attribution semantics being stable.
**Source:** 2026-03-14 HOLD SCOPE audit follow-up.

### Add fail-closed and duplicate-delivery regression coverage
**What:** Add explicit tests for Outbound Health Gate fail-closed behavior, duplicate event delivery, exactly-once derived writes, and replay after partial failure.
**Why:** The validation strategy names stage-gated coverage families, but the repo still lacks concrete regression tests for the highest-risk safety and data-integrity invariants.
**Effort:** M
**Depends on:** error taxonomy, idempotency formulas, and Growth Memory write paths being implemented.
**Source:** 2026-03-14 HOLD SCOPE audit follow-up.

### Send queue priority ordering and ramp-up schedule
**What:** Define a send_queue table, priority ordering logic (T1 new prospects > later touches from older sequences > re-engagement), and ramp-up schedule (Week 1=50 prospects/batch, Week 2=100, Week 3=150, Week 4=200). Deferred sends shift by 1 day, not skipped.
**Why:** Without a send queue, Day 3 exceeds mailbox capacity when T1s from new batches collide with T2s from prior batches. At 200 prospects/day with 180-300 daily send capacity, overflow is mathematically guaranteed by week 2.
**Effort:** S
**Priority:** P1
**Depends on:** Sender Agent spec (Section 2.5.5), deployment sequence (Section 10.1).
**Source:** Sales Machine spec second-pass CEO review, Issue 9.

### Enrichment Agent staleness heuristic and Google Places API integration
**What:** Add staleness detection to the Enrichment Agent (check Google listing status, flag stale data, skip closed businesses). Switch to Google Places API as primary data source for Google listing data. Add concurrency (10 parallel enrichments) and per-prospect timeout (15 seconds).
**Why:** Sending cold emails to closed businesses wastes sends and hurts deliverability. Sequential enrichment of 200 prospects takes 10-33 minutes (risks Inngest function timeout). Google Places API is more reliable than scraping.
**Effort:** M
**Priority:** P1
**Depends on:** Enrichment Agent spec (Section 2.5.2), Google Places API key provisioned.
**Source:** Sales Machine spec second-pass CEO review, Issues 5 and 12.

## P2 — Post-Contract-Lock Extensions

### Add founder weekly operating packet spec
**What:** Define a 15-minute weekly founder packet with four sections: What Changed, What to Approve, What to Kill, and What Proof to Build Next.
**Why:** The system needs a bounded operating ritual, not just dashboards and digests.
**Effort:** S
**Depends on:** growth-path reporting view and proof supply chain being defined.
**Source:** CEO mega-review v2, operator-surface recommendation.

### Define external service resilience patterns
**Status:** Partially resolved in code and ADR 002 for Supabase, Inngest, and LangSmith. Remaining work is Retell AI, Cal.com, and Twilio once those integrations exist in this repo.
**What:** Define fallback behavior when Retell AI, Supabase, Cal.com, or Twilio are unavailable.
**Why:** All four are production SPOFs with no fallback story in the spec.
**Effort:** M
**Depends on:** Section 0 (Current State) establishing which services are critical.
**Source:** CEO review, Section 1F (Single Points of Failure).

### Define Inngest event validation schema
**Status:** Resolved in code and ADR 004 for `harness/process-call` and `harness/job-complete`.
**What:** Define the event schema for harness trigger events emitted by Express V2 after processing Retell webhooks. Include required fields (call_id, tenant_id, call metadata), validation rules, and rejection behavior for malformed events.
**Why:** Without event validation, malformed or unauthorized events could trigger unintended worker execution. This is also a security vector (unauthorized event injection into the Inngest event bus).
**Effort:** S
**Depends on:** Harness trigger mechanism (Section 5) being implemented, Express V2 webhook handler structure.
**Source:** CEO review #2, Section 3 (Security & Threat Model).

### Define harness → Supabase write failure handling
**Status:** Resolved in code and ADR 002 with retry + local recovery journal fallback.
**What:** Define the specific mechanism for handling Supabase write failures during harness operations: transaction boundaries, retry policy, cleanup on partial failure.
**Why:** Error Philosophy rule #4 says "partial state is the enemy" but there's no specific mechanism for the harness → Supabase integration. A failed write mid-job could leave orphaned artifacts or incomplete tenant state.
**Effort:** S
**Depends on:** Return path definition (Section 5), Implementation Phasing (Section 24).
**Source:** Eng review, Failure Modes analysis.

### Define PII redaction implementation approach
**Status:** Resolved in code and ADR 003 with recursive regex redaction + identifier hashing.
**What:** Specify the PII redaction mechanism for LangSmith traces (regex-based, NER model, allowlist/denylist, or library like presidio).
**Why:** Section 5 says "redact or hash direct identifiers" but doesn't specify the approach. PII redaction is notoriously error-prone — regex misses edge cases, NER models add latency.
**Effort:** S
**Depends on:** Harness deployment decisions, LangSmith integration, data volume and latency budget.
**Source:** Eng review, Section 5 (Trace data classification).

## P3 — Nice to Have

### Define Express V2 horizontal scaling story
**What:** Document whether Express V2 on Render runs as single instance, auto-scaled, or behind a load balancer. Define the scaling trigger and expected behavior at 10x tenant count.
**Why:** At 10 tenants × 3 trades, Express V2 handles all webhooks and API requests. Current single-contractor load doesn't require scaling, but the spec positions Express V2 as the product core backend.
**Effort:** S
**Depends on:** Tenant count growth, Render deployment configuration.
**Source:** CEO review #2, Section 7 (Performance Review).

### Define Cockpit alerting thresholds and channels
**Status:** Partially resolved in code. Alert types now include scheduler stale claims and backlog age, thresholds can be overridden per tenant config, delivery supports dashboard, optional webhooks, email, SMS, and pager out of the box, stale alerts can auto-escalate by policy, duplicate sustained conditions are suppressed into a single active alert, recovered conditions can auto-resolve after cooldown, and grouped incidents are now queryable with episode history plus operator workflow, normalized classification, bound runbooks with structured step semantics (`required`, `depends_on`, `parallel_group`), completion and approval policy, per-step runbook progress, derived execution-plan guidance, step ownership/claiming with lease expiry, heartbeat, step-granular compare-and-set, DB-side atomic Supabase step mutation, DB-side atomic incident workflow mutation, DB-side atomic incident reminder/reassignment mutation, DB-side atomic alert-to-incident sync mutation, DB-side atomic alert-update-plus-incident-sync mutation, and DB-side atomic alert-create-plus-incident-sync mutation, weighted/capacity-aware assignment routing, availability-aware fallback, skill-aware routing, and reminders. Production threshold tuning still needs baseline traffic data.
**What:** Define specific threshold values for the four alert types (policy gate block rate, worker metric degradation, job failure spikes, external service errors) and tune the delivery mix for production operations.
**Why:** Sections 3 and 5 say the harness emits alerts to the Cockpit, but without thresholds, alerts are either too noisy or never fire. Thresholds need baseline data from initial deployment.
**Effort:** S
**Depends on:** Harness implementation, baseline metrics from initial deployment.
**Source:** Eng review, Section 3 (Alerting).

### P2 — Growth Memory Replay (Phase 2 vision)
**What:** Time-slider in Founder Dashboard showing how Growth Memory evolved over time. Founder can slide to any date and see what the system knew then.
**Why:** Makes "compounding learning" viscerally visible — founder watches the system get smarter. Builds trust and differentiates from static dashboards.
**Effort:** M
**Depends on:** Growth Memory changelog infrastructure (Phase 1).
**Source:** Growth system expansion review, Delight D1.

### P2 — Prospect Story Timeline (Phase 2 vision)
**What:** Visual timeline of every touch, routing decision, and outcome for a single prospect — from first enrichment to final outcome in one view.
**Why:** The "Prove It" feature applied to individual journeys. Aids debugging, deepens founder understanding, impressive in sales demos.
**Effort:** S
**Depends on:** Touchpoint log + routing decision log (Phase 1).
**Source:** Growth system expansion review, Delight T2.

### P2 — "Teach Me" Override Dialogue (Phase 2)
**What:** When founder overrides a recommendation, system optionally asks: "was the data wrong, the timing wrong, or the strategy wrong?" Stored as structured training signal.
**Why:** Transforms overrides from binary (approve/reject) into the richest learning signal in the system. Teaches strategic intent no experiment can discover.
**Effort:** S
**Depends on:** Founder Review UI (Phase 2).
**Source:** Growth system expansion review, Delight T4.

### P3 — Production Shadow Testing (Phase 3)
**What:** Run validation tests (Test 1-6) against anonymized production data periodically, not just synthetic data.
**Why:** Simulation tests prove theory; production shadow tests prove practice. Real data has messiness simulations miss.
**Effort:** M
**Depends on:** Phase 2 (enough production data to test against).
**Source:** Growth system expansion review, TODO T5.

### P2 — Cold Start Accelerator (Phase 5)
**What:** When launching a new wedge, borrow priors from similar wedges (e.g., plumbing borrows HVAC priors at 0.3 confidence) for faster Thompson sampling convergence.
**Why:** Without this, every new wedge starts from zero. With it, second wedge learns 3-5x faster. Directly accelerates Phase 5 wedge replication.
**Effort:** M
**Depends on:** Learning Velocity Tracker, wedge-as-config, at least one proven wedge.
**Source:** Growth system expansion review, Delight T3.

### P1 — Phase 6-7 Schema Readiness Validation
**What:** Validate Phase 0-1 schemas against Phase 6-7 requirements. Add `is_aggregate_safe` flags to Growth Memory column definitions, `pricing_mentioned` + `geographic_context` to competitor_mentions, and `product_usage_correlation` table to schema design.
**Why:** Phase 6-7 (Growth Intelligence Platform + Network Effects) is the 12-month endgame. Discovering schema gaps in month 9 is expensive. These fields cost nothing to add now.
**Effort:** S
**Depends on:** Phase 0 schema finalization.
**Source:** CEO mega-review, Issue 1 + Issue 8.

### P1 — Extended Lifecycle Post-Customer States
**What:** Implement post-CUSTOMER lifecycle states (EXPANDING, AT_RISK, CHURNED, ADVOCATE) in lifecycle state machine spec, with structured churn reason taxonomy and referral attribution.
**Why:** Closes the growth loop — post-sale signals are the highest-fidelity learning. CHURNED reasons feed Loss Analysis and pricing hypotheses. ADVOCATE state enables referral channel.
**Effort:** M
**Depends on:** Lifecycle State Machine spec (Phase 0).
**Source:** CEO mega-review, Issue 2.

### P2 — Journey Orchestrator Component
**What:** Implement Journey Orchestrator (component 7.24) — multi-touch sequence planning per segment × lifecycle, Thompson sampling over journey strategies, narrative coherence, adaptive rules.
**Why:** Journey-level experiments are higher-leverage than touch-level. A coherent narrative arc (pain → proof → urgency) converts differently than independent optimized touches.
**Effort:** L
**Depends on:** Touchpoint log, Lifecycle State Machine, Experiment Allocator.
**Source:** CEO mega-review, Issue 3.

### P2 — Growth Heartbeat (Phase 2 delight)
**What:** Daily 1-sentence push notification about what the system learned today.
**Why:** Creates a daily habit loop, costs almost nothing to build (Growth Advisor already synthesizes data), keeps founder connected to system intelligence.
**Effort:** S
**Depends on:** Growth Advisor v2 (Phase 2).
**Source:** CEO mega-review, Delight 1.

### P2 — Experiment Graveyard (Phase 2 delight)
**What:** Dedicated view showing retired/killed experiments with structured failure reasons and lessons learned.
**Why:** Prevents repeating failed experiments, surfaces "what doesn't work" patterns as organizational knowledge.
**Effort:** S
**Depends on:** experiment_history table (Phase 1).
**Source:** CEO mega-review, Delight 2.

### P2 — Founder Intuition Score (Phase 2 delight)
**What:** Track founder override accuracy over time — was the founder right when they disagreed with the system?
**Why:** Builds calibrated trust. Makes the Phase 2→3 autonomy transition data-driven. Shows where founder gut beats system and vice versa.
**Effort:** M
**Depends on:** Founder Review UI + outcome tracking on overrides.
**Source:** CEO mega-review, Delight 3.

### P2 — Insight Ancestry (Phase 2 delight)
**What:** Trace any recommendation through its full evidence chain: insight → experiments → touchpoints → prospects → outcomes.
**Why:** Transforms "trust the system" into "verify the system" — verification builds deeper trust than any dashboard metric.
**Effort:** S
**Depends on:** Routing decision log + touchpoint log (Phase 1).
**Source:** CEO mega-review, Delight 6.

### P3 — Growth Memory Time Machine (Phase 3 delight)
**What:** Counterfactual replay — "if we had known in Month 2 what we know in Month 6, how much faster would we have converged?" Quantifies ROI of the growth system itself.
**Why:** Makes the value of the learning system tangible and concrete.
**Effort:** M
**Depends on:** Growth Memory changelog + sufficient historical data.
**Source:** CEO mega-review, Delight 5.

### P2 — Anti-Pattern Lifecycle Management
**What:** Add context tags (seasonal, price-dependent, proof-dependent), re-evaluation triggers (context change fires review), and graduation criteria (3 re-test failures across different contexts → durable) to anti_pattern_registry.
**Why:** Anti-patterns aren't permanent truths. An angle that fails in March might work in July. Without lifecycle management, the anti-pattern registry becomes a graveyard of ideas that were bad once but might work now. Phase 1 captures anti-patterns; Phase 2 manages their lifecycle.
**Effort:** S
**Depends on:** Anti-pattern registry capturing ≥10 entries (enough to warrant lifecycle management).
**Source:** v3 depth pass, Bucket 3A.

### P2 — 5-Core Narrative Restructure
**What:** Reorganize design doc Table of Contents into 5-core framing: Acquisition Core, Belief Core, Learning Core, Control Core, Expansion Core. Group existing component sections under their core. Presentation layer change only — no architectural impact.
**Why:** The doc currently reads as 38 peer components. The 5-core framing makes a new engineer understand the system in 10 minutes instead of 2 hours. Deferred from v3 to avoid mixing substantive changes with presentation changes.
**Effort:** M
**Depends on:** v3 substantive changes landed and stable.
**Source:** v3 depth pass, Bucket 3B.

### P2 — Wedge Fitness Score Calibration
**What:** Tune Wedge Fitness component weights using Phase 1 baseline data. Add belief_depth weight refinement. Calibrate gate thresholds against actual Phase 1 outcomes.
**Why:** Initial weights are educated guesses. Calibration requires real data from Phase 1 to know which components are most predictive of actual wedge readiness.
**Effort:** S
**Depends on:** Phase 1 data (≥4 weeks of Wedge Fitness Score computation).
**Source:** v3 depth pass, Bucket 3C.

### P3 — Belief Signal Map Quarterly Review Process
**What:** Define formal review cadence and evolution process for the Belief Signal Map. Include: review triggers (new touchpoint types, calibration drift), update protocol, version migration for historical belief_events.
**Why:** The initial Belief Signal Map is a first approximation. The review process can be defined once the first map proves useful and drift patterns emerge.
**Effort:** S
**Depends on:** Belief Layer v1 deployed and producing data for ≥8 weeks.
**Source:** v3 depth pass, Bucket 3D.

### P3 — Achievement Toasts (Office Dashboard Phase 2)
**What:** Toast notifications on agent/department milestones (10th deal closed, 100th verification, zero-error week).
**Why:** Gamification for internal team morale. Makes the office feel alive and celebratory.
**Effort:** S
**Depends on:** Office Dashboard Phase 1 complete + sufficient event data to calibrate thresholds.
**Source:** CEO mega-review, Delight 4.

### P3 — Ambient Sound Design (Office Dashboard Phase 2)
**What:** Subtle audio layer tied to agent states — typing, murmurs, paper shuffling, alarm buzzer. Mutable. Volume scales with activity.
**Why:** Peripheral awareness for always-on desktop window. Unique differentiator.
**Effort:** M
**Depends on:** Office Dashboard Phase 1 complete + Electron desktop wrap.
**Source:** CEO mega-review, Delight 5.

### P2 — Deprecate MetricsEmitter after InngestEmitter stabilizes
**What:** After InngestEmitter has been stable for ≥2 sprints, migrate remaining metric_events consumers to Inngest events and remove MetricsEmitter. Unify into a single observation pipeline.
**Why:** Two parallel observation systems (MetricsEmitter → metric_events, InngestEmitter → Inngest → agent_office_state) will drift in schema, reliability guarantees, and maintenance burden. InngestEmitter is strictly more capable (Inngest retry, DLQ, fan-out).
**Effort:** M
**Depends on:** InngestEmitter stable in production for ≥2 sprints.
**Source:** Office Dashboard CEO review, Issue 1A.

### P3 — Backfill existing Inngest event names to calllock/ prefix
**What:** Rename existing event types from unprefixed names (ProcessCallPayload, JobDispatchPayload, etc.) to `calllock/` prefixed convention (calllock/call.process, calllock/job.dispatch, etc.). Update all Inngest function triggers accordingly.
**Why:** The `calllock/` prefix is now the standard per ADR. Existing events should follow the same convention to avoid a permanent naming split across the event catalog.
**Effort:** M (6 event types + all function triggers + tests)
**Depends on:** Event naming convention ADR.
**Source:** Office Dashboard CEO review, Issue 5.

## Closed

### ~~P3 — Define Express V2 horizontal scaling story~~
**Resolved by:** `docs/decisions/002-express-v2-scaling.md` (ADR 002)

### ~~P1 — Define compliance graph conflict resolution rule~~
**Resolved by:** `supabase/migrations/006_compliance_conflict_resolution.sql`

### ~~P2 — Define Inngest event validation schema~~
**Resolved by:** Inngest event schema implementation in `inngest/src/events/schemas.ts`

### ~~P2 — Define harness → Supabase write failure handling~~
**Resolved by:** Harness persistence node and repository error handling in `harness/src/harness/nodes/persist.py` and `harness/src/db/supabase_repository.py`

### ~~P2 — Define PII redaction implementation approach~~
**Resolved by:** Pattern-matching PII redactor in `harness/src/observability/pii_redactor.py` and verification node checks in `harness/src/harness/nodes/verification.py`
