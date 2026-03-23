---
id: DEC-2026-03-22-discord-gateway
domain: architecture
status: active
---

# Discord as bidirectional context interface via hermes-agent gateway

## Context
The agent context system (decisions/, errors/, knowledge/) needs an input surface for the decomposition loop. The founder holds context in his head and explains it fresh each session. Moving to Discord as a bidirectional interface lets him post problems/ideas and have the CEO agent decompose them into repo context files automatically.

## Options Considered
- **Option A: Read-only Discord mirror** — Agents post summaries via existing webhook projector. Input happens through agent sessions (Claude Code, Codex, Gemini CLI).
- **Option B: Custom Discord.js bot** — Build a bot in inngest/ that listens to Discord events and calls Python harness tools via HTTP. Full control, more maintenance.
- **Option C: hermes-agent gateway** — Use NousResearch's hermes-agent gateway for bidirectional Discord (and Telegram) with MCP tool calling, persistent memory, cross-platform continuity. CEO tools + context tools exposed as MCP endpoints.

## Decision
Option C. The hermes-agent gateway provides the Discord bot layer with built-in conversation management, cross-platform continuity (Discord primary, Telegram mobile fallback), and MCP tool integration. This replaces Telegram as the primary control surface while keeping it as a fallback.

The gateway calls 16 MCP tools: 10 original CEO tools + 6 new context tools (decompose_problem, check_decisions, create_decision, check_errors, log_error, update_knowledge).

## Consequences
- hermes-agent becomes a runtime dependency for the CEO agent gateway.
- Discord replaces Telegram as the primary founder control surface.
- The existing webhook-based discord-projector.ts continues for one-way agent observability (state changes, verifications, health checks).
- The gateway handles bidirectional conversation; the projector handles event streaming. No overlap.
- Hermes gateway memory is ephemeral conversation context; the repo (decisions/, errors/, knowledge/) is the authoritative long-term memory.
- Hermes skill auto-creation is disabled — skill promotion remains human-gated.
