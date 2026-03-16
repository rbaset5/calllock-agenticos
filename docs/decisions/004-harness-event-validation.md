# ADR 004: Harness Event Validation

Status: Accepted

## Decision

Inbound harness events use strict typed envelopes:

- `POST /events/process-call` accepts only `name = "harness/process-call"` with a typed `ProcessCallRequest`
- `POST /events/job-complete` accepts only `name = "harness/job-complete"` with a typed `JobCompleteEvent`
- Extra fields are rejected
- `ProcessCallRequest` requires at least one of `transcript` or `problem_description`
- Event endpoints require `HARNESS_EVENT_SECRET` when configured

## Rationale

- This closes the loose-envelope gap between Inngest and FastAPI.
- Invalid or malformed events fail at request validation with `422` rather than being partially processed.
- The contract is now consistent between the TypeScript sender and Python receiver.

## Current Scope

The event contract here covers the harness-side events currently implemented in this repo:

- process-call
- job-complete

Future event types should follow the same envelope pattern.
