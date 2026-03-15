# TODOS

Items identified during architecture reviews (2026-03-12).
Updated 2026-03-13: closed resolved items, narrowed remaining scope.
Updated 2026-03-14: added growth system expansion review items.
Updated 2026-03-14: added CEO mega-review expansion items (21 architectural decisions).
Updated 2026-03-14: added v3 depth pass deferred items (anti-pattern lifecycle, 5-core narrative, wedge fitness calibration, belief signal review).
Updated 2026-03-14: resolved 3 of 6 Droid-handoff blockers (runtime placement, idempotency/DLQ, Growth Memory migrations).
Updated 2026-03-14: resolved remaining 3 Droid-handoff blockers (attribution token lifecycle, regression test contract, Wedge Fitness computation). All 6 blockers now have ADRs.

## Active

### P1 — Extract HVAC logic from V2 backend into industry pack format
**What:** The existing V2 backend has hardcoded HVAC logic (117 smart tags, emergency tiers, service taxonomy, urgency rules). This needs to be extracted into the spec's industry pack format.
**Why:** This is the bridge from current state to target architecture for the industry pack layer. Without it, the industry pack concept remains theoretical.
**Effort:** L
**Depends on:** Section 0 (Current State) being finalized, Industry Pack format being stable.
**Source:** CEO review, Section 1A (Bridge Gap).

### P2 — Define external service resilience patterns (narrowed)
**What:** Define fallback behavior when Retell AI, Cal.com, or Twilio are unavailable.
**Why:** All three are production SPOFs with no fallback story. Supabase resilience is covered by the harness write-failure handling already implemented.
**Scope:** Deferred until Retell/Cal.com/Twilio integration clients exist in this repo. Define resilience patterns alongside the integration code, not speculatively.
**Effort:** M
**Source:** CEO review, Section 1F (Single Points of Failure).

### P3 — Tune Cockpit alerting thresholds from production baselines
**What:** Define specific threshold values for the four alert types (policy gate block rate, worker metric degradation, job failure spikes, external service errors) using observed baselines from the metrics API.
**Why:** Thresholds need baseline data from actual deployment, not guesses.
**Prerequisite:** Metrics API deployed and collecting data from production traffic.
**Effort:** S
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
