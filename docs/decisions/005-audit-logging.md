# ADR 005: Audit Logging for Control-Plane Actions

Status: Accepted

## Decision

Administrative and recovery actions in this repository are persisted to an `audit_logs` store with:

- `action_type`
- `actor_id`
- `reason`
- `tenant_id` when scoped
- `target_type` and `target_id`
- structured payload metadata

Current audit coverage includes:

- tenant onboarding start/completion/failure
- kill switch updates
- artifact lifecycle transitions
- eval runs
- improvement experiments
- recovery replays

## Rationale

- Control-plane actions must be visible and reviewable without reconstructing state from jobs, traces, and artifacts.
- Audit logging gives the Cockpit and operators one durable history for administrative changes.

## Current Limits

- Approval workflow state is not yet modeled separately from the audit log.
- Cross-tenant Cockpit admin access still depends on future auth/RLS role work.
