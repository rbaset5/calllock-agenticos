# Execution Org Design

**Date:** 2026-03-23
**Status:** Draft
**Author:** Rashid Baset + Codex
**Depends on:** [CallLock Corporate Hierarchy & Agent Roster](2026-03-17-corporate-hierarchy-agent-roster.md), [Truth Plane Design](2026-03-23-truth-plane-design.md), [Governance Plane Design](2026-03-23-governance-plane-design.md), [Detection Plane Design](2026-03-24-detection-plane-design.md)

## Summary

Design the Execution Org for CallLock as the part of the system that does the work: it investigates, responds to detection-triggered issues, proposes changes, produces candidate artifacts, and executes bounded workflows.

The Execution Org must stay separate from both Truth and Governance. Execution workers may propose, but they may not certify. They do not decide whether reality improved, and they do not decide whether risky actions are allowed to proceed.

This spec uses a hybrid model:

- keep departments for identity and reporting
- define actual execution ownership by workflow
- split builder/judge boundaries only where the core surfaces require it now

## Goals

- make execution ownership clear on core workflows
- remove mixed builder/judge responsibility where it matters most
- keep the roster lean outside the highest-risk surfaces
- define dispatch rules by workflow rather than generic department identity
- make every execution worker legible in terms of what it owns and what it cannot do

## Non-Goals

- rewriting the entire company roster in one step
- forcing every department into the same maturity model immediately
- replacing the broader hierarchy document
- turning execution workers into validators or policy owners
- proliferating workers across every function before the first loops are stable

## Recommendation

Use a `targeted execution split`.

That means:

- keep the broad company structure
- split only the highest-risk mixed roles now
- define workflow ownership and dispatch clearly
- leave the rest of the roster lean until more truth/governance loops are real

This is preferable to keeping the current roster unchanged because it leaves the core voice builder/judge problem intact. It is preferable to a full org rewrite because that would produce more conceptual churn than operational value right now.

## Purpose

The Execution Org exists to:

- do the work
- investigate failures
- propose changes
- produce implementation artifacts
- execute bounded workflows

It does not:

- declare its own work correct
- own truth thresholds
- bypass governance
- redefine strategic intent

Its job is:

`bounded execution with clear ownership`

## Current Repo Grounding

The design must be grounded in the current worker set:

- [`eng-ai-voice.yaml`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/knowledge/worker-specs/eng-ai-voice.yaml)
- [`eng-product-qa.yaml`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/knowledge/worker-specs/eng-product-qa.yaml)
- [`eng-app.yaml`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/knowledge/worker-specs/eng-app.yaml)
- [`eng-fullstack.yaml`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/knowledge/worker-specs/eng-fullstack.yaml)
- [`customer-analyst.yaml`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/knowledge/worker-specs/customer-analyst.yaml)
- [`outbound-scout.yaml`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/knowledge/worker-specs/outbound-scout.yaml)

The main org flaw in the current repo is that `eng-ai-voice` still mixes builder and judge responsibilities, while `eng-product-qa` and `eng-app` already function more like validation workers than execution workers.

## Organizational Model

The Execution Org should be:

- `clarity for core surfaces only`
- `workflow-owned`
- `department-aware but not department-driven`

Departments remain useful for:

- reporting structure
- company identity
- management grouping

But execution ownership should be defined by workflow.

## Workflow Ownership Model

The first execution workflows should be:

### 1. Voice Change Workflow

Owned by: `voice-builder`

Scope:

- prompt changes
- extraction logic changes
- taxonomy changes
- routing change proposals
- candidate voice configuration changes

### 2. App Fix Workflow

Owned by: `eng-fullstack`

Scope:

- app-side implementation fixes
- seam-driven UI and transform changes
- customer-facing app bug fixes

### 3. Customer Outcome Analysis Workflow

Owned by: `customer-analyst`

Scope:

- lead routing interpretation
- churn or risk analysis
- post-call analysis and summaries

### 4. Outbound Workflow

Owned by: `outbound-scout`

Scope:

- prospect discovery
- scoring
- probing
- outbound prep

### Detection-Triage Coordination

In Phase 1 and early Phase 2, `eng-product-qa` should temporarily coordinate detection-triggered triage across voice and product surfaces:

- classify the affected surface
- collapse obvious duplicate issue threads where possible
- route narrow investigations to the correct execution owner

This is coordination, not ownership of execution work itself.

## Workflow Ownership Matrix

| Workflow | Execution Owner | Validation Owner | Governance Trigger |
|---|---|---|---|
| Voice change | `voice-builder` | `voice-truth` | truth gate result, approval boundaries, rollout boundary |
| App fix | `eng-fullstack` | `eng-app` for app-only validation; `eng-product-qa` for seam/cross-surface validation; both when the fix spans both | product seam boundary, approval boundaries |
| Customer outcome analysis | `customer-analyst` | founder/program as provisional validator until a dedicated truth loop exists | policy boundaries on customer-facing action or escalation |
| Outbound workflow | `outbound-scout` | founder/program as provisional validator until a dedicated truth loop exists | outbound policy boundaries, customer-facing outreach boundary |

## First Worker Split

The first major execution correction should be:

- deprecate `eng-ai-voice` as the long-term operational role
- replace it with:
  - `voice-builder` in Execution
  - `voice-truth` in Truth

This is the most important builder/judge split in the current repo.

## Functional Placement

These workers should remain outside the Execution Org functionally, even if their department label stays inside engineering:

- `eng-product-qa`
- `eng-app`
- `voice-truth`

They are validation or truth roles, not execution roles.

The one temporary exception is detection-triage coordination: `eng-product-qa` may coordinate the first detection slice operationally without becoming the owner of the resulting execution work.

## Dispatch Rules

Dispatch should follow this rule:

`route by workflow first, then by allowed action, then by required judge`

This means:

- voice prompt, extraction, taxonomy, or routing work → `voice-builder`
- voice detection-triggered investigation → `voice-builder` after detection triage
- app implementation defects → `eng-fullstack`
- app validation or rendering verification → `eng-app`
- seam or cross-surface validation → `eng-product-qa`
- lead/risk interpretation → `customer-analyst`
- outbound prospecting/probing → `outbound-scout`

The dispatch system should not route to “best available engineer” or “generic engineering.”
It should route to the worker that owns that workflow.

For app work specifically:

- app-only validation routes to `eng-app`
- seam or cross-surface validation routes to `eng-product-qa`
- fixes that span both app correctness and seam correctness should be validated by both

## Builder / Judge Boundary

The central execution rule is:

`execution workers may propose, but they may not certify`

### `voice-builder`

Can:

- investigate voice failures
- create candidate prompt or config changes
- rerun extraction and comparisons
- produce a candidate for truth evaluation

Cannot:

- declare pass/block for voice changes
- tune truth thresholds
- modify the locked eval contract mid-run

### `eng-fullstack`

Can:

- fix app and seam-driven implementation issues
- propose app code changes
- update implementation artifacts

Cannot:

- validate its own fixes as production-ready
- bypass app or seam validation

### `customer-analyst`

Can:

- classify outcomes
- flag risk
- prepare summaries and routing recommendations

Cannot:

- take customer-facing action outside policy boundaries
- claim policy compliance or governance approval

### `outbound-scout`

Can:

- discover and rank prospects
- run silent probes
- produce prospect artifacts

Cannot:

- perform customer-facing outreach
- mutate source data
- self-approve outbound action beyond policy limits

## Ownership Model

Use three levels of ownership.

### 1. Workflow Owner

Who executes the work.

Examples:

- `voice-builder`
- `eng-fullstack`
- `customer-analyst`
- `outbound-scout`

### 2. Validation Owner

Who judges whether the work is correct.

Examples:

- `voice-truth` for voice changes
- `eng-app` for app correctness
- `eng-product-qa` for seam and cross-surface validation
- founder/program as the provisional validator for `customer-analyst` and `outbound-scout` until dedicated truth loops exist

### 3. Governance Owner

Who determines whether the action is allowed to continue when boundaries are crossed.

In early CallLock, this is primarily:

- policy gate
- approval requests
- founder judgment on escalations and overrides

## V1 Worker Mapping

| Current Worker | V1 Role | Functional Placement |
|---|---|---|
| `eng-ai-voice` | deprecated transitional role | to be replaced by `voice-builder` + `voice-truth` |
| `voice-builder` | execution worker | Execution |
| `voice-truth` | evaluator / truth worker | Truth |
| `eng-product-qa` | cross-surface validator | Truth |
| `eng-app` | app validator | Truth |
| `eng-fullstack` | implementation worker | Execution |
| `customer-analyst` | analysis worker | Execution |
| `outbound-scout` | outbound execution worker | Execution |

## Approval and Validation Handoff

Execution workers hand off to validation and governance rather than carrying work all the way through themselves.

The intended handoff pattern is:

1. execution worker proposes change
2. validation owner judges correctness
3. governance decides whether the action may continue if boundaries are crossed

This should remain explicit in worker specs, dispatch logic, and any founder-facing control surfaces.

## Generic Worker Policy

Generic fallback workers should be minimized.

Rules:

- do not route work to a generic fallback when a specialized workflow owner exists
- keep generic workers only as temporary scaffolding or migration aids
- do not let generic “engineering” capacity erase workflow ownership clarity

This is especially important for `engineer.yaml`-style abstractions if they remain in the repo.

## What Not To Do

The Execution Org should explicitly avoid:

- keeping `eng-ai-voice` as the long-term operational role
- routing by generic engineering capacity
- letting execution workers tune their own eval thresholds or truth contracts
- using a generic fallback worker when a specialized owner exists
- exploding the roster across every department before core flows are stable
- forcing all departments into the same org maturity at the same time

## Phased Delivery

### Phase 1

- define workflow ownership explicitly
- split `eng-ai-voice` into `voice-builder` and `voice-truth`
- keep `eng-product-qa` and `eng-app` out of Execution functionally
- normalize dispatch rules around workflow ownership
- let `eng-product-qa` coordinate the first detection-triggered triage slice

### Phase 2

- tighten ownership and validation handoffs on app and outbound surfaces
- remove or demote generic fallback workers where specialized ownership exists

### Phase 3

- apply the same execution-ownership model to more workflows as more truth/governance loops become real

## Risks

### Risk: role ambiguity survives under new names

If the repo renames workers without changing dispatch and ownership rules, the org will still be mixed in practice.

### Risk: roster sprawl

If every function is split immediately, the org becomes harder to reason about before the operating loops justify that complexity.

### Risk: department gravity

If dispatch continues to follow department identity rather than workflow ownership, the org chart will look cleaner on paper than it behaves in execution.

## Open Questions for Planning

These are planning questions, not unresolved product-direction questions:

- What is the exact migration path from `eng-ai-voice` to `voice-builder` + `voice-truth` in worker specs and runtime dispatch?
- Which dispatch layer should own the workflow-first routing logic in the current harness?
- How should transitional compatibility be handled for existing references to `eng-ai-voice`?

## Acceptance Criteria

This design is successful if:

- core execution workflows each have a clear owner
- builders and judges are separated on the highest-risk surfaces
- dispatch routes to workflow owners rather than generic department workers
- validation ownership is explicit for every core execution worker
- the org remains lean outside the surfaces that genuinely need sharper separation

## Implementation Boundary

This spec defines the Execution Org: worker split, dispatch rules, builder/judge boundaries, and execution ownership model. It does not define the full truth runner, the full governance runtime, or the entire company hierarchy rewrite. Those should be planned separately and integrated through the execution model defined here.
