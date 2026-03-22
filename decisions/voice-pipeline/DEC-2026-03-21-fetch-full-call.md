---
id: DEC-2026-03-21-fetch-full-call
domain: voice-pipeline
status: active
---

# Fetch full call from Retell API before extraction

## Context
The post-call webhook payload from Retell is incomplete — it doesn't always include the full `transcript_with_tool_calls` or all metadata fields needed for extraction.

## Options Considered
- **Option A:** Trust the webhook payload and extract from whatever is present.
- **Option B:** Always fetch the full call object from Retell's GET /call/{call_id} API before extraction.

## Decision
Option B. Always fetch the full call from Retell API. The webhook is a notification, not a data source.

## Consequences
- Adds one API call per post-call webhook (acceptable latency).
- Extraction always operates on complete data.
- If Retell API is down, extraction fails — acceptable because we'd rather fail than extract from partial data.
- Commit: `fcb84ec`
