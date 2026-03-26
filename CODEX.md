# CallLock AgentOS — Codex Instructions

Read and follow `AGENT.md` in this repo root. It contains all project conventions, navigation instructions, and domain context.

## Codex-Specific Notes

- When delegated implementation tasks, check `decisions/_index.md` first to avoid relitigating settled decisions.
- Before debugging, check `errors/_index.md` for known patterns.
- For knowledge navigation, start at `knowledge/_moc.md` and follow wiki-links.
- Runtime split: Python (`harness/`) for orchestration, TypeScript (`inngest/`, `scripts/`) for events/validation only.
