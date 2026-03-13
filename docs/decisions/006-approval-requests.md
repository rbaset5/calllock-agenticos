# ADR 006: Approval Requests as First-Class Control-Plane State

Status: Accepted

## Decision

Escalations in this repository create durable approval requests rather than only writing audit logs.

Current behavior:

- verification or policy escalations create `approval_requests` with `pending` status
- operators can inspect pending requests via `GET /approvals`
- operators can resolve them via `POST /approvals/{approval_id}` with `approved`, `rejected`, or `cancelled`
- approved requests attempt bounded continuation automatically using the stored resumable state
- approval decisions are also written to the audit log

## Rationale

- Audit logs explain what happened; approval requests model what still needs operator action.
- This separates passive history from an active work queue for the Cockpit.

## Current Limits

- Continuation currently supports the escalated run shapes implemented in this repo; it is not yet a generic workflow engine.
- Approval scope is currently tied to escalated runs, not a broader generic approval engine.
