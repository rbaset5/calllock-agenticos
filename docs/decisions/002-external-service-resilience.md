# ADR 002: External Service Resilience

Status: Accepted

Scope: the services directly exercised by this repository today.

## Decision

- Supabase REST calls use bounded retry with small linear backoff for transient network and 5xx errors.
- If harness persistence still fails after retries, the run does not crash silently. A recovery journal entry is written locally under `.context/recovery/` and the response is marked `persistence_status: degraded`.
- Inngest dispatch failures do not abort job creation. The job remains visible with `dispatch.dispatched = false` and a `recovery_path`.
- LangSmith tracing is degradable. Failed or unavailable trace submission falls back to local JSONL traces under `.context/traces/`.

## Rationale

- This preserves operator visibility and replayability without pretending partial failure did not happen.
- The recovery journal gives the Cockpit and API a source of truth for manual or automated replay.
- Bounded retry covers transient outages without turning every failure into a long-running hang.

## Out of Scope

- Retell AI fallback behavior
- Cal.com fallback behavior
- Twilio fallback behavior

Those services are not implemented in this repo yet and need separate decisions when their runtime paths exist.
