# Detection Plane Design

**Date:** 2026-03-24
**Status:** Draft
**Author:** Rashid Baset + Codex
**Depends on:** [Truth Plane Design](2026-03-23-truth-plane-design.md), [Governance Plane Design](2026-03-23-governance-plane-design.md), [Execution Org Design](2026-03-23-execution-org-design.md), [Founder Control Surface Design](2026-03-23-founder-control-surface-design.md)

## Summary

Design a Detection Plane for CallLock as the production-aware layer that notices likely problems quickly, scopes them into narrow operational threads, and only wakes humans up when the issue appears meaningful.

The Detection Plane is not the Truth Plane. It does not decide whether reality improved. It does not ship changes. It does not replace governance. Its job is to:

- watch production signals
- trigger narrow investigations
- cluster and suppress duplicate alerts
- distinguish probable signal from probable noise
- feed real issues into Execution, Truth, and Governance cleanly

The design is motivated by a simple lesson:

`detect everything, notify selectively`

## Goals

- add a production-aware detection layer without collapsing Truth into observability
- move issue discovery from founder/manual noticing toward event-driven triage
- reduce alert noise and duplicate escalation
- trigger narrow execution workflows with high-quality issue context
- keep human notifications high-signal

## Non-Goals

- replacing the Truth Plane with monitors
- turning every production anomaly into a founder notification
- building a giant generic observability platform
- auto-merging or auto-shipping fixes based on monitor output
- making Detection the source of constitutional truth

## Recommendation

Add a `Detection Plane` as a distinct operating layer between Program and Execution in practical runtime flow:

1. `Program`
2. `Detection`
3. `Execution`
4. `Truth`
5. `Governance`

This is preferable to keeping the current design unchanged because scheduled evaluation alone is too coarse to notice narrow production failures quickly. It is preferable to making monitors the center of the architecture because CallLock still needs an independent Truth Plane and hard Governance boundaries.

## Purpose

The Detection Plane exists to answer:

`What deserves investigation now, and what should stay quiet?`

It does not answer:

- `Did the candidate change improve reality?`
- `Is this allowed to ship?`
- `What is the company optimizing for?`

Those belong to Truth, Governance, and Program respectively.

## Core Design Rule

The most important rule in this design is:

`A fired monitor is an investigation trigger, not a truth verdict.`

That means:

- a monitor firing does not mean the system is definitely wrong
- a monitor firing does not mean a candidate is blocked
- a monitor firing does not mean the founder must be notified

It means:

- gather issue context
- assess likely scope
- check for duplicates
- decide whether to investigate, suppress, or escalate

## Current Repo Grounding

The Detection Plane should build on existing repo/runtime surfaces rather than inventing a parallel stack:

- alerting machinery in [`harness/src/harness/alerts/`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/src/harness/alerts)
- incidents in [`harness/src/harness/incidents.py`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/src/harness/incidents.py)
- incident routing and classification in [`harness/src/harness/incident_routing.py`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/src/harness/incident_routing.py) and [`harness/src/harness/incident_classification.py`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/src/harness/incident_classification.py)
- alert lifecycle and thresholds in [`harness/src/harness/alerts/lifecycle.py`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/src/harness/alerts/lifecycle.py) and [`harness/src/harness/alerts/thresholds.py`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/src/harness/alerts/thresholds.py)
- existing founder-facing status surfaces in [`harness/src/harness/cockpit.py`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/src/harness/cockpit.py)

This spec does not require a wholesale observability rewrite. It formalizes how those kinds of signals should interact with the agentic operating system.

## Detection Plane Objects

The Detection Plane should be built around five core objects.

### 1. Signal Source

A concrete production signal that can produce a detection event.

Examples:

- alert threshold breach
- repeated extraction failure pattern
- warning-rate spike
- app sync failure cluster
- latency anomaly

### 2. Detection Event

A normalized representation of a signal worth triaging.

Fields should include:

- `source`
- `surface`
- `signal_type`
- `severity`
- `observed_at`
- `tenant_id`
- `dedupe_key`
- `raw_context`

### 3. Triage Assessment

The machine-readable assessment of a detection event.

Outcomes:

- `investigate`
- `suppress`
- `stand_down`
- `escalate`

This is the main working object of the Detection Plane.

### 4. Issue Thread

A durable thread that groups repeated detections pointing to the same underlying problem.

This is how the system avoids flooding itself or the founder with duplicates.

In Phase 1 and early Phase 2, the first implementation of `Issue Thread` should reuse the existing incident model rather than introduce a new durable store immediately.

### 5. Notification Decision

A separate decision about whether a human should be notified.

This is intentionally separate from the triage assessment.
Something can be real enough to investigate without being important enough to wake a human.

Canonical notification outcomes should be:

- `internal_only`
- `operator_notify`
- `founder_notify`
- `silent_stand_down`

## Detection Plane Outcomes

Detection should standardize around four outcomes:

- `investigate`
- `suppress`
- `stand_down`
- `escalate`

### `investigate`

The signal looks meaningful enough to trigger a narrow execution workflow.

### `suppress`

The signal appears to be noise, low-value, or below the current notification threshold.

### `stand_down`

The signal may be real, but a matching issue is already open or an in-flight fix already exists.

### `escalate`

The signal is significant enough that human review should happen now, even before a deeper execution pass completes.

`escalate` does not automatically imply `founder_notify`.
The Notification Decision determines who gets notified.

## Phase 1 Source-of-Truth Reuse

The Detection Plane should reuse current repo/runtime records in its first implementation.

| Detection Object | Phase 1 / Early Phase 2 Source of Truth | Notes |
|---|---|---|
| `Signal Source` | Existing alerts, health signals, incident-adjacent runtime events | No new source registry required initially |
| `Detection Event` | Existing `alerts` plus normalized alert/incident payloads in runtime | Detection events are first projected, not yet stored in a new dedicated table |
| `Triage Assessment` | Runtime decision payload attached to alert/incident handling | Can be persisted into existing alert or incident notes/payload as needed |
| `Issue Thread` | Existing `incidents` | Reuse incidents as the first durable dedupe/thread object |
| `Notification Decision` | Runtime decision plus existing alert/incident notification behavior | No new notification table in the first slice |

This keeps Detection grounded in the current operating system and avoids inventing a second incident model prematurely.

## Monitor Classes

Phase 1 and Phase 2 should use a small, sharp set of monitor classes.

### Voice Detection

- extraction failure spike
- empty structured output spike
- urgency classification anomaly
- route drift anomaly
- safety-emergency mismatch anomaly
- callback or booking mismatch spike
- warning-rate spike
- missing required downstream field spike

### Seam / App Detection

- app sync failure spike
- required-field persistence mismatch
- render-data mismatch on required app surfaces
- stale downstream data on critical records

### Operational Detection

- repeated approval escalations on the same issue type
- repeated quarantines from the same failure mode
- recurring retries around one worker/surface pair

## Triage Rules

The Detection Plane should use these triage rules:

### Rule 1: Detect everything, notify selectively

It is acceptable to generate many internal detection events.
It is not acceptable to turn all of them into founder-facing noise.

### Rule 2: Narrow the mission

Every detection that survives triage should become a narrow investigation target, not a vague “look into production” assignment.

### Rule 3: Collapse duplicates

Repeated detections with the same underlying issue should update an existing issue thread instead of creating a new founder-visible escalation.

### Rule 4: Prefer suppression over human spam

If the system is uncertain whether something is meaningful enough to notify a human, it should usually investigate first and notify later only if the signal strengthens.

## Notification Policy

Detection should standardize a separate notification policy from triage.

### `internal_only`

The signal should remain inside the system:

- execution can investigate
- issue thread may update
- founder is not notified

### `operator_notify`

The signal should notify an operator or assignee, but not the founder immediately.

Use when:

- the issue appears real
- the blast radius is limited
- the system needs human awareness but not founder judgment

### `founder_notify`

The signal should reach the founder now.

Use when:

- the issue is high severity
- the issue crosses an approval/truth/governance boundary
- the signal indicates a broad customer or trust risk

### `silent_stand_down`

The signal should not notify anyone because:

- a matching issue thread is already open
- a fix is already in flight
- the event adds no new useful information

## Flow

The recommended Detection Plane flow is:

### 1. Signal observed

A monitor or runtime signal produces a detection event.

### 2. Normalize

The event is normalized into a common detection shape:

- surface
- tenant
- severity
- dedupe key
- issue context

### 3. Triage

The Detection Plane decides:

- `investigate`
- `suppress`
- `stand_down`
- `escalate`

### 4. If investigate

Trigger a narrow execution workflow with the detection context attached.

Examples:

- `voice-investigate`
- `seam-investigate`
- `app-investigate`

### 5. Execution investigates

The assigned worker:

- reproduces the issue where possible
- scopes likely cause
- prepares evidence
- proposes a candidate fix or issue record

### 6. Truth and Governance interact only if needed

If the execution path produces a candidate fix or a governed decision:

- Truth evaluates the candidate where applicable
- Governance decides rollout, approval, quarantine, or override behavior

### 7. Founder visibility

The founder sees:

- meaningful escalations
- active issue threads
- repeated noisy detector surfaces

not raw detector firehose activity.

In Phase 1 / early Phase 2:

- `internal_only` and `silent_stand_down` stay out of founder-facing surfaces
- `operator_notify` may appear indirectly through runs/incidents but should not dominate the founder briefing
- `founder_notify` is the only class that should reliably surface into `Home / Briefing`

## Relationship to Execution

Detection should usually trigger Execution, not replace it.

Recommended Phase 1 / early Phase 2 ownership:

- `eng-product-qa` temporarily owns cross-surface detection triage coordination
- `voice-builder` owns narrow voice investigation and candidate preparation
- `eng-fullstack` or app-specific execution owners handle app-side fixes

Later, if detection volume becomes meaningful, a dedicated `ops-detection` or `incident-triage` role can be split out.

## Relationship to Truth

Truth remains constitutionally separate.

Detection may say:

`this looks wrong enough to investigate`

Truth may say:

`this candidate passes`
`this candidate blocks`
`this candidate escalates`

Detection must never be treated as a substitute for the locked truth loop.

## Relationship to Governance

Detection does not own rollout, approvals, or overrides.

However, it should interact with Governance by:

- attaching issue-thread and signal context to escalations
- helping suppress duplicate approval-generating investigations
- surfacing noisy monitor classes that need threshold or policy adjustment

## Relationship to Founder Surface

The founder surface should not show raw monitor spam.

Instead, Detection should influence:

### Home / Briefing

- top active issue thread
- top noisy detector surface
- recommended triage action

### Runs

- detection-triggered investigations
- escalated issue threads

### Decisions

- monitor policy changes
- threshold adjustments
- suppression-pattern decisions

Detection should be visible as filtered operational posture, not as an alert wall.

## Phase Plan

### Phase 1

Detection remains implicit and lightweight.

- use existing alerts/incidents
- no new full Detection Plane runtime yet
- keep founder visibility exception-first

### Phase 2

Add the first explicit Detection Plane slice for voice.

- normalize voice production signals
- triage into `investigate / suppress / stand_down / escalate`
- attach dedupe keys and issue threads
- reduce founder-visible noise

### Phase 3

Extend the same pattern to seam/app surfaces.

### Phase 4

Broaden to operational/business surfaces if needed.

## Risks

### Risk: monitor-as-truth confusion

If operators or founders start treating monitor fires as constitutional truth, the system will become noisy and intellectually sloppy.

### Risk: detection sprawl

If too many low-value monitor classes are added too early, the Detection Plane will create activity without clarity.

### Risk: founder spam

If the notification policy is weak, the founder surface will regress into an incident feed instead of a judgment surface.

### Risk: duplicate work

If repeated signals do not collapse into issue threads, workers will repeatedly investigate the same underlying failure.

## Acceptance Criteria

This design is successful if:

- production signals can trigger narrow investigations automatically
- repeated detections can stand down behind a known issue thread
- humans are notified selectively rather than constantly
- Detection remains clearly distinct from Truth and Governance
- the founder surface becomes more timely without becoming noisier

## Implementation Boundary

This spec defines the Detection Plane conceptually: its purpose, objects, outcomes, triage rules, and relation to the rest of the operating system. It does not define the full implementation plan, the precise monitor schema, or the runtime wiring for every signal source. Those should be planned separately once this layer is accepted.
