# Founder MVP Design

**Date:** 2026-03-24
**Status:** Draft
**Author:** Rashid Baset + Codex
**Depends on:** [Founder Control Surface Design](2026-03-23-founder-control-surface-design.md), [Truth Plane Design](2026-03-23-truth-plane-design.md), [Governance Plane Design](2026-03-23-governance-plane-design.md), [Detection Plane Design](2026-03-24-detection-plane-design.md)

## Summary

Define the smallest founder-usable MVP for CallLock's operating system.

This is not the full AgentOS cockpit. It is the narrowest product slice that allows the founder to run the day through one operating surface instead of reconstructing reality from scattered logs, alerts, and conversations.

The Founder MVP must let the founder do five things quickly:

- see what changed
- see what broke
- see whether voice is currently trustworthy
- see what needs judgment
- act on the highest-signal issue or approval

## Goals

- give the founder one real operating surface for daily review
- make `voice truth` visible in a compact, decision-usable form
- make `detection posture` visible without raw alert spam
- make `approvals` actionable and concrete
- separate `active issues` from `blocked work`
- keep the UI thin over real backend read models

## Non-Goals

- shipping the full multi-surface AgentOS cockpit
- representing every designed subsystem in the UI
- polishing the 3D office into the MVP itself
- exposing full experiment management, full run history, or full decision archaeology
- making the web UI the primary interaction surface instead of chat

## Recommendation

Ship a `thin founder operating console` with four primary panels:

1. `Briefing`
2. `Voice Truth`
3. `Issue Posture`
4. `Approvals`

and one secondary panel:

5. `Blocked / Escalated Work`

This is preferable to a broader MVP because founder value comes from fast judgment, not from broad internal visibility. It is preferable to a backend-only MVP because the founder still needs one place where the system becomes operationally usable.

## Founder Morning Loop

The Founder MVP is successful if the founder can do this in under five minutes:

1. open the operating surface
2. see whether voice truth is currently healthy
3. see whether any meaningful issue thread is active
4. see whether anything needs approval
5. decide the top priority for the day

If the product cannot support this loop, it is not founder MVP.

## MVP Route Set

The Founder MVP should ship exactly three routes:

1. `Home`
2. `Approvals`
3. `Blocked Work`

`Home` contains:

- `Briefing`
- `Voice Truth`
- `Issue Posture`

This is intentionally narrower than the broader founder control surface spec. The goal is daily usability, not structural completeness.

## MVP Read Models

The MVP must be built on explicit read models rather than loosely assembled UI cards.

### 1. `FounderBriefing`

Purpose:
- summarize the current operating situation in one compact object

Fields:
- `generated_at`
- `top_change`
- `top_regression`
- `top_issue_thread`
- `top_blocked_work`
- `top_pending_approval`
- `recommended_action`
- `active_priority`

Source of truth:
- `approval_requests`
- `incidents`
- exception-state `jobs`
- latest truth `agent_reports`
- `AGENT.md` active priority projection

Rules:
- only one item per category
- founder-visible issue threads only
- no raw monitor events
- no more than one recommended action

### 2. `VoiceTruthSummary`

Purpose:
- give the founder one compact answer to “is voice currently safe enough to trust?”

Fields:
- `state`
  one of: `pass | block | escalate | not_active`
- `top_reason`
- `last_evaluated_at`
- `failed_metric_count`
- `baseline_version`
- `candidate_version`
- `artifact_refs`

Source of truth:
- truth `agent_reports`
- eval result artifacts

Rules:
- this is a summary object, not an eval explorer
- one row only in MVP
- non-voice truth loops are deferred from MVP

### 3. `DetectionIssuePosture`

Purpose:
- show the founder which production issue threads are meaningful right now

Fields:
- `counts.open_threads`
- `counts.founder_visible_threads`
- `active_threads[]`

Each active thread includes:
- `incident_id`
- `incident_key`
- `alert_type`
- `incident_domain`
- `incident_category`
- `severity`
- `workflow_status`
- `notification_outcome`

Source of truth:
- existing `incidents`
- linked `alerts`
- detection notification metadata

Rules:
- only `operator_notify` and `founder_notify` threads appear
- `internal_only` and `silent_stand_down` do not appear
- issue posture is about live issue threads, not proposed changes

### 4. `ApprovalInboxItem`

Purpose:
- give the founder a compact and actionable approval queue

Fields:
- `id`
- `title`
- `affected_surface`
- `risk_level`
- `reason`
- `requested_action`
- `age`
- `evidence_summary`
- `recommended_action`

Source of truth:
- existing `approval_requests` only

MVP approval classes:
- escalated-run approvals already represented in `approval_requests`
- truth escalations that project into `approval_requests`
- governance escalations that project into `approval_requests`

Rules:
- this is not a generic governance inbox
- no speculative future approval classes in MVP

### 5. `BlockedWorkItem`

Purpose:
- show the founder which proposed changes or runs need judgment or inspection

Fields:
- `id`
- `worker_id`
- `task_type`
- `state`
- `blocked_reason`
- `recommended_next_step`
- `artifact_refs`

Source of truth:
- exception-state `jobs`

Rules:
- this panel is for blocked or escalated work items
- it is distinct from issue posture
- detection-triggered investigations only appear here when they are active work items, not just issue threads

## Screen Architecture

### `Home`

The `Home` route contains exactly four sections:

1. `Briefing`
2. `Voice Truth`
3. `Issue Posture`
4. `Active Priority`

The page must answer:

- what changed?
- what broke?
- is voice trustworthy?
- what needs attention first?

### `Approvals`

The `Approvals` route is a list/detail workflow over `ApprovalInboxItem`.

Primary actions:
- `approve`
- `deny`
- `defer`

Rules:
- defer may map to the current backend compromise if necessary, but the UI should present it as `defer`, not `cancelled`
- only real approval requests appear here

### `Blocked Work`

The `Blocked Work` route contains exception-state `BlockedWorkItem`s.

Primary questions:
- what is blocked?
- why is it blocked?
- what should happen next?

This route must not merge with issue posture.

## Information Separation

The founder MVP must keep these concepts separate:

### `Issue Posture`

- live problem threads in production
- sourced from incidents + alerts
- asks: `what is wrong in reality right now?`

### `Blocked Work`

- proposed changes or active runs that cannot continue
- sourced from jobs / run state
- asks: `what work is stuck or needs judgment right now?`

### `Approvals`

- explicit boundary-crossing decisions
- sourced from approval requests
- asks: `what must I decide right now?`

These are related, but not the same thing. The MVP must preserve that distinction.

## Visual Shell Constraint

The `office-dashboard` 3D office shell is **optional presentation**, not part of the MVP acceptance criteria.

The MVP may render:

- inside the existing office shell
- or as simple overlays/cards within it

But acceptance is based on the operating loop, not on the scene.

The 3D office must not consume work needed for:

- `Briefing`
- `Voice Truth`
- `Issue Posture`
- `Approvals`
- `Blocked Work`

## Backend Scope Required for MVP

The backend must provide these stable reads:

- `FounderBriefing`
- `VoiceTruthSummary`
- `DetectionIssuePosture`
- `ApprovalInboxItem[]`
- `BlockedWorkItem[]`

The frontend should not reconstruct these ad hoc from raw records if a backend projection can provide them cleanly.

## Success Criteria

The Founder MVP is complete when:

- the founder can run the morning loop in under five minutes
- `VoiceTruthSummary` gives one compact status answer
- `Issue Posture` contains no raw detector spam
- `Approvals` contains only real actionable approval objects
- `Blocked Work` is clearly distinct from issue posture
- the MVP is usable even if the 3D office presentation is minimal

## Deferred From Founder MVP

- full `Truth` multi-loop page
- full `Runs` explorer
- full `Decisions` explorer
- improvement-lab UI
- app truth UI
- outbound truth UI
- rich trend analytics
- rich override authoring in web
- broad office-dashboard visual polish

## Build Order

1. backend read models
2. approvals route
3. home route with briefing, voice truth, and issue posture
4. blocked work route
5. optional office-dashboard shell integration and polish

This order is mandatory because founder value comes from the read models and their decision surfaces, not from the shell.
