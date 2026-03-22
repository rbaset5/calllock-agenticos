---
id: ERR-2026-03-21-empty-tool-call-data
domain: voice-pipeline
occurrences: 2
status: resolved
---

# Extraction reads empty tool-call data

## Symptoms
Extraction pipeline produced empty/null fields for customer name, issue type, etc., even though the voice agent successfully collected this data during the call.

## Root Cause
Three layered issues found across multiple fixes:
1. Extraction logic read `transcript` instead of `transcript_with_tool_calls` (missed tool args entirely).
2. When tool-call data was empty strings, the overwrite logic skipped them instead of treating them as "no data."
3. Enriched payload wasn't being persisted back to Supabase after extraction.

## Fix
- Read tool args from `transcript_with_tool_calls` field (commit: `0255571`)
- Overwrite empty tool-call data properly (commit: `54a9c65`)
- Persist enriched payload after extraction (commit: `54a9c65`)

## Pattern Notes
Retell's data model has multiple transcript representations. Always use `transcript_with_tool_calls` for structured extraction. Plain `transcript` is for display/logging only.
