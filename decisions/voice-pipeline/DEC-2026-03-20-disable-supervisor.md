---
id: DEC-2026-03-20-disable-supervisor
domain: voice-pipeline
status: active
---

# Disable supervisor in post-call pipeline

## Context
The LangGraph supervisor node was running on every post-call webhook, consuming excessive memory and causing OOM kills that quarantined all incoming calls.

## Options Considered
- **Option A:** Optimize supervisor memory usage (reduce context window, limit tool calls).
- **Option B:** Disable supervisor entirely and run extraction pipeline directly.
- **Option C:** Move supervisor to a separate, larger instance.

## Decision
Disable supervisor entirely (Option B). Run the extraction pipeline directly in the post-call webhook handler. The supervisor added no value for the extraction-only post-call path — it was orchestration overhead with no multi-step reasoning needed.

## Consequences
- Post-call pipeline is now a simple linear flow: webhook -> fetch full call -> extract -> persist.
- If we later need multi-step reasoning in post-call (e.g., conditional follow-up actions), we'll need to re-introduce orchestration — but scoped to specific use cases, not blanket supervisor.
- Commit: `0a6d490`
