# Founder Control Surface Design

**Date:** 2026-03-23
**Status:** Draft
**Author:** Rashid Baset + Codex
**Depends on:** [CallLock AgentOS Architecture](calllock-agentos-architecture.md), [Product Guardian Design](2026-03-18-product-guardian-design.md), [Detection Plane Design](2026-03-24-detection-plane-design.md)

## Summary

Design a founder operating surface for CallLock that is optimized for judgment, not activity tracking. The founder should operate the company primarily through chat, with a compact web cockpit used for inspecting exceptions, reviewing evidence, and making decisions that cross governance boundaries.

This spec covers only the founder control surface. It does not define the full truth-plane runtime, eval runner implementation, or worker-graph rewiring. It assumes those systems exist or are being built separately and focuses on how the founder sees and acts on their outputs.

The founder surface should also reflect filtered detection posture, not just truth and governance outputs. It should help the founder understand when a real issue thread is active without turning into an alert wall.

## Goals

- Make the founder's default operating mode `chat-first`
- Create a compact web cockpit that is `exception-first`
- Reduce founder time spent reconstructing reality from raw activity
- Present only the system objects that require judgment
- Keep the UI thin over canonical repo/runtime objects instead of inventing a second source of truth
- Show filtered issue posture without exposing raw detector noise

## Non-Goals

- Building a broad internal admin dashboard
- Replacing Discord/Hermes as the primary founder control path
- Creating a workflow builder or visual orchestration tool
- Exposing full worker-spec editing in the browser
- Designing the entire office-dashboard or 3D visualization layer

## Recommendation

Use a two-layer founder surface:

1. **Primary layer: chat**
   Discord/Hermes is the daily operating interface for intake, questions, quick approvals, dispatch, and context capture.

2. **Secondary layer: web cockpit**
   A compact founder cockpit is used for exception review, truth inspection, approvals, blocked-run diagnosis, and recent decisions.

This is preferable to a web-first approach because founder work is primarily language and judgment, not broad control-panel interaction. It is preferable to a chat-only approach because evidence inspection and exception triage need a persistent visual surface.

## User Model

The founder is a solo operator who needs to answer five questions quickly:

- What changed?
- What broke?
- What needs my judgment?
- What is blocked?
- What improved reality?

The surface should optimize for those questions in under a minute, not for completeness of operational telemetry.

## Operating Model

### Chat-first

Chat remains the primary interface for:

- new problem intake
- quick status queries
- dispatching work
- approvals and denials
- adding priorities and constraints
- capturing decisions, errors, and knowledge updates

### Web cockpit

The web cockpit is used when the founder needs:

- a compact briefing
- inspection of truth-loop status
- approval context with evidence
- blocked and escalated run review
- recent decision and error visibility

The cockpit should not duplicate chat. It should hold the evidence and state that make founder judgment faster and more reliable.

## Information Architecture

The cockpit starts with five views only:

1. **Home / Briefing**
   The default founder landing page. It combines the briefing summary with the highest-signal exception blocks and is the single home route in v1.

2. **Truth**
   Status of active truth loops, starting with voice truth and later expanding to app truth, outbound truth, and compliance truth.

3. **Approvals**
   Existing escalated-run approval requests that need founder judgment in v1. This is not yet a generic governance queue.

4. **Runs**
   Active, blocked, quarantined, and escalated work items with links to evidence and outputs.

5. **Decisions**
   Recent durable decisions, overrides, and newly surfaced error patterns.

No additional first-class views should be added in v1.

## Home / Briefing Screen

The `Home / Briefing` screen is a dense operating page built around six blocks:

### 1. Briefing

A short summary card that shows:

- top change since yesterday
- top regression
- top blocked item
- top active issue thread when detection has found a meaningful production problem
- recommended founder action

### 2. Truth Status

A compact status board for:

- voice
- app
- outbound
- compliance

Each row shows:

- current state: `pass`, `block`, `escalate`, or `degraded`
- last evaluation time
- one-line reason

Phase 1 behavior:

- `voice` is active and shown normally
- `app`, `outbound`, and `compliance` are shown with a display-only label: `not active yet`
- these non-voice loops are visible in `Home / Briefing` to preserve the full truth-stack model, but their dedicated truth detail pages are deferred until later phases

### 3. Approvals Queue

Each approval item shows:

- title
- affected surface
- risk level
- age
- recommended action

### 4. Blocked / Escalated Runs

This section only shows exception-state work that needs inspection:

- blocked by eval
- quarantined
- failed verification
- escalated for founder judgment
- detection-triggered investigations that survived triage

### 5. Recent Decisions / Errors

This section surfaces:

- new decisions
- updated decisions
- error patterns that crossed recurrence thresholds
- founder overrides

### 6. Active Priority

A single pinned company priority for the current horizon. This anchors the rest of the screen and prevents the cockpit from becoming unprioritized noise.

In Phase 1, the canonical source is [`AGENT.md`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/AGENT.md). If adjacent strategy documents exist, they may inform founder edits, but the cockpit reads a single active priority from `AGENT.md`.

## V1 Route Set

The v1 cockpit ships exactly five routes:

1. `Home / Briefing`
2. `Truth`
3. `Approvals`
4. `Runs`
5. `Decisions`

There is no separate `Home` versus `Briefing` distinction in v1. They are the same page.

## Interaction Model

The founder should be able to take four primary actions from the control surface:

- `Approve`
- `Deny`
- `Escalate / defer`
- `Set priority / add constraint`

These are the only actions that need to be first-class in v1.

For v1, `Set priority / add constraint` is chat-only. The cockpit displays the active priority and current constraints, but does not edit them directly.

### Override Policy

Founder overrides are **not executable from the cockpit in v1**.

- Overrides remain chat-only in Discord/Hermes
- The cockpit renders overrides as read-only historical objects sourced from `guardian_overrides`
- Override objects must remain visible in `Decisions` and any relevant run or approval detail views

This keeps the cockpit focused on normal approvals and evidence review while reserving exceptional override actions for the higher-friction chat path.

The cockpit should not begin with:

- Kanban-style task management
- drag-and-drop orchestration
- broad CRUD for workers
- custom automation builders
- bulk operational tooling

Those would push the founder into managing activity rather than making decisions.

## Object Model

The founder UI should render existing operating-system objects, not invent new truth. The minimum object set is:

### `BriefingItem`

- `id`
- `summary`
- `severity`
- `source`
- `recommended_action`
- `linked_artifacts`
- `created_at`

In Phase 1, `BriefingItem` is assembled server-side from existing stores at read time:

- pending `approval_requests`
- current-day `agent_reports`
- exception-state `jobs`
- high-signal `incidents`
- latest `decisions/` records
- latest `errors/` records

No new durable aggregation layer is introduced for briefing generation in v1.

### `TruthStatus`

- `loop_name`
- `state`
- `baseline_version`
- `candidate_version`
- `failed_metrics`
- `last_evaluated_at`
- `artifact_refs`

### `Approval`

- `id`
- `title`
- `affected_surface`
- `requested_action`
- `reason`
- `risk_level`
- `blast_radius`
- `evidence_refs`
- `recommended_action`
- `created_at`
- `expires_at`

### `Override`

- `id`
- `title`
- `scope`
- `reason`
- `linked_run_id`
- `linked_approval_id`
- `created_by`
- `created_at`
- `artifact_refs`

Overrides are first-class governance objects, not approval outcomes and not ordinary decisions. In v1 they are rendered read-only in the cockpit and executed only through chat.

### `Run`

- `id`
- `worker_id`
- `task_type`
- `state`
- `started_at`
- `blocked_reason`
- `output_refs`
- `linked_issue_or_pr`

### `DecisionRecord`

- `id`
- `title`
- `scope`
- `status`
- `created_at`
- `supersedes`
- `superseded_by`

### `ErrorPattern`

- `slug`
- `severity`
- `recurrence_count`
- `last_seen_at`
- `promotion_candidate`

### `Priority`

- `title`
- `horizon`
- `constraints`
- `owner`
- `expires_at`

## Phase 1 Object-to-Source Matrix

Phase 1 reuses existing repo/runtime records. The cockpit projects them into a founder-facing read model but does not introduce a new durable aggregation or governance subsystem.

| UI Object | Phase 1 Source of Truth | Phase 1 Rule |
|---|---|---|
| `BriefingItem` | Derived projection from `approval_requests`, `agent_reports`, `jobs`, `incidents`, `decisions/`, and `errors/` | Read-model only, no new durable store |
| `TruthStatus` | `agent_reports` for active truth loops | Voice active; app/outbound/compliance shown as `not active yet` |
| `Approval` | Existing `approval_requests` | Limited to escalated-run approvals in v1 |
| `Override` | Existing `guardian_overrides` | Read-only projection only in v1 |
| `Run` | Existing `jobs` / run-state records | `Runs` route is exception-state runs only in v1 |
| `DecisionRecord` | `decisions/` markdown records | Repo remains canonical |
| `ErrorPattern` | `errors/` markdown records | Repo remains canonical |
| `Priority` | Founder-set repo-backed program context | UI reflects canonical strategy context, not a UI-owned store |

## State Rules

The control surface must reflect the following operating rules:

- A blocked truth result is a fact, not an invitation to reinterpret success.
- A founder override is exceptional and should be rendered as an explicit override object, not as a normal approval.
- Approvals are boundary-crossing objects, not a generic task queue.
- In v1, approvals are limited to existing escalated-run `approval_requests`; the cockpit does not expand them into a generic governance queue.
- The home screen is driven by exceptions and durable learnings, not worker activity volume.

## Initial Truth Ordering

The cockpit should assume this truth order:

1. **Voice truth**
2. **App truth**
3. **Business / outbound truth**
4. **Compliance truth**

Voice truth should be visually primary in the founder experience until the later truth loops are real and stable.

## UX Principles

- **Exception-first:** show what needs judgment, not everything that happened
- **Truth-first:** lead with pass/block/escalate, not activity metrics
- **Evidence-linked:** every meaningful object links to the artifact behind it
- **Low-noise:** avoid ornamental dashboards and redundant status surfaces
- **Thin UI:** the browser reads from the system of record; it does not become a second hidden operating system

## Deferred Work

The following are explicitly deferred:

- worker directory / org-chart UI
- deep analytics dashboards
- browser-based worker-spec editing
- workflow builders
- complex command centers
- office-dashboard integration as the main control surface
- broad multi-tenant admin controls

These may become useful later, but they are not required for the first effective founder operating surface.

## Phased Delivery

### Phase 1

- chat remains primary
- `Home / Briefing` route
- `Approvals` route
- `Truth` route for voice only
- `Runs` route with exception-state runs only
- `Decisions` route with recent decisions, errors, and overrides
- filtered detection posture via issue-thread-driven briefing items and runs

### Phase 2

- app truth and outbound truth views
- richer run inspection pages
- better artifact drill-down
- clearer issue-thread and noisy-detector visibility

### Phase 3

- compliance truth integration
- trend summaries across truth loops
- more structured founder packet generation

## Risks

### Risk: dashboard sprawl

If the cockpit grows into a general operations dashboard too early, it will increase founder load instead of reducing it.

### Risk: duplicated truth

If the browser stores or computes status independently from the canonical runtime and repo objects, the founder surface will drift and become untrustworthy.

### Risk: activity bias

If worker activity is more visible than truth and approvals, the founder will be pulled toward throughput theater.

## Detail Presentation

In v1, object detail inspection should use right-side drawers from list and card surfaces rather than separate sub-routes or modal-heavy flows. This keeps navigation shallow and preserves context while the founder is reviewing exceptions.

## Open Questions for Planning

- Which existing HTTP/API reads should back the server-side briefing projection in phase 1?

## Acceptance Criteria

This design is successful if the founder can:

- understand the current company state from one page in under a minute
- identify the highest-priority exception immediately
- approve or deny a boundary-crossing action with linked evidence
- inspect the latest truth status without reading raw logs
- see recent durable decisions and error patterns without searching the repo manually

## Implementation Boundary

This spec is intentionally narrow. It defines the founder control surface information architecture, object model, and interaction principles. It does not define the voice eval runtime, the gate implementation, or the full internal operating system backend. Those should be planned separately and integrated into this surface through canonical objects and evidence links.
