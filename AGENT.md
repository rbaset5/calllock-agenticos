# CallLock AgentOS

This repo uses the repo itself as durable operating memory. Before proposing or executing changes, check:

- `decisions/_index.md` for prior trade-offs and active decisions.
- `errors/_index.md` for recurring error patterns.
- `knowledge/_moc.md` for curated domain context.

## Phase-One Hermes CEO Gateway

- Founder interface is Discord-first.
- Telegram is deferred beyond phase one.
- Persistent Hermes memory is disabled for phase one.
- Repo files remain the authoritative long-term memory.
- Direct repo writes through the gateway are allowed only when `CALLLOCK_GATEWAY_WRITE_ENABLED=1`.

## Repo Memory Routing

- New trade-off or conclusion: write to `decisions/`.
- Recurring bug or failure pattern: write to `errors/`.
- Durable domain update: write to `knowledge/`.

## Runtime Notes

- The CEO tool contract lives in `harness/src/harness/tool_registry.py`.
- The MCP server entrypoint is `python -m harness.mcp_server`.
- Bootstrap local Hermes config with `scripts/bootstrap-hermes-gateway.py`.
