---
id: ERR-2026-03-20-supervisor-oom
domain: voice-pipeline
occurrences: 3
status: pattern-extracted
extracted_to: decisions/voice-pipeline/DEC-2026-03-20-disable-supervisor.md
---

# Supervisor OOM on post-call webhook

## Symptoms
LangGraph supervisor node exhausts memory on every post-call webhook invocation. Container killed by OOM, all subsequent calls quarantined until restart.

## Root Cause
Supervisor loads full conversation context + tool definitions for multi-step reasoning, but post-call extraction is a single-step linear operation. The memory overhead is unnecessary.

## Fix
Disabled supervisor entirely in post-call pipeline. Extraction runs directly.
Commit: `0a6d490`

## Pattern Notes
Extracted to decision: supervisor is disabled for post-call. If multi-step post-call reasoning is needed later, scope it to specific use cases — don't blanket-wrap extraction in a supervisor.
