# Deployment Runbook

## Services

- `calllock-harness`: Python FastAPI + LangGraph runtime
- `calllock-inngest`: Node Inngest function server
- `calllock-litellm`: LiteLLM proxy
- `calllock-redis`: Redis cache

## Required Environment

### Harness

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `HARNESS_EVENT_SECRET`
- `LITELLM_BASE_URL`
- `LANGSMITH_API_KEY` if tracing is enabled

### Inngest

- `HARNESS_BASE_URL`
- `HARNESS_EVENT_SECRET`
- `INNGEST_EVENT_KEY`
- `INNGEST_SIGNING_KEY`
- `INNGEST_SERVE_PATH` if not using `/api/inngest`

## Order of Operations

1. Apply the SQL in `supabase/migrations/` and `supabase/seed.sql`.
2. Deploy `calllock-litellm` and `calllock-redis`.
3. Deploy `calllock-harness` with Supabase and shared-secret configuration.
4. Confirm `calllock-harness /health` reports the expected configuration state.
5. Deploy `calllock-inngest`.
6. Confirm `calllock-inngest /health` reports the expected configuration state.
7. Send a test `harness/process-call` event and verify a `jobs` row is written in Supabase.
8. Run `scripts/check-live-stack.py` with the deployed service URLs and Supabase credentials.

## Post-Deploy Checks

- `GET /health` on the harness returns `status: ok`
- `GET /health` on the Inngest service returns `status: ok`
- `GET /api/inngest` returns the Inngest SDK metadata payload
- A test event flows through `calllock-inngest` to the harness and persists to `jobs`

## Automated Check

Use `scripts/check-live-stack.py` with:

- `HARNESS_BASE_URL`
- `INNGEST_BASE_URL` if deployed
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `HARNESS_EVENT_SECRET` if the harness event endpoint is protected

## Hermes CEO Gateway

Phase one is local/dev-first. VPS deployment and always-on hosting are explicitly deferred beyond this phase.

Required local environment:

- `DISCORD_BOT_TOKEN`
- `DISCORD_ALLOWED_USERS`
- `CALLLOCK_GATEWAY_WRITE_ENABLED=1` only when you intentionally want mutating gateway tools enabled

Bootstrap flow:

1. Run `python scripts/bootstrap-hermes-gateway.py --check` to detect drift.
2. Run `python scripts/bootstrap-hermes-gateway.py --write` to sync the repo-owned prompt/config assets into `~/.hermes/` and install the MCP server entry.
3. Verify the server manually with `cd harness && PYTHONPATH=src ./.venv/bin/python -m harness.mcp_server`.
4. Start Hermes with `hermes gateway`.

Phase-one defaults:

- Discord enabled and primary
- Telegram disabled
- Persistent Hermes memory disabled
- Cross-platform continuity disabled
- Cron blocks remain template-only and opt-in for later always-on deployment
