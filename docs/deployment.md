# Deployment Runbook

## Services

- `calllock-harness`: Python FastAPI + LangGraph runtime
- `calllock-inngest`: Node Inngest function server
- `calllock-redis`: Redis cache

## Live Topology

- Primary deploy target: Hetzner via Coolify
- Live harness URL: `http://ls5e6qqlb3wl1jesk21ds2zb.89.167.116.18.sslip.io`
- Discord assistant transport: Discord Gateway bot running inside `calllock-harness`
- Assistant model selection: `SALES_ASSISTANT_MODEL` env var, default `gpt-4.1-mini`

Render remains available as a legacy/fallback deploy path, but the current live assistant path is Hetzner + Coolify.

## Required Environment

### Harness

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `HARNESS_EVENT_SECRET`
- `OPENAI_API_KEY`
- `DISCORD_BOT_TOKEN`
- `DISCORD_BOT_ENABLED=true`
- `SALES_ASSISTANT_MODEL` optional, defaults to `gpt-4.1-mini`
- `LANGSMITH_API_KEY` if tracing is enabled

If you route model traffic through a proxy, you can still set `LITELLM_BASE_URL`, but the live Discord assistant no longer depends on a separate LiteLLM service.

### Inngest

- `HARNESS_BASE_URL`
- `HARNESS_EVENT_SECRET`
- `INNGEST_EVENT_KEY`
- `INNGEST_SIGNING_KEY`
- `INNGEST_SERVE_PATH` if not using `/api/inngest`

## Order of Operations

1. Apply the SQL in `supabase/migrations/` and `supabase/seed.sql`.
   - `supabase/seed.sql` provides realistic app data (tenant-alpha, `demo-call-*`).
   - Deterministic CI/guardian fixtures remain migration-based (`055_test_tenant_seed.sql`).
   - Optional validation queries live in `supabase/seed-checks.sql`.
2. Deploy `calllock-redis` if the target environment does not already provide Redis.
3. Deploy `calllock-harness` with Supabase, OpenAI, Discord, and shared-secret configuration.
4. Confirm `calllock-harness /health` reports `status: ok`, `litellm.configured: true`, and `event_secret.configured: true`.
5. Deploy `calllock-inngest`.
6. Confirm `calllock-inngest /health` reports the expected configuration state.
7. Send a test `harness/process-call` event and verify a `jobs` row is written in Supabase.
8. Send a test `POST /discord/ask` request with `HARNESS_EVENT_SECRET` auth and verify the assistant returns a real answer.
9. Run `scripts/check-live-stack.py` with the deployed service URLs and Supabase credentials.

## Post-Deploy Checks

- `GET /health` on the harness returns `status: ok`
- `GET /health` on the Inngest service returns `status: ok`
- `GET /api/inngest` returns the Inngest SDK metadata payload
- A test event flows through `calllock-inngest` to the harness and persists to `jobs`
- `POST /discord/ask` returns a natural-language answer
- Hetzner/Coolify logs show the Discord bot connecting to Gateway

## Automated Check

Use `scripts/check-live-stack.py` with:

- `HARNESS_BASE_URL`
- `INNGEST_BASE_URL` if deployed
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `HARNESS_EVENT_SECRET` if the harness event endpoint is protected
