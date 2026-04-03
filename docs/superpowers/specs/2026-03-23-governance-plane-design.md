# Governance Plane Design

**Date:** 2026-03-23
**Status:** Draft
**Author:** Rashid Baset + Codex
**Depends on:** [CallLock AgentOS Architecture](calllock-agentos-architecture.md), [Product Guardian Design](2026-03-18-product-guardian-design.md), [Truth Plane Design](2026-03-23-truth-plane-design.md), [Detection Plane Design](2026-03-24-detection-plane-design.md)

## Summary

Design the Governance Plane for CallLock as the enforcement layer that controls risky actions. Governance decides whether the system is allowed to proceed, at what scope, and under what conditions.

This spec defines a shared governance model, but only wires the first real surfaces in v1:

- voice truth / shipping control
- product change control
- existing approval requests
- existing override audit trail

The Governance Plane must remain grounded in the repo’s current machinery:

- approval requests in [`harness/src/harness/approvals.py`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/src/harness/approvals.py)
- policy gate in [`harness/src/harness/nodes/policy_gate.py`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/src/harness/nodes/policy_gate.py)
- guardian/quarantine handling in [`harness/src/harness/nodes/guardian_gate.py`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/src/harness/nodes/guardian_gate.py)
- approval ADR in [`docs/decisions/006-approval-requests.md`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/docs/decisions/006-approval-requests.md)
- override audit trail in [`supabase/migrations/053_guardian_overrides.sql`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/supabase/migrations/053_guardian_overrides.sql)

## Goals

- make governance a real enforcement layer, not just a documentation layer
- standardize how risky actions are allowed, escalated, blocked, or quarantined
- define reusable governance concepts without overbuilding an abstract policy engine
- preserve auditability around approvals, overrides, and quarantines
- reuse existing governance records wherever possible in v1

## Non-Goals

- building a broad enterprise policy framework for every future subsystem
- inventing a second approvals system in v1
- replacing truth with governance
- turning the Governance Plane into a full workflow engine
- wiring every future product and business surface immediately
- turning raw detection events into founder-visible governance spam

## Recommendation

Use a `shared governance model with narrow first wiring`.

That means:

- define reusable governance concepts now
- wire only the first real surfaces in v1
- defer broader company-wide governance rollout until voice/product control is real

This avoids both underdesign and overdesign.

## Purpose

The Governance Plane exists to answer:

`Even if something can be done, is it allowed to happen now, at this scope, with this risk?`

Truth decides whether reality improved.
Governance decides whether the system is allowed to proceed.

Its primary job in v1 is:

`control risky actions`

That means governance must own:

- approval classes
- rollout boundaries
- quarantine behavior
- override rules
- policy boundaries
- auditability

## Core Governance Objects

The Governance Plane should be built around five core objects.

### 1. Policy Decision

The machine-readable result of a gate check.

Canonical v1 outcomes:

- `allow`
- `escalate`
- `block`

This is the immediate answer from policy evaluation.
In v1, current runtime `deny` should be normalized to `block`.

### 2. Approval Request

A durable request for founder or operator judgment when the system cannot auto-continue.

In v1, this reuses the existing `approval_requests` model, which is currently scoped to escalated runs.

### 3. Quarantine Record

A record that something was persisted for audit or debugging, but is not allowed to participate in normal downstream behavior.

Quarantine is distinct from block:

- `block` means do not proceed
- `quarantine` means keep for audit, but hide from normal paths

### 4. Override Record

A durable record of an exceptional founder or operator action that bypassed a normal governance outcome.

In v1, this reuses the existing `guardian_overrides` audit trail.

### 5. Rollout Boundary

A bounded scope limit attached to a governed change or action.

This is what makes governance about blast radius rather than simple yes/no permission.

In v1, the canonical runtime home for `Rollout Boundary` is the governed task/run context. It may later become a first-class candidate-level object, but the first implementation should attach it to run/task state so it composes cleanly with the current approval and policy machinery.

## Governance Outcomes

Governance should standardize around three decision outcomes in v1:

- `allow`
- `escalate`
- `block`

### `allow`

The action may proceed within its current boundary.

### `escalate`

The action may not proceed without explicit human judgment.

### `block`

The action may not proceed.

### `quarantine` handling flag

The output is persisted for audit/debugging but must not enter normal downstream behavior.

In v1, `quarantine` is **not** a fourth decision enum value.
It is a separate handling mode layered on top of the decision result, matching the current guardian model more closely:

- policy/truth decide `allow`, `escalate`, or `block`
- guardian/persistence may additionally mark output as `quarantine: true`

## Approval Classes

Governance should define four approval classes now, even if not all are fully wired in v1.

### Class 1. Policy Escalation

The system cannot auto-allow the action because it crosses a policy boundary.

Examples:

- human-review tier worker action
- risky configuration change
- sensitive mutation outside auto-allowed scope

### Class 2. Truth Escalation

The truth result is `escalate` rather than `pass` or `block`.

Examples:

- borderline canary
- insufficient dataset coverage
- materially contradictory advisory signals

### Class 3. Rollout Expansion

The change is acceptable in a limited scope but needs approval to widen blast radius.

Examples:

- moving from canary to a wider rollout
- raising a rollout boundary from eval-only to canary-only

### Class 4. Exceptional Override

A founder or operator wants to bypass a block or normal limit.

Examples:

- emergency production override
- urgent business exception

## V1 Wired Approval Classes

In v1, wire only:

- `Policy Escalation`
- `Truth Escalation`
- `Exceptional Override`

Rollout Expansion should be defined now but can remain a later wiring step.

## Rollout Boundaries

Every governed change should carry a boundary state in v1.

The initial boundary set should be:

- `local_only`
- `eval_only`
- `canary_only`
- `approved_for_ship`

### `local_only`

Not eligible for live effect.

### `eval_only`

Eligible for locked evaluation but not live canary or production effect.

### `canary_only`

Eligible only for a narrow approved live slice.

### `approved_for_ship`

Eligible for normal production promotion.

This boundary model gives governance a concrete blast-radius control surface without requiring a broad deployment-policy engine.

## Override Policy

Overrides must be treated as exceptional governance actions.

### Rules

- overrides are chat-only in early founder operation
- every override must be logged durably
- every override must cite:
  - actor
  - reason
  - original block or escalation
  - affected scope
  - timestamp
- overrides do not silently become normal policy
- repeated overrides are signals that policy or truth is wrong

### V1 Record Model

In v1, reuse the existing `guardian_overrides` record set for override auditability. Do not introduce a second generic override store yet.

### V1 Override Scope

V1 override support is intentionally narrow:

- read-only projection of existing guardian/Product-Guardian override cases
- no claim of generic cross-surface override coverage yet
- broader override generalization is deferred to a later phase

## Policy Boundaries

Policy boundaries should be defined around actions and surfaces, not around teams.

The first policy boundaries should be:

### 1. Voice Change Boundary

Anything touching:

- prompts
- extraction logic
- routing logic
- voice contracts
- deploy configuration

Default governance:

- must satisfy the voice truth gate
- may require escalation depending on worker approval tier
- may be restricted to canary-only before ship

### 2. Product Seam Boundary

Anything that changes or breaks the extraction → storage → app render chain.

Default governance:

- must satisfy seam validation
- may be quarantined if downstream integrity is broken

### 3. Human-Review Boundary

Actions already marked as human-review in worker specs remain non-auto.

### 4. Override Boundary

An override is allowed only as an exceptional governance action, never as the default mechanism for forward progress.

## V1 Source-of-Truth Reuse

The Governance Plane should reuse the current repo/runtime records in v1.

| Governance Object | V1 Source of Truth | V1 Scope |
|---|---|---|
| `Policy Decision` | Existing policy-gate / guardian-gate outputs | Current governed runs |
| `Approval Request` | Existing `approval_requests` | Escalated-run approvals only |
| `Quarantine Record` | Existing guardian-gate / persisted run state | Quarantined outputs only |
| `Override Record` | Existing `guardian_overrides` | Read-only guardian/Product-Guardian override cases only |
| `Rollout Boundary` | Governed task/run context, projected into approval context on escalation | First wired for voice/product changes only |

This keeps governance thin and grounded in the current operating system rather than inventing a parallel one.

## Relationship to Truth Plane

The Governance Plane is not the Truth Plane.

For voice in v1:

- Truth produces the final `pass / block / escalate` gate verdict
- Governance owns surrounding approval classes, rollout boundaries, quarantine handling, and override behavior

For integration purposes in v1:

- truth `pass` makes the change eligible for governance `allow` within its current rollout boundary
- truth `block` remains a block
- truth `escalate` remains an escalate

Governance does not reinterpret truth to produce a contradictory result.

This means governance does not reinterpret a truth block as a pass.
It governs what happens around that truth result.

## Relationship to Detection Plane

The Governance Plane is not the Detection Plane.

Detection may decide:

- this issue should be investigated
- this issue should stand down behind an existing thread
- this issue is meaningful enough to notify a human

Governance decides:

- whether a resulting action is allowed
- whether a rollout boundary changes
- whether a human approval is required
- whether a quarantined output may enter normal paths

Detection should provide context into Governance, but it should not replace governance outcomes.

## Relationship to Existing Approval System

The existing approval system already models escalated runs as durable approval requests.

That model should remain authoritative in v1.

Governance v1 must not create a second approval queue.
It may later broaden the concept, but the first implementation should remain scoped to the existing `approval_requests` record family.

## Quarantine Semantics

Quarantine should remain a first-class governance handling mode.

Use quarantine when:

- output should be preserved for audit/debugging
- output is not trustworthy enough for normal downstream use
- investigation or replay is still valuable

Do not use quarantine as a synonym for generic failure.

## Auditability

Governance actions must be inspectable after the fact.

That means:

- approvals remain durable
- overrides remain durable
- quarantined outputs remain inspectable
- policy decisions remain attributable to a gate result and context

V1 auditability should prefer existing stores and logs rather than a new governance database.

## What Not To Do

The Governance Plane should explicitly avoid:

- building a giant abstract policy engine before the first governed surfaces are real
- creating a second approval system instead of reusing `approval_requests`
- collapsing truth escalation and policy escalation into an undifferentiated queue
- treating quarantine as just failure logging
- making overrides easy or invisible
- wiring broad company-wide governance before voice/product control is real

## Phased Delivery

### Phase 1

- define governance objects and outcome language
- reuse existing approval and override records
- wire governance around voice truth and product seam control
- formalize rollout boundaries for first governed changes

### Phase 2

- improve rollout expansion handling
- broaden governance visibility in founder surfaces
- make approval class presentation more explicit in the founder workflow

### Phase 3

- reuse the same governance model for additional truth loops and adjacent surfaces

## Risks

### Risk: abstraction before enforcement

If governance becomes too abstract before it controls real surfaces, it will turn into documentation rather than an operating system.

### Risk: duplicate queues

If the system creates a second approval or override path, operators will lose trust in which queue is authoritative.

### Risk: override normalization

If overrides become common, governance will silently erode and policy boundaries will stop meaning anything.

## Open Questions for Planning

- Which founder-facing governance surfaces should come from chat only versus be visible in the cockpit?

## Acceptance Criteria

This design is successful if:

- risky actions can be classified into a small shared governance model
- voice/product changes are controlled through real governance boundaries
- approval, quarantine, and override behavior are auditable
- the system does not invent a second governance subsystem in v1
- governance remains distinct from truth while still integrating cleanly with it

## Implementation Boundary

This spec defines CallLock’s Governance Plane: approval classes, rollout boundaries, quarantine semantics, override policy, and first policy boundaries. It does not define the full founder UI, the full truth runner implementation, or a broad enterprise policy engine. Those should be planned separately and integrated through the governance model defined here.
