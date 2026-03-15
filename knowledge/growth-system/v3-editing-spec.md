---
id: growth-system-v3-editing-spec
title: Growth System Design Doc v3 Editing Spec
graph: knowledge
owner: founder
last_reviewed: 2026-03-14
trust_level: authoritative
progressive_disclosure: full
---

# Growth System Design Doc v3 Editing Spec

## Summary

Revise the design doc to deepen the model without widening scope. The editorial goal is:

- add the missing conceptual depth around belief, doctrine, and proof quality
- tighten phase gating around wedge proof and booked pilots/customers
- reduce Phase 6-7 architectural gravity on Phase 0-2
- avoid introducing new major components beyond what is needed for implementation clarity

This revision is a **doc-level restructuring and specification pass**, not a product expansion pass.

## Key Edits

### 1. Add Belief Layer as a derived interpretation layer
Insert a new Section `7.37 Belief Layer` and a new schema `8.28 belief_event`.

Include:
- purpose: model inferred belief change between touchpoints and outcomes
- explicit statement that `belief_event` is derived from observable behavior
- explicit statement that `touchpoint_log` remains source of truth
- single-writer ownership for `belief_events`
- performance constraint: inference must be rule-based and lightweight in early phases
- integration points with Journey Orchestrator, Proof Selector, Growth Advisor, and dashboard views

Add a canonical `Belief Inference Policy`:
- belief is inferred, never treated as ground truth
- every belief event carries confidence
- low-confidence belief signals are logged but excluded from routing decisions
- belief inference rules are versioned and reviewable

Add a canonical `Belief Signal Map`:
- observable behavior
- inferred shift
- confidence
- routing relevance

### 2. Add Doctrine Registry with hard vs soft doctrine
Insert a new Section `7.38 Doctrine Registry` and new schemas `8.29 founder_doctrine` and `8.30 doctrine_conflict_log`.

Split doctrine into two classes:
- `hard_rule`: non-negotiable constraints like forbidden claims, compliance constraints, pricing bounds
- `soft_preference`: strategic preferences like preferred lead angles, proof ordering, segment emphasis

Add canonical precedence rules:
- hard doctrine always beats experiment output, delegate action, and automated recommendations
- soft doctrine constrains recommendations but can be flagged for founder review when evidence consistently conflicts
- doctrine is never silently overridden
- all doctrine conflicts are logged with resolution metadata

Seed doctrine from existing founder-controlled intent already described in the doc:
- approved claims
- forbidden claims
- pricing boundaries
- strategic positioning rules
- approval constraints

### 3. Upgrade proof coverage into proof quality
Revise the Proof Selector and dashboard sections so proof coverage is not binary.

Replace proof status with:
- `gap`
- `weak`
- `covered`

Define:
- `gap`: no proof exists for a key segment × objection × stage combination
- `weak`: proof exists but belief-shift performance is below threshold
- `covered`: proof exists and consistently shifts belief

Add schema `8.31 proof_coverage_entry`.

Update related behavior:
- Growth Advisor should recommend both proof creation and proof improvement
- dashboard heat maps should reflect gap vs weak vs covered
- proof effectiveness should reference belief-layer outputs, not just conversion outcomes

### 4. Reduce future-phase architectural gravity
Revise Phase 0, Phase 1, and schema language so future ambition does not distort early execution.

Apply this rule:
- any field, schema element, or table justified only by Phase 6-7 must either show a Phase 1-2 use case or be deferred

Keep only lightweight future-ready items in early phases:
- additive flags and metadata fields that are effectively free
- simple compatibility fields already aligned with near-term work

Defer heavy future-only items:
- tables or subsystems that exist solely for later strategic intelligence unless they support current wedge proof

Rewrite the Phase 1 success definition around:
- repeatable path from segment to pain to proof to belief shift to booked pilot
- strong attribution
- trustworthy learning
- operator-readable founder insight

### 5. Replace loose phase gates with Wedge Fitness gating
Add a canonical `wedge_fitness_score` definition (new Section 11) and use it as the primary gating system for automation and expansion decisions. Add schema `8.33 wedge_fitness_snapshot`.

Use it for:
- eligibility to move from manual proof to assisted routing
- eligibility to increase autonomy
- eligibility to test pricing
- eligibility to replicate into new wedges

Keep a short separate list of hard operational kill criteria outside the score:
- sender reputation failure
- attribution collapse
- no-pilot threshold after meaningful volume
- major data integrity failure

This preserves catastrophic-stop logic while making the broader progression system coherent.

### 6. Tighten Phase 1 around belief-backed wedge proof
Rewrite Phase 1 success criteria so it no longer reads as "find a winning angle."

Phase 1 should prove:
- at least one repeatable persuasion path
- proof matters, not just message
- booked pilot outcomes are traceable
- the system can explain why a path works well enough to repeat it

Phase 1 should remain narrow:
- HVAC only
- cold email only
- limited proof inventory
- strong instrumentation
- no breadth-first additions

### 7. Fix `insight_log` semantics
Rewrite `insight_log` so it is no longer described as a faux single-writer table.

Make it:
- append-only
- multi-writer by design
- explicitly typed and source-attributed

Require metadata on every entry:
- `source_component`
- `insight_type`
- `supersedes_insight_id` when relevant
- confidence
- review status

Keep ownership strict for stateful tables, but acknowledge that append-only insight logging is intentionally multi-writer.

### 8. Add anti-pattern schema
Add schema `8.32 anti_pattern_entry` for negative knowledge capture. Anti-patterns are context-bounded, not permanent. Lifecycle management (decay, re-evaluation, graduation) is deferred to Phase 2.

### 9. Update Growth Memory and ownership
Update the Growth Memory schema (Section 7.10) to include 6 new tables:
- `belief_events`
- `founder_doctrine`
- `doctrine_conflict_log`
- `proof_coverage_map`
- `anti_pattern_registry`
- `wedge_fitness_snapshots`

Update the Single-Writer Ownership Map to assign write owners for all new tables.

### 10. Add feature flags and validation tests
Add 5 feature flags for progressive rollout:
- `belief_layer`
- `doctrine_enforcement` (default ON)
- `proof_coverage`
- `anti_pattern`
- `wedge_fitness`

Add validation Tests 11-15:
- Test 11: Belief Shift Test — system distinguishes clicked from believed
- Test 12: Proof Coverage Test — uncovered objections generate proof-gap actions
- Test 13: Doctrine Conflict Test — founder doctrine beats model preference
- Test 14: Anti-Pattern Test — known bad combinations are suppressed
- Test 15: Wedge Fitness Gate Test — expansion blocked when component thresholds unmet

### 11. Update data classification and section numbering
Assign new tables to privacy tiers in Section 9 (Data Classification):
- Tier 1: `founder_doctrine`, `doctrine_conflict_log`
- Tier 2: `belief_events`, `proof_coverage_map`, `anti_pattern_registry`, `wedge_fitness_snapshots`

Renumber Sections 12-21 → 13-22 to accommodate new Section 11 (Wedge Fitness Score & Phase Gates).

### 12. Unify Phase 2-3 kill criteria and gates
Update Phase 2 and Phase 3 to use unified kill criteria (hard kills + Wedge Fitness gate) consistent with the Phase 1 structure. Each phase gets an explicit phase gate section.

## Editing Sequence

### Pass 1: Additions
- Add `7.37 Belief Layer`
- Add `8.28 belief_event`
- Add canonical Belief Inference Policy
- Add canonical Belief Signal Map
- Add `7.38 Doctrine Registry`
- Add `8.29 founder_doctrine`
- Add `8.30 doctrine_conflict_log`
- Add doctrine precedence and conflict rules
- Add `8.31 proof_coverage_entry`
- Add `8.32 anti_pattern_entry`
- Add `8.33 wedge_fitness_snapshot`

### Pass 2: Rewrites
- Revise Proof Selector to support `gap | weak | covered`
- Revise dashboard and Growth Advisor references to proof quality
- Revise Phase 0 to remove future-only architectural drag
- Revise Phase 1 success criteria around belief-backed booked pilot proof
- Add `wedge_fitness_score` section (new Section 11) and replace loose progression criteria
- Preserve explicit hard kill criteria
- Rewrite `insight_log` as append-only multi-writer infrastructure
- Update Growth Memory schema with 6 new tables
- Update Single-Writer Ownership Map
- Update Data Classification (Section 9) with new table tier assignments
- Add 5 feature flags for progressive rollout
- Add validation Tests 11-15
- Unify Phase 2-3 kill criteria and phase gates
- Renumber sections 12-21 → 13-22

### Pass 3: Deferrals
Move these to the deferred backlog instead of expanding the doc now:
- anti-pattern lifecycle decay and graduation model
- 5-core narrative/TOC restructure
- wedge fitness calibration refinements
- formal quarterly review process for Belief Signal Map

## Validation Pass

After the edits, the doc should pass these review checks:

- A reader can explain the difference between `touchpoint`, `belief`, and `outcome`
- Founder intent is codified as doctrine, not only inferred from overrides
- Proof quality is distinguishable from proof existence
- Phase 1 reads as depth-first wedge proof, not as a staging area for Phase 7
- The path from manual proof to automation is controlled by explicit gates
- `insight_log` no longer reads as an ownership contradiction
- No new major component was added unless it closed a real conceptual gap
- All new tables have assigned privacy tiers in Data Classification
- All new tables have write owners in the Single-Writer Ownership Map
- Feature flags exist for every new conceptual layer
- Validation tests exist for every new conceptual layer

## Assumptions

- This revision is conceptual and editorial only; no implementation work is included
- The doc should deepen existing logic rather than introduce another broad expansion wave
- The system remains an internal GTM operating system, not a customer-facing platform
- The dominant business outcome remains booked pilots/customers
- Future phases stay in the vision, but should not drive early-phase complexity unless they improve current wedge proof
