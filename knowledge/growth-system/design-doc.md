---
id: growth-system-design
title: CallLock Agentic Growth Loop — Expanded Design Doc
graph: growth-system
owner: founder
last_reviewed: 2026-03-14
trust_level: curated
progressive_disclosure:
  summary_tokens: 500
  full_tokens: 15000
status: Draft — v4: Post CEO mega-review v2 (persuasion path, belief split, proof supply chain, 4-plane, scorecard gates)
---

# CallLock Agentic Growth Loop — Expanded Design Doc

**Date:** March 14, 2026  
**Status:** Draft — v4  
**Owner:** Founder / GTM / Product

## Summary

CallLock should build a Persuasion OS for one wedge before it builds a broad growth machine.

The system exists to discover, explain, and repeat booked-pilot paths for the right buyer. It should learn which segment, pain, objection, proof, and journey sequence create enough conviction and buying readiness to produce a booked pilot or customer. The growth loop is the mechanism. Repeatable persuasion path discovery is the goal.

This v4 revision keeps the conceptual richness of v3 while applying the CEO review’s corrections:

- the atomic unit of learning is explicit
- belief is split into conviction and readiness
- proof quality gets an operating loop, not just a heat map
- the architecture is framed as four planes, not a catalog of organs
- phase gates are scorecards with floors, not a single blended number
- future analytical modules are moved behind the core wedge-proof story

---

## 1. Purpose

Design a self-improving internal GTM operating system for CallLock that discovers, explains, and repeats booked-pilot paths inside one wedge before widening scope.

The system should help CallLock answer:

- who the right buyer is
- which pain angle is most salient
- which proof creates conviction
- which objections block movement
- which next action best advances the prospect
- which repeatable patterns deserve more traffic and more investment

### 1.1 The Atomic Unit of Learning

The canonical unit of learning is:

`persuasion_path = segment × pain × objection × proof × belief_delta × outcome`

This is the reporting lens for:

- routing decisions
- proof quality analysis
- weekly founder review
- gate decisions
- Growth Advisor recommendations
- win-path replication

The system should not ask only, "what converted?" It should ask:

1. Which segment was in play?
2. Which pain was activated?
3. Which objection surfaced?
4. Which proof was shown?
5. What changed in conviction and buying readiness?
6. Did that path create a booked pilot or customer outcome?

Every major metric should roll up by `persuasion_path`. Every decision surface should be able to explain itself in that language.

## 2. Core Thesis

CallLock should not optimize for arbitrary outbound automation, broad content volume, or abstract AI sophistication.

It should optimize for one thing:

**finding and repeating the fastest believable path to "that is exactly my problem" for the right home-service buyer.**

The moat is not having more components. The moat is learning faster and more honestly than competitors which messages, proofs, and journeys actually create conviction and booked pilots.

## 3. Strategic Context

### Positioning anchor

CallLock wins when positioned as the system that turns missed calls into booked jobs for home-service businesses.

### Best initial wedge

Start with one trade where:

- urgency is obvious
- missed calls are expensive
- live response matters
- booking speed matters

Recommended starting wedge: **HVAC first**.

### GTM implication

The system should route prospects into simple, believable, operator-focused stories:

- missed calls become booked jobs
- answers live when you cannot
- books while you work
- better than voicemail or message-taking

## 4. System Goal

Build a repeatable persuasion path discovery system for one wedge.

The growth loop remains the mechanism. The goal is not "closed-loop GTM automation" in the abstract; the goal is discovering repeatable `persuasion_path` patterns that reliably produce booked pilots and can later be replicated into new wedges.

## 5. Design Principles

### 5.1 Workflow-led outside, agentic inside

Externally, the system should feel simple and operational. Internally, agents can enrich, route, analyze, and recommend.

### 5.2 Customer path should be bounded

Anything customer-facing and revenue-critical should operate inside clear policy and business rules. The model selects from approved inventory; it does not improvise claims.

### 5.3 Strategy remains founder-owned

The system can recommend wedges, proof priorities, and routing changes, but strategy, pricing, positioning, and claims remain human-controlled.

### 5.4 Structured assets beat freeform sprawl

Templates, pages, proof assets, and experiments are schema-first and versioned.

### 5.5 Learning must be trustworthy

Fast signals can guide exploration, but only deeper signals should justify strong belief or phase advancement.

### 5.6 Observability is part of the product

If the founder cannot understand what changed and why, the system is underbuilt.

### 5.7 Single-writer state, append-only evidence

Stateful tables should have clear ownership. Event logs, touchpoints, and insights can be append-only multi-writer streams with explicit source attribution.

### 5.8 Universal Rescue Doctrine

Every component must degrade visibly and safely.

| Component | Failure Class | Degraded Mode | Visibility |
|---|---|---|---|
| Enrichment | scrape/classify failure | partial enrichment, low confidence | dashboard + quality counter |
| Routing | missing template or page | bounded fallback asset | advisor alert |
| Proof Supply Chain | proof gap detected but owner/brief generation fails | mark coverage as `gap`, queue manual proof brief | dashboard + advisor alert |
| Conviction/Readiness Inference | dual-axis inference unavailable | fall back to legacy single-axis belief inference, exclude from routing upgrades | dashboard: inference fallback counter |
| Founder Weekly Operating Packet | packet assembly fails | render raw scorecard + alerts + proof queue | founder alert + packet generation metric |
| Doctrine Enforcement | doctrine registry unavailable | conservative mode, block risky actions, route for founder review | critical alert |
| Wedge Fitness Scorecard | one component missing or stale | mark gate incomplete, prevent advancement | gate blocked + scorecard warning |

### 5.9 Idempotency by default

Every event handler is idempotent. Duplicate delivery should not distort outcomes or sends.

### 5.10 Safety systems fail closed

If the health gate or doctrine enforcement layer is unavailable, risky actions queue rather than execute.

### 5.11 Channel-aware, wedge-first

Schemas should be channel-aware from day one, but Phase 1 remains HVAC + cold email only.

### 5.12 Keep future-phase gravity out of Phase 0-3

Future ambition is allowed in vision and appendix. It should not distort the current loop unless it helps current wedge proof.

## 6. What Is the Engine?

The engine is the repeatable persuasion path discovery loop.

It is not:

- just an email writer
- just a page generator
- just a dashboard
- just a bandit allocator
- just an LLM

It is the system that captures demand signals, interprets them, decides the next bounded action, and governs the learning quality of the resulting `persuasion_path`.

---

## 7. System Architecture

### 7.0 Architecture Overview

The system is organized into four planes. This supersedes the old body-metaphor framing and any earlier five-core narrative.

| Plane | Purpose | Representative Components |
|---|---|---|
| Capture | collect source-of-truth events and outcomes | Prospect Enrichment Pipeline, Touchpoint Log, Product-to-Growth Bridge, Sales Insight Layer, Referral Mechanism, Cost Layer |
| Interpret | turn raw signals into usable meaning | Segmentation Engine, Belief Layer, Proof Selector, Signal Quality Layer, Prospect Scoring Model, Intent Signal Detector, Loss Analysis Engine, Decision Audit Engine |
| Decide | choose the next best bounded action | Message Router, Page Router, Journey Orchestrator, Experiment Allocator, Outbound Health Gate, Lifecycle State Machine |
| Govern | make the system legible, safe, and founder-aligned | Founder Doctrine Registry, Growth Advisor, Founder Dashboard, Learning Integrity Monitor, LLM Output Regression Monitor, Strategic Intelligence Briefing, feature flags |

Later-phase analytical modules remain modules within these planes, not first-class organs.

```text
                         PERSUASION PATH DISCOVERY

 Demand Signals
      |
      v
  +-----------+      +-------------+      +-----------+      +-----------+
  | CAPTURE   | ---> | INTERPRET   | ---> | DECIDE    | ---> | GOVERN    |
  | source of |      | meaning,    |      | bounded   |      | safety,   |
  | truth     |      | quality,    |      | next best |      | review,   |
  | events    |      | doctrine    |      | action    |      | gates     |
  +-----------+      +-------------+      +-----------+      +-----------+
         ^                                                        |
         |                                                        v
         +---------------- outcomes and founder feedback ---------+
```

Every major component should be explainable in terms of how it improves or audits a `persuasion_path`.

### 7.1 Prospect Enrichment Pipeline

Purpose: turn raw leads into usable profiles for routing.

Pipeline:

```text
raw lead
  -> web scrape / source fetch
  -> sanitize
  -> classify
  -> validate against enums
  -> confidence scoring
  -> profile write
```

Outputs:

- trade
- likely buyer type
- likely pain profile
- confidence per field
- intent signals
- enrichment freshness

Guardrails:

- sanitize all untrusted text before model use
- validate outputs against enums
- mark uncertain fields as estimated
- route unknowns into explicit fallback segments

Error posture:

- scrape timeout -> partial enrich with low confidence
- classification ambiguity -> dual candidate profile + review flag
- malformed source data -> discard source fragment, not the prospect
- enrichment cost cap breach -> pause queue, preserve raw leads

### 7.2 Segmentation Engine

Purpose: map prospects into GTM buckets that determine initial messaging and destination.

Segmentation is dynamic but bounded:

- initial assignment at enrichment time
- event-driven re-evaluation on meaningful new signals
- oscillation counter and circuit breaker
- primary/secondary segment support

Rules:

- no more than three re-segmentations in seven days without review
- unmatched prospects route to `unclassified`, not null
- primary segment drives routing; secondary segment remains available for later recovery paths

Segmentation flow:

```text
prospect profile
  -> initial segment score set
  -> primary/secondary assignment
  -> new evidence arrives
  -> re-score candidate segments
  -> transition log write
  -> route or hold
```

Shadow paths:

- nil segment evidence -> keep prior segment and mark stale
- competing scores within threshold -> preserve ambiguity and record both
- oscillation limit exceeded -> freeze primary segment, escalate for review

Error table:

| Failure class | Rescue action | Degraded mode |
|---|---|---|
| no matching segment | assign `unclassified` | generic but bounded routing |
| stale profile data | trigger re-enrichment | use prior segment with stale flag |
| repeated oscillation | lock segment window | manual review before further changes |

### 7.3 Message Router

Purpose: choose the angle and approved template family most likely to advance the prospect.

The model is a selector, not a freeform copywriter. It chooses among approved assets and slot values.

Template architecture:

```text
approved template family
  + validated slots
  + approved angle statement
  + approved proof statement
  + approved CTA
```

Inputs:

- segment
- pain hypothesis
- lifecycle stage
- doctrine constraints
- experiment assignment
- proof context

Outputs:

- selected template family
- selected angle
- fallback usage list
- blocked options and why

Example request flow:

```text
segment + pain hypothesis + doctrine snapshot + experiment arm
  -> candidate template families
  -> doctrine filter
  -> slot resolution
  -> fallback fill for missing fields
  -> routing decision log write
```

### 7.4 Asset Inventory System

Purpose: maintain a structured library of GTM assets that the routing layer can safely use.

Asset types:

- outbound templates
- landing pages
- comparison pages
- calculators
- demo-call pages
- FAQs
- proof assets
- offers and CTAs

Lifecycle:

```text
draft
  -> approved
  -> active
  -> under_review
  -> archived
```

Assets should be versioned. Routing references exact versions, not "latest."

### 7.5 Page Router

Purpose: choose where each prospect should go next.

Destinations can include:

- wedge page
- comparison page
- calculator
- demo page
- proof-rich FAQ
- direct booking page

Routing should be explicit about:

- destination page
- secondary destination if the first choice is blocked
- proof order on-page
- CTA path after proof consumption

### 7.6 Proof Selector

Purpose: decide what evidence to show to create conviction and move a prospect forward.

Proof coverage is tracked per segment × objection × lifecycle stage with three states:

- `gap` — no proof exists
- `weak` — proof exists but conviction movement is below threshold
- `covered` — proof exists and consistently creates conviction

Proof quality uses `conviction_shift_rate`, not raw clicks and not a blended belief metric.

#### Proof Supply Chain

The system must not stop at "we have a gap." It needs an operating loop:

```text
objection seen
    -> gap or weak coverage detected
    -> proof brief created
    -> owner assigned
    -> approved
    -> proof deployed
    -> conviction re-measured
    -> coverage state updated
```

`proof_brief` is the structured work object for missing or weak proof:

- target segment
- target objection
- target stage
- recommended proof type
- why now
- owner
- status
- expected revenue impact

Growth Advisor should recommend both proof creation and proof improvement. The Founder Weekly Operating Packet should expose proof debt directly.

Example coverage flow:

```text
touchpoint + objection + proof consumed
  -> belief event derived
  -> conviction shift aggregated by segment x objection x stage
  -> coverage status recomputed
  -> proof debt queue updated if still gap/weak
```

Error table:

| Failure class | Rescue action | Degraded mode |
|---|---|---|
| no proof asset for objection | emit proof brief | route best available fallback proof |
| conviction sample too small | mark state provisional | keep `weak`, avoid promotion to `covered` |
| conflicting proof signals | split by stage/segment and re-score | do not collapse to one global winner |

### 7.7 Experiment Allocator

Purpose: manage traffic allocation and winner detection for bounded experiments.

Principles:

- optimize for value per dollar, not just click rate
- use fast signals for exploration, deeper signals for confidence
- declare winners only after enough sample and stability
- never let one shallow metric dominate

Winner declaration should pass three gates:

1. minimum sample per arm
2. strong enough posterior confidence on the relevant business outcome
3. temporal stability across the measured period

Feedback horizons:

- Tier 1 fast signals: opens, clicks, shallow page engagement
- Tier 2 medium signals: replies, demo plays, meetings
- Tier 3 deep signals: pilot start, pilot conversion, early retention

Tier 1 helps explore. Tier 2 helps allocate. Tier 3 decides what deserves durable trust.

Error table:

| Failure class | Rescue action | Degraded mode |
|---|---|---|
| no eligible experiment | create bounded exploration arm set | uniform allocation within safe inventory |
| unstable posterior | floor values and recompute | freeze winner declaration |
| scorecard floor not met | block automation promotion | continue manual or assisted mode |

### 7.8 Sales Insight Layer

Purpose: convert calls, replies, and notes into structured insight.

Outputs:

- objection taxonomy updates
- competitor mentions
- talk-track gaps
- FAQ candidates
- recurring blockers by segment

### 7.9 Product Outcome Layer

Purpose: feed real product performance back into GTM understanding without letting product ambitions dominate early phases.

Key signals:

- calls answered
- booking completion
- scenario performance
- escalation rate
- pilot-to-customer movement

Flow:

```text
product event
  -> transform to GTM-safe signal
  -> join to attribution chain where possible
  -> update persuasion-path evidence
  -> influence proof and segment understanding
```

The layer should strengthen proof claims and scenario fit, not become a catch-all product analytics platform.

### 7.10 Growth Memory

Purpose: hold the shared knowledge that lets learning compound instead of reset every week.

Core tables:

- touchpoint_log
- routing_decision_log
- segment_performance
- angle_effectiveness
- proof_coverage_map
- belief_events
- founder_doctrine
- doctrine_conflict_log
- experiment_history
- cost_per_acquisition
- insight_log

Supporting tables that matter early:

- segment_transitions
- journey_assignments
- loss_records
- anti_pattern_registry
- wedge_fitness_snapshots

Design rules:

- source-of-truth logs are append-only
- stateful tables have clear write owners
- all important derived layers are recomputable from lower-level evidence

Single-writer map, conceptually:

- enrichment owns prospect-profile writes
- segmentation owns segment transitions
- experiment allocator owns experiment state
- proof selector owns proof coverage recomputation
- doctrine registry owns doctrine state
- advisor owns synthesized insights, not raw evidence

Evidence hierarchy:

```text
touchpoint_log / product events / explicit founder actions
  -> derived belief + coverage + performance layers
  -> scorecards + recommendations + dashboards
```

Rollback posture:

- if a derived layer is wrong, recompute from lower evidence
- if a routing recommendation is wrong, preserve the log and correct the model
- if doctrine changes, preserve both the prior rule and the new effective rule

### 7.11 Signal Quality Layer

Purpose: score events before they influence memory, routing, or gates.

Functions:

- source verification
- behavioral coherence
- anomaly detection
- quarantine of low-quality events

Scoring bands:

- `> 0.7` full weight
- `0.3 - 0.7` reduced weight + reviewable
- `< 0.3` quarantined from decisioning

Scoring flow:

```text
raw event
  -> source verification
  -> coherence checks
  -> anomaly checks
  -> quality score
  -> write / reduce / quarantine
```

Error table:

| Failure class | Rescue action | Degraded mode |
|---|---|---|
| scorer unavailable | apply neutral reduced weight | preserve event, avoid full trust |
| mass anomaly spike | assume possible scoring bug | pause quarantine, route to review |
| missing source metadata | lower score and continue | analysis-only unless later corroborated |

### 7.12 Learning Integrity Monitor

Purpose: detect when the system is learning badly even if it is still operating.

Questions:

1. Is data flowing?
2. Is attribution connecting?
3. Is evidence trustworthy?
4. Are gates being fed with enough qualified data?

Alert surfaces:

- attribution completeness drop
- proof coverage stagnation
- doctrine conflict spike
- repeated gate blocks from the same failed floor
- signal quality collapse

### 7.13 Outbound Health Gate

Purpose: enforce compliance and sender reputation before any outbound action executes.

Checks:

- suppression list
- bounce/complaint thresholds
- daily caps
- duplicate send window
- required legal fields
- doctrine compliance
- lifecycle eligibility

Hard invariant:

If the health gate itself is unavailable, outbound queues. It never fails open.

Gate flow:

```text
routing decision
  -> suppression check
  -> doctrine check
  -> sender health check
  -> duplicate window check
  -> lifecycle eligibility check
  -> send or queue
```

### 7.14 Growth Advisor

Purpose: synthesize learning into recommendations that the founder can approve, reject, or defer.

It should recommend:

- routing adjustments
- proof creation or improvement
- doctrine review when evidence conflicts with preferences
- experiments worth launching or killing
- stuck or decaying persuasion paths

Output surfaces:

- weekly operating packet
- dashboard cards
- recommendation queue
- proof debt queue
- doctrine conflict queue

A recommendation is only valid if it can cite:

- the relevant persuasion paths
- the evidence window
- any doctrine constraints
- the expected impact of acting or not acting

Recommendation states:

```text
draft
  -> reviewable
  -> approved / overridden / deferred
```

Overrides should carry reasoning when possible:

- data wrong
- timing wrong
- strategy wrong
- other

### 7.15 Founder Dashboard

Purpose: expose system health, winning paths, proof debt, doctrine conflicts, and decision queues.

Levels:

- daily health glance
- weekly what's winning
- weekly what should I do
- investigation view for reasoning chains

The dashboard should be able to answer:

- which persuasion paths are improving?
- which objections lack proof?
- which doctrine rules are constraining experiments?
- what changed since last week?

Minimum panes:

- health and scorecards
- winning and decaying persuasion paths
- proof debt and doctrine conflicts
- review queue
- audit trail for one prospect or one experiment

### 7.16 Touchpoint Log

Purpose: immutable source of truth for every relevant interaction.

It records:

- prospect and company IDs
- touchpoint type
- channel
- experiment and arm
- cost
- signal quality
- timestamp

Touchpoint log remains the source of truth over any later belief or score interpretation.

### 7.17 Routing Decision Log

Purpose: preserve the full reasoning context behind each bounded action.

Each record should capture:

- inputs
- doctrine checks
- selected assets
- confidence
- fallbacks used
- gate results

This is the main audit surface for "Why did the system choose this?"

### 7.18 Cost & Unit Economics Layer

Purpose: let the system optimize for persuasion path quality per dollar, not just response rate.

Track:

- enrichment cost
- asset cost
- send cost
- review cost
- cost per meeting
- cost per pilot

The allocator should never consume a conversion metric without the corresponding cost context being available or explicitly missing.

### 7.19 Prospect Lifecycle State Machine

Purpose: model where the prospect is in their journey and gate what actions are allowed.

Primary states:

- UNKNOWN
- REACHED
- ENGAGED
- EVALUATING
- IN PIPELINE
- PILOT STARTED
- CUSTOMER
- DORMANT
- LOST

Key invalid transitions should be explicitly blocked, for example:

- UNKNOWN -> IN PIPELINE
- LOST -> PILOT STARTED
- DORMANT -> CUSTOMER without an intermediate engagement signal

Canonical flow:

```text
UNKNOWN
  -> REACHED
  -> ENGAGED
  -> EVALUATING
  -> IN PIPELINE
  -> PILOT STARTED
  -> CUSTOMER

Shadow paths:
REACHED -> DORMANT
EVALUATING -> LOST
CUSTOMER -> DORMANT (win-back or expansion later)
```

### 7.20 Journey Orchestrator

Purpose: choose and adapt multi-step journeys instead of treating every touch as isolated.

The orchestrator should maintain narrative coherence:

- pain recognition
- proof delivery
- comparison or FAQ
- urgency or CTA

Adaptive examples:

- objection raised -> insert counter-proof
- high conviction but low readiness -> reduce urgency, increase evaluation support
- high readiness and covered objection set -> advance to CTA sooner

Journey state flow:

```text
assigned
  -> step_due
  -> step_sent
  -> response_evaluated
  -> adapted / advanced / exited
```

Exit conditions:

- meeting booked
- pilot started
- moved to dormant
- explicit loss

Error table:

| Failure class | Rescue action | Degraded mode |
|---|---|---|
| missing next step | fall back to safe default nurture step | preserve journey continuity |
| conflicting active journeys | latest valid journey wins | archive the older one |
| unsupported response pattern | continue default path | log unmatched response for later rule design |

### 7.21 Prospect Scoring Model

Purpose: prioritize enrichment depth, routing priority, and cadence based on expected fit and timing.

Scoring inputs:

- segment conversion rate
- enrichment confidence
- lookalike fit
- intent signal strength
- geographic context
- seasonal alignment

Score bands:

- hot
- warm
- cool
- cold

Use:

- enrichment depth
- queue priority
- cadence intensity
- experiment allocation priority

Scoring should remain advisory to routing, not a hidden override of segment and doctrine.

### 7.22 Intent Signal Detector

Purpose: infer whether a prospect appears in-market now, not just whether they are theoretically a fit.

Examples:

- review surge
- hiring signal
- service-area expansion
- seasonal emergency context

### 7.23 Loss Analysis Engine

Purpose: convert losses into targeting, proof, pricing, and qualification improvements.

Loss reasons should be structured and queryable.

Suggested taxonomy:

- price
- competitor
- timing
- no need
- bad fit
- feature gap
- trust
- unknown

### 7.24 Decision Audit Engine

Purpose: detect drift, exploration collapse, outcome disconnect, and blind spots in the system’s own choices.

Audit questions:

- are we over-routing to the same path without evidence?
- are we exploring enough to discover new wins?
- are Tier 1 gains disconnected from Tier 3 outcomes?
- are some prospect shapes always getting the same answer regardless of evidence?

Outputs:

- weekly audit summary
- flagged blind spots
- exploration warnings
- local-optimum warnings

### 7.25 Referral Mechanism

Purpose: activate advocate-driven acquisition without breaking attribution or narrative coherence.

Referral-specific rule:

A referred prospect starts with inherited social proof, so the journey should usually skip generic pain recognition and lead with proof and evaluation support.

### 7.26 Strategic Intelligence Briefing

Purpose: synthesize major learnings for leadership without turning future modules into present-tense dependencies.

This remains a governed output, not an excuse to re-expand scope in the core loop.

### 7.27 Future Module Boundary

Any module justified only by later strategic intelligence belongs in Appendix B unless it improves current wedge proof.

### 7.37 Belief Layer

Purpose: infer what changed inside the prospect journey strongly enough to matter for routing and proof evaluation.

Belief is split into two dimensions:

- `conviction_shift` — did the prospect become more convinced the claim is true?
- `buying_readiness_shift` — did the prospect become more ready to act now?

These are related but not identical. A prospect can become more convinced while remaining unready, or become more ready while still carrying unresolved objections.

#### Belief Inference Policy

- touchpoint logs remain the source of truth
- belief events are derived, recomputable annotations
- low-confidence inferences are logged but excluded from routing decisions
- proof coverage references `conviction_shift_rate`
- journey adaptation can use both conviction and readiness when confidence is sufficient
- conviction analysis should answer "did the proof work?"
- readiness analysis should answer "is now the right next step?"

#### Belief Signal Map

| Observable behavior | Conviction shift | Buying readiness | Conviction confidence | Readiness confidence | Routing relevance |
|---|---|---|---|---|---|
| email opened, no click | flat | flat | 0.2 | 0.1 | none |
| page depth > 2 | up | flat | 0.5 | 0.3 | moderate |
| watched demo > 60% | up | up | 0.7 | 0.5 | high |
| comparison page > 30s | up | flat | 0.6 | 0.3 | moderate |
| calculator completed | up | up | 0.6 | 0.7 | high |
| replied with objection | flat | up | 0.3 | 0.6 | high |
| replied asking for call | up | up | 0.8 | 0.9 | very high |
| meeting booked | up | up | 0.8 | 0.95 | very high |
| meeting no-show | down | down | 0.6 | 0.8 | high |

This keeps proof analysis honest: proof is judged primarily by its effect on conviction, while journey timing can respond to readiness.

Interpretation rule:

- conviction should answer "did this proof change their mind?"
- readiness should answer "are they more prepared to take the next step now?"

Error table:

| Failure class | Rescue action | Degraded mode |
|---|---|---|
| evidence supports only one dimension | log the supported dimension and set the other to `flat` with low confidence | partial belief event |
| signal map miss | log unmapped signal | no routing impact |
| confidence below threshold | retain for analysis only | exclude from decisioning |

### 7.38 Founder Doctrine Registry

Purpose: encode founder strategy as explicit, queryable doctrine rather than relying on a trail of overrides.

Doctrine fields:

- `scope` — messaging, pricing, claims, wedge, approval, routing
- `owner` — founder by default; delegates may propose soft doctrine only
- `review_cadence` — weekly, monthly, quarterly
- `affected_surfaces` — templates, pages, experiments, pricing tests, dashboards
- `blast_radius` — low, medium, high

Doctrine strengths:

- `hard_rule` — cannot be violated by experiments, delegates, or automation
- `soft_preference` — creates friction and a review path, not a silent override

Doctrine is never silently overridden. All conflicts are logged with resolution metadata.

Typical doctrine seeds:

- approved claims
- forbidden claims
- pricing boundaries
- strategic positioning rules
- approval constraints

Doctrine authoring flow:

```text
rule proposed
  -> scope and blast radius assigned
  -> founder review
  -> active
  -> future conflict logging and scheduled review
```

Error table:

| Failure class | Rescue action | Degraded mode |
|---|---|---|
| conflicting hard rules | reject newer rule until resolved | existing doctrine stays active |
| stale doctrine past review date | keep enforced, emit review prompt | no silent expiry |
| doctrine registry unavailable | conservative mode | risky routing blocked |

---

## 8. Schemas

### 8.1 Prospect schema

```json
{
  "prospect_id": "uuid",
  "company_id": "uuid",
  "trade": "hvac",
  "buyer_type": "owner_operator",
  "pain_profile": ["missed_calls", "after_hours"],
  "primary_segment": "hvac_owner_operator_missed_calls",
  "secondary_segments": ["hvac_owner_operator_after_hours"],
  "lifecycle_state": "REACHED",
  "source_channel": "cold_email",
  "prospect_score": 72,
  "intent_signals": {
    "strength": "moderate",
    "signals": ["review_volume_surge"]
  },
  "confidence": {
    "trade": 0.95,
    "pain_profile": 0.78
  }
}
```

### 8.2 Experiment schema

```json
{
  "experiment_id": "uuid",
  "segment": "hvac_owner_operator_missed_calls",
  "channel": "cold_email",
  "lifecycle_stage_scope": "UNKNOWN_TO_REACHED",
  "arms": [
    {
      "arm_id": "a",
      "angle": "booked_jobs",
      "template_id": "tmpl_hvac_missed_001",
      "destination_page": "/hvac/missed-call-booking-system",
      "proof_asset": "demo_hvac_call_01"
    }
  ],
  "status": "exploring"
}
```

### 8.3 Outcome schema

```json
{
  "outcome_id": "uuid",
  "prospect_id": "uuid",
  "experiment_id": "uuid",
  "arm_id": "a",
  "replied": true,
  "clicked": true,
  "meeting_booked": false,
  "pilot_started": false,
  "cost_to_date": 1.47
}
```

### 8.4 Touchpoint log schema

```json
{
  "touchpoint_id": "uuid",
  "prospect_id": "uuid",
  "touchpoint_type": "email_sent",
  "channel": "cold_email",
  "experiment_id": "uuid",
  "arm_id": "a",
  "signal_quality_score": 0.85,
  "cost": 0.12,
  "timestamp": "2026-03-14T12:00:00Z"
}
```

### 8.5 Routing decision schema

```json
{
  "decision_id": "uuid",
  "prospect_id": "uuid",
  "timestamp": "2026-03-14T12:05:00Z",
  "inputs": {
    "primary_segment": "hvac_owner_operator_missed_calls",
    "pain_hypothesis": "missed_calls",
    "lifecycle_state": "REACHED",
    "doctrine_snapshot_version": 4
  },
  "outputs": {
    "template_id": "tmpl_hvac_missed_001",
    "destination_page": "/hvac/missed-call-booking-system",
    "proof_asset_id": "demo_hvac_call_01"
  },
  "gates_passed": {
    "health_gate": true,
    "doctrine_gate": true,
    "lifecycle_gate": true
  },
  "fallbacks_used": []
}
```

### 8.6 Proof brief schema

```json
{
  "proof_brief_id": "uuid",
  "segment": "hvac_owner_operator_missed_calls",
  "objection": "already_have_answering_service",
  "lifecycle_stage": "EVALUATING",
  "recommended_proof_type": "comparison",
  "why_now": "high-volume objection with weak conviction movement",
  "owner": "founder",
  "status": "draft",
  "expected_revenue_impact": "high",
  "created_at": "2026-03-14T00:00:00Z"
}
```

### 8.7 Template schema

```json
{
  "template_id": "tmpl_hvac_missed_001",
  "version": 3,
  "target_segment": "hvac_owner_operator_missed_calls",
  "target_angle": "booked_jobs",
  "channel": "cold_email",
  "subject_template": "{trade_title} companies are booking more jobs from missed calls",
  "body_template": "Hi {first_name}, most {trade} companies tell us {angle_statement}. {proof_statement}. {cta_statement}.",
  "slots": {
    "first_name": {"source": "prospect.contact_name", "fallback": "there"},
    "trade": {"source": "prospect.trade", "validation": "enum"},
    "angle_statement": {"source": "approved_angle_library", "validation": "approved_only"},
    "proof_statement": {"source": "approved_proof_library", "validation": "approved_only"},
    "cta_statement": {"source": "approved_cta_library", "validation": "approved_only"}
  },
  "status": "active"
}
```

### 8.8 Wedge configuration schema

```json
{
  "wedge_id": "hvac",
  "trade": "hvac",
  "segments": [
    {"id": "hvac_owner_missed", "name": "Owner-led + missed daytime calls"},
    {"id": "hvac_owner_afterhours", "name": "Owner-led + after-hours pain"}
  ],
  "angles": [
    {"id": "booked_jobs", "statement": "Missed calls become booked jobs"},
    {"id": "after_hours", "statement": "After-hours leads should not hit voicemail"}
  ],
  "channels": ["cold_email"],
  "proof_assets": ["demo_hvac_call_01", "calculator_01"],
  "experiment_defaults": {
    "min_sample_per_arm": 100,
    "significance_threshold": 0.9,
    "temporal_stability_required": true
  }
}
```

### 8.9 Cost per acquisition schema

```json
{
  "cost_record_id": "uuid",
  "experiment_id": "uuid",
  "arm_id": "a",
  "channel": "cold_email",
  "enrichment_cost": 0.08,
  "asset_cost": 0.03,
  "send_cost": 0.12,
  "review_cost": 0.09,
  "total_cost_per_meeting": 42.0,
  "total_cost_per_pilot": 210.0
}
```

### 8.10 Journey assignment schema

```json
{
  "journey_assignment_id": "uuid",
  "prospect_id": "uuid",
  "journey_id": "journey_hvac_owner_cold",
  "current_step": 2,
  "status": "active",
  "next_step_due_at": "2026-03-18T09:00:00Z"
}
```

### 8.11 Loss record schema

```json
{
  "loss_id": "uuid",
  "prospect_id": "uuid",
  "loss_reason": "competitor",
  "loss_reason_detail": "Chose incumbent answering service with lower monthly price",
  "segment": "hvac_owner_operator_missed_calls",
  "experiment_id": "uuid",
  "arm_id": "a",
  "recoverable": true,
  "recovery_eligible_after": "2026-06-14T00:00:00Z",
  "timestamp": "2026-03-14T00:00:00Z"
}
```

### 8.12 Feature flag snapshot schema

```json
{
  "flag_snapshot_id": "uuid",
  "captured_at": "2026-03-14T00:00:00Z",
  "flags": {
    "growth.enrichment.enabled": true,
    "growth.belief_layer.enabled": false,
    "growth.doctrine_enforcement.enabled": true,
    "growth.proof_coverage.enabled": false
  },
  "environment": "staging"
}
```

### 8.13 Operating packet schema

```json
{
  "packet_id": "uuid",
  "period_start": "2026-03-07T00:00:00Z",
  "period_end": "2026-03-14T00:00:00Z",
  "what_changed": [
    "after-hours HVAC owner-operators improved from weak to covered on demo proof"
  ],
  "what_to_approve": [
    "approve comparison proof brief for answering-service objection"
  ],
  "what_to_kill": [
    "retire interruption angle for dispatcher-heavy segment"
  ],
  "what_proof_to_build_next": [
    "comparison proof for already-have-answering-service objection"
  ]
}
```

### 8.14 Churn record schema

```json
{
  "churn_id": "uuid",
  "customer_id": "uuid",
  "prospect_id": "uuid",
  "churn_reason": "price",
  "churn_reason_detail": "Monthly cost too high relative to perceived value",
  "acquisition_channel": "cold_email",
  "acquisition_experiment_id": "uuid",
  "segment_at_acquisition": "hvac_owner_operator_missed_calls",
  "recoverable": true,
  "recovery_eligible_after": "2026-06-14T00:00:00Z",
  "timestamp": "2026-03-14T00:00:00Z"
}
```

### 8.15 Referral link schema

```json
{
  "referral_link_id": "uuid",
  "referrer_customer_id": "uuid",
  "referrer_trade": "hvac",
  "attribution_token": "signed_token",
  "status": "active",
  "created_at": "2026-03-10T00:00:00Z",
  "expires_at": "2026-06-10T00:00:00Z",
  "referrals_generated": 3,
  "referrals_converted": 1
}
```

### 8.16 Learning score schema

```json
{
  "score_id": "uuid",
  "score_date": "2026-03-14T00:00:00Z",
  "learning_score": 68,
  "components": {
    "knowledge_frontier": 72,
    "prediction_accuracy": 65,
    "discovery_rate": 74,
    "transfer_success": 55,
    "founder_alignment": 78
  },
  "trend": "up"
}
```

### 8.17 Anti-pattern entry schema

```json
{
  "anti_pattern_id": "uuid",
  "pattern_type": "segment_angle_mismatch",
  "segment": "hvac_dispatcher_heavy",
  "angle": "interruption",
  "channel": "cold_email",
  "failure_mode": "zero_tier2_signals_after_200_prospects",
  "confidence": 0.82,
  "avoid_until_reviewed": true,
  "review_trigger": "new_proof_asset_for_segment"
}
```

### 8.18 Decision audit result schema

```json
{
  "audit_id": "uuid",
  "audit_date": "2026-03-14T00:00:00Z",
  "overall_status": "healthy",
  "analyses": {
    "decision_drift": "ok",
    "exploration_collapse": "warning",
    "outcome_disconnect": "ok",
    "systematic_blind_spots": "ok"
  },
  "recommendations": [
    "increase exploration in hvac_owner_operator_missed_calls"
  ]
}
```

### 8.25 Aggregate intelligence schema

Reserved stub. Full description moved to Appendix B: Future Analytical Modules.

### 8.26 Product usage correlation schema

Reserved stub. Full description moved to Appendix B: Future Analytical Modules.

### 8.28 Belief event schema

```json
{
  "belief_event_id": "uuid",
  "prospect_id": "uuid",
  "touchpoint_id": "uuid",
  "lifecycle_stage": "EVALUATING",
  "pain_hypothesis": "missed_calls",
  "objection": "already_have_answering_service",
  "proof_asset_id": "demo_hvac_call_01",
  "conviction_shift": "up",
  "buying_readiness_shift": "flat",
  "conviction_confidence": 0.72,
  "buying_readiness_confidence": 0.48,
  "evidence_source": "page_behavior",
  "evidence_detail": "demo viewed 78% duration",
  "belief_signal_map_version": 2,
  "next_best_action": "comparison_proof",
  "timestamp": "2026-03-14T14:32:00Z"
}
```

### 8.29 Founder doctrine schema

```json
{
  "doctrine_id": "uuid",
  "scope": "messaging",
  "decision_type": "forbidden_claim",
  "strength": "hard_rule",
  "rule": "Never claim CallLock replaces human dispatchers",
  "rationale": "Legal risk and misrepresentation. CallLock augments, not replaces.",
  "effective_from": "2026-03-14T00:00:00Z",
  "review_after": "2026-06-14T00:00:00Z",
  "priority": 1,
  "created_by": "founder",
  "review_cadence": "monthly",
  "affected_surfaces": ["templates", "landing_pages", "experiments"],
  "blast_radius": "high"
}
```

### 8.30 Doctrine conflict schema

```json
{
  "conflict_id": "uuid",
  "doctrine_id": "uuid",
  "conflicting_signal_type": "experiment_data",
  "conflicting_signal_detail": "price-first angle won 3 consecutive experiments",
  "resolution": "doctrine_reaffirmed",
  "resolved_by": "founder",
  "resolved_at": "2026-03-15T00:00:00Z"
}
```

### 8.31 Proof coverage entry schema

```json
{
  "coverage_id": "uuid",
  "segment": "hvac_owner_operator_missed_calls",
  "objection": "already_have_answering_service",
  "lifecycle_stage": "EVALUATING",
  "coverage_status": "weak",
  "conviction_shift_rate": 0.31,
  "proof_assets": [
    {
      "proof_asset_id": "demo_hvac_call_01",
      "proof_type": "demo_call",
      "conviction_shift_rate": 0.31,
      "sample_size": 34
    }
  ],
  "proof_brief": {
    "recommended_proof_type": "comparison",
    "why_now": "high-volume objection with weak conviction movement",
    "owner": "founder",
    "status": "draft",
    "expected_revenue_impact": "high"
  }
}
```

### 8.33 Wedge fitness snapshot schema

```json
{
  "snapshot_id": "uuid",
  "wedge": "hvac",
  "trend_score": 62,
  "component_scores": {
    "booked_pilot_rate": 0.65,
    "attribution_completeness": 0.88,
    "proof_coverage": 0.55,
    "founder_alignment": 0.78,
    "learning_velocity": 0.70,
    "retention_quality": 0.60,
    "segment_clarity": 0.80,
    "cost_efficiency": 0.72,
    "conviction_depth": 0.45,
    "readiness_quality": 0.52
  },
  "gates_status": {
    "automation_eligible": true,
    "closed_loop_eligible": false,
    "expansion_eligible": false,
    "pricing_experiment_eligible": true
  }
}
```

---

## 9. Data Classification & Privacy

Four tiers:

- Tier 1 — aggregate metrics and safe summaries
- Tier 2 — pseudonymous prospect-linked operating data
- Tier 3 — identifiable PII
- Tier 4 — sensitive raw content, redacted or discarded at write time

Examples:

- Tier 1: proof coverage, scorecards, aggregate performance, doctrine rules
- Tier 2: belief events, touchpoints, routing logs, loss records
- Tier 3: prospect identity, company domain, contact details
- Tier 4: raw transcripts, raw replies, raw recordings

Rules:

- raw transcripts and raw replies should not become permanent growth memory
- dashboard and API queries over Tier 2 should enforce minimum cohort safeguards
- deletion requests should sever identity links while preserving safe aggregates

## 10. Agentic vs Non-Agentic Split

### Fully agentic

- enrichment
- classification
- routing selection from approved inventory
- signal quality scoring
- bounded experiment allocation
- proof gap detection

These are safe only when their outputs remain bounded by doctrine, inventory, and gates.

### Bounded agentic with human oversight

- strategic recommendations
- proof brief drafting
- doctrine review prompts
- asset proposals

### Human-controlled

- positioning
- pricing
- legal and compliance claims
- doctrine authoring
- wedge expansion decisions
- hard-kill decisions

Delegate approvals may exist between these surfaces, but they should remain narrower than founder-owned strategy.

---

## 11. Wedge Fitness Score & Phase Gates

The composite Wedge Fitness Score remains a trend metric. It is not, by itself, permission to advance.

`persuasion_path` quality should rise alongside the score. If the composite improves while proof quality, doctrine alignment, or attribution integrity falls, the system is not actually ready to advance.

### Wedge Fitness Trend Metric

Track a 0-100 composite for momentum and comparison over time.

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

### Gate Scorecards

One strong component cannot compensate for a component below its floor.

| Gate | Trend requirement | Component floors that ALL must pass |
|---|---|---|
| Automation eligibility | Wedge Fitness trending above 40 | attribution completeness >= 0.8; proof coverage >= 0.5; doctrine stable for 2 weeks |
| Closed-loop eligibility | Wedge Fitness trending above 60 | conviction coverage on top objections >= 0.6; readiness confidence usable in routing; founder override rate < 0.4 |
| Expansion eligibility | Wedge Fitness trending above 75 | retention quality >= 0.7; proof coverage on top objections >= 0.7; at least one proven `persuasion_path` replicated twice |
| Pricing experiment eligibility | Wedge Fitness trending above 50 | loss analysis sample >= 30; price-related losses >= 20%; doctrine allows pricing test |

Hard operational kills remain outside the scorecard:

- sender reputation failure
- attribution collapse
- no-pilot threshold after meaningful volume
- major data integrity failure

---

## 12. Phase Plan

### Phase 0 — Foundation and Instrumentation

Goal: create the minimum structure needed to learn.

Build:

- wedge taxonomy
- segment taxonomy
- angle taxonomy
- Growth Memory core schemas
- touchpoint log
- routing decision log
- doctrine seed set
- proof coverage map
- feature flags
- signal quality rules
- scorecard gate definitions

Exit criteria:

- every outbound touch can be tied to a segment, pain hypothesis, proof context, and outcome
- doctrine seed rules exist for claims and pricing boundaries
- proof coverage starter map exists for top HVAC objections
- scorecard definitions exist even if many floors are initially unmet

### Phase 1 — Manual Wedge Proof

Goal: prove one wedge with humans in the loop while building trusted instrumentation.

Scope:

- HVAC only
- cold email only
- limited proof inventory
- strong event capture
- founder-reviewed templates and proof

Success:

- at least one repeatable `persuasion_path`
- traceable path from segment -> pain -> proof -> booked pilot
- founder can explain why it works

Kill criteria:

- sender reputation breach
- attribution collapse
- zero pilots after meaningful volume
- inability to define a clean segment taxonomy

### Phase 2 — Assisted Routing and Asset Selection

Same loop, less manual effort, more trust.

Phase 2 should automate more of the existing `persuasion_path` loop, not introduce a new ambition layer. New analytical modules are opportunistic, not prerequisites, unless they improve trust or explanation.

Success:

- routing suggestions outperform static defaults
- proof sequencing improves movement into meetings or pilots
- doctrine conflicts are visible and reviewable

### Phase 3 — Closed-Loop GTM Optimization

Same loop, closed automatically.

Phase 3 should automate the already-proven loop. Anything that does not clearly improve `persuasion_path` discovery, proof quality, or founder trust should remain optional.

Success:

- the system can reliably identify and scale winning paths
- automation stays bounded by doctrine and scorecard floors
- founder review shifts from tactical routing to strategic approval

### Phase 4 — Product Feedback Integration

Goal: feed real product outcomes back into persuasion analysis and proof selection.

Success:

- product outcomes improve proof prioritization
- proof assets start reflecting real scenario performance
- GTM language and proof claims become more grounded in actual customer behavior

### Phase 5 — Wedge Replication Engine

Goal: replicate a proven wedge using configuration, proof inventory, and doctrine, not a rewrite of the core loop.

Success:

- new wedge launch time falls materially relative to the first wedge
- the replicated wedge reuses core routing, doctrine, and proof processes
- at least one winning persuasion path transfers with less time-to-proof

### Phase 6

Future analytical expansion is deferred to Appendix B: Future Analytical Modules.

### Phase 7

Future network and aggregate intelligence expansion is deferred to Appendix B: Future Analytical Modules.

---

## 13. Initial Asset Inventory for Phase 1

Pages:

- `/`
- `/hvac/`
- `/hvac/missed-call-booking-system`
- `/compare/hvac-answering-service-vs-ai-receptionist`
- `/tools/missed-call-revenue-calculator`
- `/demo/hvac-booking-call`

Proof assets:

- one HVAC demo call
- one workflow visual
- one calculator
- one FAQ pack
- one voicemail comparison

Outbound template families:

- missed calls
- after-hours
- interruption
- better than voicemail

## 14. Metrics

The key question is whether the system is getting better at discovering and repeating winning `persuasion_path` patterns.

Core metrics:

- reply rate by segment
- proof-driven conviction movement
- meeting-book rate
- pilot-start rate
- attribution completeness
- proof coverage state
- cost per meeting
- cost per pilot

Interpretive metrics:

- conviction movement rate by proof asset
- readiness movement rate by journey step
- doctrine conflict rate
- proof debt backlog size
- repeatability of top persuasion paths

### 14.1 Founder Weekly Operating Packet

The founder should get one weekly packet that is readable in 15 minutes and decidable in 15 minutes.

The packet is organized around `persuasion_path` changes:

- **What Changed** — which paths improved, degraded, or stalled
- **What to Approve** — doctrine changes, proof briefs, bounded experiments, routing changes
- **What to Kill** — weak paths, stale proof, non-performing angles, blocked experiments
- **What Proof to Build Next** — highest-value proof debt ranked by expected revenue impact

The packet replaces dashboard wandering with a bounded decision ritual.

## 15. Risks

- premature automation before wedge proof
- overfitting on shallow signals
- doctrine drift or silent policy bypass
- proof sprawl without proof quality
- false confidence from noisy data
- sender reputation damage
- attribution breakage
- future-phase gravity distorting the current loop

Mitigation posture:

- use scorecard floors, not just trend scores
- treat touchpoint log as higher truth than derived interpretation
- require doctrine conflict visibility, never silent override
- keep proof debt visible in weekly operations

## 16. What This System Is Not

This system is not:

- a generic autonomous SDR
- a broad content farm
- a replacement for positioning clarity
- a giant catalog of unrelated growth modules
- an LLM content generator for customer-facing copy

## 17. Existing Infrastructure to Reuse

Existing systems and patterns that should shape implementation:

- HVAC industry knowledge and taxonomy
- event infrastructure
- multi-tenant data isolation
- async job patterns
- observability conventions
- existing database migration patterns

The implementation should reuse existing event, database, and multi-tenant patterns wherever possible instead of inventing parallel substrate.

## 18. Validation Strategy

The doc should support explicit validation, not hand-wavy confidence.

Core tests:

1. Full-loop simulation
2. Learning correctness test
3. Proof coverage test
4. Belief split test for conviction vs readiness
5. Doctrine conflict test
6. Anti-pattern suppression test
7. Wedge Fitness scorecard gate test

Suggested named scenarios:

1. Full-loop simulation: synthetic prospects move through enrichment, routing, proof, and outcomes
2. Learning correctness test: allocator converges on the right path using deeper signals
3. Conviction vs readiness split test: the system treats "interested but unconvinced" differently from "convinced but not ready"
4. Proof supply chain test: a gap creates a proof brief and later recomputes coverage
5. Doctrine conflict test: hard doctrine blocks, soft doctrine escalates
6. Anti-pattern test: known bad combinations are suppressed from new experiment proposals
7. Scorecard gate test: a strong trend score cannot mask a failed floor

Pass criteria:

- routing changes can be explained from logged evidence
- proof coverage state changes can be reproduced from touchpoints plus belief events
- doctrine conflicts always emit a record
- blocked gates identify which floor failed
- packet generation produces an actionable weekly decision set without manual assembly

Expanded scenario detail:

### Test 1: Full-loop simulation

Inject synthetic prospects across three segments with mixed confidence and missing-field cases. Verify:

- enrichment writes profiles with confidence
- segmentation routes unknowns explicitly
- routing decisions log doctrine and gate context
- outcomes update the relevant persuasion-path metrics

### Test 2: Learning correctness test

Create arms with known outcome distributions and different costs. Verify:

- allocator explores broadly early
- deeper signals dominate winner confidence later
- value-per-dollar beats click-rate-only optimization

### Test 3: Conviction vs readiness split test

Create two groups:

- Group A: high clicks, low conviction, low readiness
- Group B: moderate clicks, strong conviction, moderate readiness

Verify:

- proof coverage prefers Group B evidence
- journeys give Group A more proof and Group B more CTA support

### Test 4: Proof supply chain test

Create one uncovered objection and one weak objection. Verify:

- both create visible proof debt
- only the weak objection references proof improvement rather than proof creation
- deployed proof can later move the state to `covered`

### Test 5: Doctrine conflict test

Set one hard doctrine and one soft preference. Verify:

- hard doctrine blocks conflicting routing
- soft doctrine allows review with explicit conflict logging
- founder resolution updates future decisions

### Test 6: Anti-pattern suppression test

Register a known-bad segment/angle combination. Verify:

- allocator excludes that combination from new proposals
- exclusion appears in logs and recommendation context

### Test 7: Scorecard gate test

Create a wedge with a strong composite trend but weak proof coverage. Verify:

- gate remains blocked
- blocking reason identifies the weak floor
- no automation or expansion action proceeds on trend score alone

Desired test questions:

- can the system distinguish clicks from conviction?
- can it distinguish conviction from readiness?
- can proof gaps create owned work?
- can doctrine constrain routing without silent failure?
- can a strong trend score still be blocked by a weak floor?

## 19. Feature Flags

Representative flags:

| Flag | Default | Controls |
|---|---|---|
| `growth.enrichment.enabled` | `false` | enrichment pipeline |
| `growth.experiment.enabled` | `false` | experiment allocator |
| `growth.outbound.enabled` | `false` | automated outbound execution |
| `growth.quality.enabled` | `true` | signal quality layer |
| `growth.belief_layer.enabled` | `false` | dual-axis belief inference |
| `growth.doctrine_enforcement.enabled` | `true` | doctrine gating |
| `growth.proof_coverage.enabled` | `false` | proof coverage recomputation |
| `growth.wedge_fitness.enabled` | `false` | scorecard and trend computation |
| `growth.journey_orchestrator.enabled` | `false` | multi-step journey planning |
| `growth.loss_analysis.enabled` | `false` | structured loss analysis |

## 20. Delight Features

- **Why This Worked** — a card on every winning persuasion path showing pain, proof, objection, conviction change, readiness change, and booked outcome
- **Belief Replay** — a view of conviction and readiness over time for one prospect
- **Proof Debt Queue** — rank missing or weak proof by expected revenue impact
- **Doctrine Diff** — show which founder rules blocked recommendations this week and why
- **Pilot Path Hall of Fame** — the top repeatable booked-pilot paths, updated weekly

## 21. Immediate Next Steps

### Week 1

- finalize HVAC wedge config
- define segment and angle taxonomy
- define touchpoint log and routing decision log
- define doctrine seed rules
- define proof coverage starter map

### Week 2

- define scorecard gates
- define signal quality thresholds
- define packet structure
- define proof brief schema

### Week 3

- launch initial page and proof inventory
- instrument all touches
- begin founder-reviewed outbound

### Week 4

- run full-loop simulation
- review first outcomes
- identify first repeatable persuasion path

## 22. Final Summary

The system is a Persuasion OS for repeatable booked-pilot paths.

It is organized as four planes:

- Capture
- Interpret
- Decide
- Govern

Its canonical learning object is `persuasion_path`, not a generic experiment arm or an isolated growth metric.

The growth loop remains the mechanism. The goal is discovering which segment, pain, objection, proof, and outcome patterns can be repeated with enough conviction and buying readiness movement to generate booked pilots.

That is the loop worth automating.

---

## Appendix A: Component Notes

### A.1 Source of truth hierarchy

1. touchpoint log
2. routing decision log
3. derived belief and proof-quality layers
4. scorecards and summaries

### A.2 Doctrine precedence

1. hard doctrine beats automation
2. hard doctrine beats delegate action
3. soft doctrine creates review friction
4. doctrine conflicts are logged, not hidden

### A.3 Proof debt definition

Proof debt is the backlog of missing or weak proof required to move high-value objections from `gap` or `weak` to `covered`.

## Appendix B: Future Analytical Modules

Future analytical expansion lives here so it does not distort the Phase 0-3 core.

These modules are valuable, but they are modules within the four planes, not prerequisites for core wedge proof.

### B.1 Product and aggregate intelligence

- aggregate intelligence: cross-tenant benchmarks and network learning
- product usage correlation: retention and feature-usage insight
- channel mix optimization: budget-level portfolio decisions
- growth simulator: strategic scenario modeling
- strategic briefing: monthly or quarterly synthesis

These modules should remain dormant until the wedge-proof loop has enough trustworthy evidence to justify broader synthesis.

### B.2 Appendix schema notes

`8.25` and `8.26` remain reserved in the main schema section and are described here because they belong to later analytical expansion, not the core wedge-proof loop.

### B.3 Boundary rule

Any field, table, or module justified only by later strategic intelligence should live here until it can prove a Phase 1-3 use case.
