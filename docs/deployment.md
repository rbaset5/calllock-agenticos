# Deployment Runbook

Primary target: Coolify on Hetzner for the harness Docker deployment. `render.yaml` remains in the repo for historical reference and fallback, but the harness should be treated as Hetzner-first.

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
- `RETELL_API_KEY`
- `VOICE_CREDENTIAL_KEY`
- `DISCORD_BOT_ENABLED=true` if you want the Discord assistant to connect on boot
- `DISCORD_BOT_TOKEN` if the Discord assistant is enabled
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
   - `supabase/seed.sql` provides realistic app data (tenant-alpha, `demo-call-*`).
   - Deterministic CI/guardian fixtures remain migration-based (`055_test_tenant_seed.sql`).
   - Optional validation queries live in `supabase/seed-checks.sql`.
2. Deploy `calllock-litellm` and `calllock-redis`.
3. Deploy `calllock-harness` from the repo root using [harness/Dockerfile](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/rabat/harness/Dockerfile).
   - In Coolify, the build context should be the repo root so `knowledge/` is copied into the image.
   - Health check path: `/health`
   - Exposed container port: `8000`
4. Configure the harness env vars listed above in Coolify.
5. Confirm `calllock-harness /health` reports the expected configuration state.
6. Set `HARNESS_BASE_URL` anywhere else that calls the harness, including Inngest and the dialer.
7. Deploy `calllock-inngest`.
8. Confirm `calllock-inngest /health` reports the expected configuration state.
9. Send a test `harness/process-call` event and verify a `jobs` row is written in Supabase.
10. Run `scripts/check-live-stack.py` with the deployed service URLs and Supabase credentials.

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

Use `scripts/smoke-test.sh` with:

- `HARNESS_URL` or `HARNESS_BASE_URL`
- `EXPECTED_TOOL_HOSTS` if Retell tool URLs legitimately span more than one host
- `RETELL_API_KEY`
