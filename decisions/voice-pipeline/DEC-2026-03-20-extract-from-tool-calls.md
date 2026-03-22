---
id: DEC-2026-03-20-extract-from-tool-calls
domain: voice-pipeline
status: active
---

# Extract structured data from Retell tool call arguments

## Context
Call data (customer name, issue type, appointment details) was being extracted by LLM from free-text transcript. The same data already existed in structured form within Retell's `transcript_with_tool_calls` field as tool call arguments.

## Options Considered
- **Option A:** Continue LLM extraction from transcript text (unreliable, hallucinates).
- **Option B:** Read structured data directly from tool call arguments in the transcript.

## Decision
Option B. Tool call arguments are the authoritative source for structured call data. LLM extraction from free text is a fallback only when tool calls are absent.

## Consequences
- Extraction is now deterministic for calls where the agent used tools (majority of calls).
- Must handle edge case: calls that end before any tool is invoked still need LLM fallback.
- Extraction logic must read `transcript_with_tool_calls`, not just `transcript`.
- Commits: `755e1e3`, `0255571`, `54a9c65`
