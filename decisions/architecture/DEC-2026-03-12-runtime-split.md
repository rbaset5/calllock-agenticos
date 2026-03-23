---
id: DEC-2026-03-12-runtime-split
domain: architecture
status: active
---

# Python/TypeScript runtime split

## Context
The monorepo needs both orchestration (LLM calls, context assembly, multi-step reasoning) and event-driven functions (webhooks, fan-out, scheduled tasks).

## Options Considered
- **Option A:** All Python — use Celery or similar for event-driven work.
- **Option B:** All TypeScript — use LangChain.js for orchestration.
- **Option C:** Split — Python for orchestration (LangGraph), TypeScript for event-driven (Inngest).

## Decision
Option C. Python harness for orchestration, context assembly, policy gate, verification, and persistence. TypeScript only where it interfaces with Inngest or repository validation/extraction.

## Consequences
- Two runtimes to maintain, but each plays to its strengths.
- LangGraph ecosystem (Python) is more mature for agentic orchestration.
- Inngest ecosystem (TypeScript) is purpose-built for event-driven serverless functions.
- Cross-runtime communication happens via Supabase (shared database) and Inngest events.
