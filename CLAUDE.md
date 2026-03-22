# CallLock AgentOS — Claude Instructions

Read and follow `AGENT.md` in this repo root. It is the single source of truth for all project conventions, navigation, and domain context.

## Claude-Specific Overrides

- Before proposing changes to voice pipeline, product, or architecture, check `decisions/_index.md`.
- Before debugging, check `errors/_index.md` for known patterns.
- Skills and memory pointers are managed via Claude Code's built-in memory system — they complement, not replace, the repo-based context in `AGENT.md`, `decisions/`, and `errors/`.
- When updating agent instructions, update `AGENT.md` (not this file) unless the change is Claude-specific.
