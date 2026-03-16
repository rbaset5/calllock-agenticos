# ADR 003: PII Redaction Approach

Status: Accepted

## Decision

This repository uses a deterministic regex-and-hash redaction strategy for traces and customer-content reuse:

- Phones, emails, street-style addresses, and ZIP codes are replaced with explicit redaction tokens.
- Identifiers such as `tenant_id`, `call_id`, `run_id`, and `job_id` are hashed before trace submission.
- Redaction is recursive across nested dict/list payloads.
- Trace payloads are tagged with `data_classification = "pii-redacted"`.

## Rationale

- The current repo needs a fast, local, predictable redaction path that can run synchronously before tracing and content reuse.
- Hashing identifiers preserves correlation without exposing raw IDs.
- Recursive traversal avoids the shallow-redaction failure mode where nested payloads leak identifiers.

## Tradeoff

- This is narrower than a full NER-based privacy layer and can miss free-form names or unusual address formats.
- The approach is intentionally simple and testable for the current stage of the system.

## Follow-up

- Revisit whether a hybrid allowlist + NER pass is necessary before broad production rollout with real customer transcripts.
