# Errors Index

Error pattern log for CallLock AgentOS. Check here before debugging.

**Escalation protocol:**
1. First occurrence → create error file, `occurrences: 1`, `status: logged`
2. Same pattern recurs → bump `occurrences`, add date/details
3. Third occurrence → extract rule into `decisions/` or update `knowledge/`, mark `status: pattern-extracted`

## Voice Pipeline

- [Supervisor OOM on post-call](voice-pipeline/ERR-2026-03-20-supervisor-oom.md) — LangGraph supervisor exhausts memory on every call
- [Extraction reads empty tool-call data](voice-pipeline/ERR-2026-03-21-empty-tool-call-data.md) — tool_call args present but extraction logic skipped them
- [Retell webhook signature mismatch](voice-pipeline/ERR-2026-03-19-webhook-sig-mismatch.md) — Retell's actual signature format differs from docs

## Product

(none yet)

## Architecture

(none yet)
