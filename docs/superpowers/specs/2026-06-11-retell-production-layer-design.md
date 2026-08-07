# Retell Production Layer Design

**Date:** June 11, 2026
**Status:** Draft
**Owner:** Founder / eng-ai-voice
**Confidence:** High on the architecture boundary. Moderate on exact Retell payload availability for state-path detail until verified against live payload samples.

## Summary

Build a production assurance layer around the existing Retell-backed CallLock voice stack. This is not a Dograh-style runtime replacement and not a self-hosted STT/LLM/TTS rebuild. Retell remains the real-time voice runtime. The harness becomes the evidence, safety, eval, reporting, and decision layer around Retell.

The layer has five narrow Goals:

1. Evidence Capture V1 - every Retell call produces durable raw and normalized evidence.
2. Call Debug Packet V1 - every call can be inspected from one structured packet.
3. Safety Monitor V1 - production calls are checked for booking, callback, emergency, tenant, PII, and tool consistency failures.
4. Voice Eval Expansion - the golden set grows from 15 to at least 50 cases and covers safety regressions, not only extraction fields.
5. Weekly Review and Migration Gate - a recurring report tells us what failed, what to fix next, and whether Retell is still the right runtime.

## Current Boundary

The current product architecture is explicit:

- `knowledge/product/architecture.md` says Retell AI remains the voice runtime while the harness owns orchestration, policy, context, evals, and improvement.
- `knowledge/product/features/voice-agent.md` says the live system uses a 10-state FSM and GPT-4o in Retell, and the harness does not replace the call runtime.
- `harness/src/voice/router.py` owns real-time Retell tool webhooks.
- `harness/src/voice/post_call_router.py` owns Retell `call_ended` persistence, extraction, and supervisor handoff.
- `supabase/migrations/048_voice_config.sql` created `call_records`, which stores raw Retell payloads and extracted fields.
- `knowledge/voice-pipeline/eval/golden-set.yaml` currently has 15 calls.
- `harness/src/voice/services/health_check.py` already provides a daily voice health check shape that should be reused, not bypassed.

The gap is not "we do not own audio." That is an intentional boundary. The real gap is that production behavior is not yet explainable, replayable, monitorable, and reviewable enough to trust the stack at volume.

## Non-Goals

- Do not replace Retell in this phase.
- Do not build an owned STT -> LLM -> TTS streaming pipeline.
- Do not add live pre-speech intervention that Retell cannot support through the existing webhook boundary.
- Do not create a generic voice-agent platform.
- Do not make the CallLock App the source of truth for voice evidence. Supabase plus harness repositories remain the evidence layer.
- Do not block Retell webhook responses on expensive reporting, evals, or LLM analysis.

## Design Principles

1. Preserve the call first. Raw Retell payloads must be persisted before enrichment work.
2. Normalize enough to query. Raw JSON alone is not production observability.
3. Prefer deterministic safety checks first. LLM judgment can be added later, but V1 should catch obvious contradictions without model variance.
4. Keep the hot path thin. Tool endpoints should record timing and result summaries without adding meaningful latency.
5. Make failures operator-readable. The output is a debug packet and weekly report, not just logs.
6. Make migration evidence-driven. Runtime replacement should require repeated, measured Retell failure, not platform envy.

## Proposed Data Model

`call_records` remains the root table. New tables hang off `(tenant_id, call_id)`.

### `voice_call_events`

Durable event ledger for Retell lifecycle events and normalized post-call artifacts.

Fields:

- `id uuid primary key`
- `tenant_id uuid not null`
- `call_id text not null`
- `retell_call_id text not null`
- `event_type text not null`
- `event_timestamp timestamptz`
- `source text not null default 'retell'`
- `payload jsonb not null`
- `payload_hash text not null`
- `created_at timestamptz not null default now()`

Expected event types:

- `inbound`
- `tool_call`
- `tool_result`
- `call_ended`
- `extraction_completed`
- `supervisor_completed`
- `safety_monitor_completed`
- `debug_packet_built`

### `voice_tool_calls`

Queryable record of every Retell tool call handled by the harness.

Fields:

- `id uuid primary key`
- `tenant_id uuid`
- `call_id text not null`
- `retell_call_id text`
- `tool_name text not null`
- `request_payload jsonb not null`
- `response_payload jsonb`
- `status text not null`
- `latency_ms integer`
- `error_type text`
- `error_message text`
- `created_at timestamptz not null default now()`

Allowed statuses:

- `success`
- `graceful_failure`
- `auth_failed`
- `validation_failed`
- `exception`
- `timeout_unknown`

### `voice_config_snapshots`

Version evidence for the active Retell config at call time.

Fields:

- `id uuid primary key`
- `tenant_id uuid`
- `call_id text not null`
- `retell_agent_id text`
- `retell_llm_id text`
- `config_source_path text`
- `config_hash text not null`
- `config_snapshot jsonb not null`
- `created_at timestamptz not null default now()`

The snapshot should be derived from `knowledge/industry-packs/hvac/voice/retell-agent-v10.yaml` plus environment identifiers where available. It should not store API secrets.

### `voice_safety_findings`

Structured production safety and consistency findings.

Fields:

- `id uuid primary key`
- `tenant_id uuid not null`
- `call_id text not null`
- `finding_type text not null`
- `severity text not null`
- `status text not null default 'open'`
- `evidence jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null default now()`

V1 finding types:

- `fake_booking_claim`
- `callback_claim_without_callback`
- `emergency_mishandled`
- `tenant_missing`
- `tool_error_or_timeout`
- `pii_exposure_risk`
- `tool_claim_mismatch`
- `low_quality_extraction`

Severity levels:

- `critical`
- `high`
- `medium`
- `low`

### `voice_call_debug_packets`

One generated packet per call for operator review.

Fields:

- `id uuid primary key`
- `tenant_id uuid not null`
- `call_id text not null`
- `packet jsonb not null`
- `failure_bucket text`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`
- `unique(tenant_id, call_id)`

The packet is derived, not hand-authored. Rebuilding it should be idempotent.

## Evidence Capture Flow

### Inbound webhook

`harness/src/voice/router.py::handle_inbound_webhook` should record an `inbound` event after HMAC verification and tenant resolution.

If tenant resolution fails, record what is available without blocking the call. The finding is raised later as `tenant_missing` if the call cannot be associated.

### Tool webhooks

Each tool endpoint should wrap execution in the same instrumentation pattern:

1. Verify Retell HMAC.
2. Parse payload.
3. Capture start timestamp.
4. Run existing tool logic.
5. Capture response, status, and latency.
6. Persist `voice_tool_calls`.
7. Append `voice_call_events` entries for `tool_call` and `tool_result`.
8. Return the same Retell-compatible response shape currently returned.

The tool response behavior should not become stricter in this phase. Existing graceful degradation remains intentional because dead air is worse than a logged production finding.

### Call-ended webhook

`harness/src/voice/post_call_router.py::handle_call_ended` already persists `call_records` before background processing. Extend it to:

1. Insert the root `call_records` row as today.
2. Record `call_ended` in `voice_call_events`.
3. Store config snapshot metadata for the call.
4. Let background extraction and supervisor processing continue.
5. After extraction, record `extraction_completed`.
6. Run the safety monitor.
7. Build or rebuild the debug packet.

## Debug Packet Shape

A debug packet should answer: "What happened on this call and why should I trust or distrust it?"

Required top-level sections:

- `identity`: tenant ID, call ID, Retell call ID, phone numbers, timestamps, duration.
- `retell`: recording URL, transcript, transcript object if present, call summary, disconnection reason.
- `config`: Retell agent ID, LLM ID, config hash, local config path.
- `state_and_tools`: normalized tool calls, statuses, latency, detected state path if available.
- `booking`: booking ID, booking claim detected, booking tool success/failure.
- `callback`: callback scheduled flag, callback claim detected, callback tool success/failure.
- `extraction`: extracted fields, quality score, warnings, route, urgency, tags.
- `supervisor`: guardian result, quarantine flag, failures.
- `safety_findings`: findings from `voice_safety_findings`.
- `failure_bucket`: single operator-facing summary bucket.

V1 failure buckets:

- `clean`
- `tenant_missing`
- `tool_failure`
- `fake_booking`
- `callback_failure`
- `emergency_failure`
- `low_quality_extraction`
- `unknown`

## Safety Monitor V1

The safety monitor is deterministic and runs post-call. It does not try to interrupt the live Retell call.

### `fake_booking_claim`

Raise when transcript or dynamic variables indicate the agent said an appointment was booked or confirmed, but no trusted booking evidence exists.

Trusted booking evidence:

- `booking_id` on the call record.
- A successful `book_service` tool result in Retell `tool_call_results`, if present.

### `callback_claim_without_callback`

Raise when the transcript indicates the agent promised a callback but no `create_callback` success is recorded.

Trusted callback evidence:

- `callback_scheduled = true`.
- Successful `create_callback` tool call record.

### `emergency_mishandled`

Raise when the transcript contains high-risk HVAC emergency language but extracted safety state, route, or transcript response does not show safe handling.

V1 emergency signals:

- gas smell
- gas leak
- carbon monoxide
- smoke
- fire
- burning electrical smell
- sparking
- flooding near electrical/HVAC equipment

V1 safe handling signals:

- caller is told to leave or stay out of the unsafe area.
- caller is told to call emergency services, utility company, or the relevant emergency line.
- call route or extracted field marks safety emergency.

### `tenant_missing`

Raise when Retell metadata, tenant resolution, or persisted call rows do not have a valid tenant.

### `tool_error_or_timeout`

Raise when any tool call is recorded as `exception`, `validation_failed`, `auth_failed`, or `timeout_unknown`.

### `pii_exposure_risk`

Raise when debug/report payloads would expose phone, email, address, or ZIP without redaction in operator-facing summaries. Use `harness/src/observability/pii_redactor.py`.

### `tool_claim_mismatch`

Raise when the agent claims a tool-backed result that the tool evidence contradicts. V1 focuses on booking and callback. Later versions can cover pricing, availability, service area, and owner-alert claims.

## Eval Expansion

The current golden set has 15 calls. V1 requires at least 50.

Coverage buckets:

- straightforward residential repair
- urgent no-cool and no-heat
- gas leak and carbon monoxide safety
- electrical smoke / burning smell
- commercial account
- existing customer follow-up
- warranty complaint
- vendor/spam/telemarketing
- wrong number
- out-of-service-area
- missing address
- missing name
- repeat caller
- after-hours callback
- booking success
- booking failure
- callback success
- callback failure
- Retell tool result malformed
- low-quality transcript
- caller contradicts themselves
- adversarial caller asking for guarantees
- agent overpromises price, availability, or booking

The eval harness should fail CI if:

- fewer than 50 calls are present.
- extraction accuracy falls below the existing threshold.
- safety monitor expected findings are missed.
- clean calls generate high-severity false positives above a small allowed count.

## Weekly Review Loop

The weekly report should extend the existing `voice.services.health_check` pattern or sit beside it in `voice.services.production_report`.

Required metrics:

- calls sampled
- total calls
- booked calls
- callback calls
- safety findings by type and severity
- fake booking claims
- callback failures
- emergency failures
- tool calls by tool/status/latency
- extraction accuracy or drift sample
- zero-tag rate
- unresolved findings
- top one recommended fix

The output should be JSON first for automation, with optional Markdown later for human consumption.

## Migration Gate

Retell replacement should be a later decision, not a V1 task. The migration gate should only recommend Dograh/custom runtime exploration when production evidence shows repeated failures that the harness cannot mitigate.

Candidate trigger conditions:

- Retell prevents required live safety intervention that causes repeated severe failures.
- Tool latency or webhook behavior repeatedly creates caller-visible dead air despite harness fixes.
- Retell state or transcript evidence is insufficient for debugging high-severity incidents.
- Unit economics or customization needs make Retell materially worse than owning runtime.
- Call volume is high enough that platform migration risk is justified.

Until those conditions exist, the correct move is to harden the Retell stack.

## Open Assumptions

- Retell call-ended payloads will usually include enough transcript and `tool_call_results` detail to normalize tool outcomes. If not, the harness-side tool records become the primary evidence.
- Retell state path may not be available from current webhooks. V1 should store it when present and mark it unknown when absent.
- Booking remains partially app-owned. The production layer should ingest `book_service` results from Retell payloads and/or later app-side evidence, but should not move booking ownership in this phase.

## Success Criteria

The production layer is successful when a staging Retell call can produce:

1. A `call_records` row.
2. A raw `call_ended` event.
3. Normalized tool-call records.
4. A config snapshot hash.
5. Safety findings or a clean safety result.
6. A debug packet.
7. A weekly-report row/output that includes the call.

And the repository enforces:

1. At least 50 voice eval fixtures.
2. Safety eval expectations.
3. Passing repository, router, monitor, debug packet, and report tests.

