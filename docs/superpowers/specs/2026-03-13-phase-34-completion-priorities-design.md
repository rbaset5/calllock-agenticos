# Phase 3-4 Completion Priorities

## Overview

Phase 3 is backend-complete for the control-plane surface in this repo. Phase 4 foundation is complete but not fully end-to-end — the Founder Cockpit UI lives outside this repo, and some operational items depend on production data or future integrations.

This spec defines the prioritized remaining work to close documentation gaps, build an observable metrics surface, and explicitly scope deferred items.

## Approach

Docs-first, then metrics API. Documentation removes architectural ambiguity before any code ships. The metrics surface then makes the remaining alert-threshold work measurable instead of opinion-based.

### Execution Order

1. Write Express V2 scaling ADR
2. Finalize retrieval-engine ADR
3. Build metrics write model (Supabase table + harness emitter)
4. Build metrics read API (FastAPI endpoint on harness server)
5. Update TODOS.md to reflect closures and narrowed scope

## Section 1: Express V2 Scaling ADR

**File:** `docs/decisions/002-express-v2-scaling.md`
**Status:** Accepted

**Decision:** Express V2 remains single-instance on Render. Scaling triggers are documented for when this changes.

**Rationale:**
- Current load: 1 contractor × 3 trades = low tens of calls/day
- At 10 tenants × 3 trades, Express V2 handles webhook ingress and API routes — still within single-instance capacity for a Node.js server
- The harness is a separate service, so Express V2 only does webhook parsing + Inngest event emission — stateless and lightweight

**Scaling triggers — revisit when, over a sustained window, any of these hold:**
- Webhook p95 latency > 2s
- CPU > 80%
- Memory pressure or restarts appear
- Webhook backlog or 5xx rate rises materially

**When triggered:** Run multiple stateless instances behind the platform load balancer, preserving statelessness and idempotent webhook handling.

**Critical caveat:** Scaling Express V2 is only useful if the bottleneck is actually ingress. If Inngest, the harness, or downstream services are the choke point, adding Express instances will not help.

**Impact on TODOS.md:** Closes P3 "Define Express V2 horizontal scaling story."

## Section 2: Retrieval Engine ADR Finalization

**File:** `docs/decisions/001-retrieval-engine.md`
**Status:** Proposed → Accepted

**Decision:** Accept the current file-backed retrieval approach with a deferred benchmark upgrade path.

**Current approach:** File-backed retrieval via markdown/YAML traversal, wiki-link resolution, and context assembly prioritization.

**Why accepted now:** Current knowledge volume is small enough that a heavier retrieval layer is not justified.

**Upgrade trigger — revisit when:**
- Measured retrieval p95 > 500ms
- Relevance is observably poor
- Context assembly starts dropping important nodes under budget pressure

**Future option:** Evaluate QMD (Query-over-Markdown, a hybrid retrieval index that combines structured YAML frontmatter queries with full-text search) or another hybrid index only when that trigger is hit.

**Impact on TODOS.md:** No direct TODO item; removes an open architectural question from the decisions directory.

## Section 3: Operational Metrics Write Model

**Purpose:** Persist metric events from the harness so the API has data to serve and so alert thresholds can be derived from observed baselines.

### Categories

| Category | Example event_names |
|---|---|
| `policy_gate` | `blocked`, `warned` |
| `verification` | `retry`, `block`, `escalate` |
| `job_failure` | `timeout`, `write_failed`, `cancelled` |
| `external_service` | `timeout`, `5xx`, `connection_refused` |

### Schema: `metric_events`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `tenant_id` | uuid, nullable | Null = platform/global event |
| `run_id` | uuid, nullable | Harness run correlation |
| `job_id` | uuid, nullable | Job correlation |
| `worker_id` | text, nullable | Worker correlation |
| `category` | text | One of the four categories |
| `event_name` | text | Specific subtype within category |
| `dimensions` | jsonb | Category-specific fields |
| `created_at` | timestamptz | Event timestamp |

**Design rationale:**
- `tenant_id` nullable because `external_service` errors can be system-wide, not tenant-scoped
- `run_id`, `job_id`, `worker_id` are top-level indexed columns (not buried in JSONB) because they are the primary filter keys for debugging and rollups
- `dimensions` JSONB holds category-specific detail (rule_id, service_name, error_type, check_type, etc.)
- Single table with JSONB dimensions instead of four separate tables: at this volume, one table is simpler to migrate, query, and maintain. Partition by category later if volume demands it.

**Index:** `(category, tenant_id, created_at)` for time-range queries.

**RLS:** Two policies on `metric_events`:
1. Tenant-scoped: `tenant_id = current_setting('app.current_tenant')::uuid` — matches existing isolation model, lets tenants see their own metric events
2. Admin/platform: `current_setting('app.is_admin', true) = 'true'` — allows Cockpit/admin roles to see all rows including platform-wide events (null tenant_id). Non-admin users cannot see platform-wide events.

**Admin context helper:** The migration includes a `set_admin_context()` SQL function alongside the existing `set_tenant_context()`. Uses `set_config('app.is_admin', 'true', true)` — transaction-local, same pattern as the existing tenant context, no leak across requests.

**Emitter:** A thin `MetricsEmitter` class in the harness. Pipeline nodes call `emit(category, event_name, tenant_id, run_id, ...)`. Each node already knows when it blocks, fails, or retries.

**Emitter failure contract:**
- Observability is best-effort. Loss is acceptable; crash is not.
- `emit()` wraps the Supabase write in `try/except`, catching `httpx.TimeoutException`, `httpx.HTTPStatusError`, `httpx.ConnectError`, and `TypeError`.
- On failure: structured log via named logger `harness.metrics`, then return `None`. Never re-raise.
- Log at `warning` for bad local inputs (missing `category` or `event_name`). Log at `error` for write failures.
- Structured log fields: `category`, `event_name`, `tenant_id`, `run_id`, `job_id`, `worker_id`, `error_type`, `error_detail`.
- `category` and `event_name` are required. If either is `None`, log a warning and skip the write.

**Migration file:** Next available number in `supabase/migrations/`.

## Section 4: Operational Metrics Read API

**Purpose:** A FastAPI endpoint on the harness server that the Cockpit can poll for metric snapshots. This is the contract surface — the Cockpit does not need to know about Supabase or the table schema.

**Endpoint:** `GET /metrics/snapshot`

**Query parameters:**
- `category` — required for v1, one of the four categories. Response shape supports future expansion to multi-category without breaking changes.
- `tenant_id` — optional, filter to a specific tenant. Omit for platform-wide view.
- `window` — time window in minutes, default 60, max 1440 (24h).
- `group_by` — optional, one of: `event_name`, `worker_id`, `tenant_id`. Top-level indexed fields only; no arbitrary JSONB grouping in v1.

**Response shape:**

```json
{
  "category": "verification",
  "window_minutes": 60,
  "applied_filters": {
    "tenant_id": "tenant-alpha",
    "group_by": "event_name"
  },
  "total_count": 42,
  "groups": [
    {"key": "retry", "count": 30},
    {"key": "block", "count": 10},
    {"key": "escalate", "count": 2}
  ],
  "oldest_event": "2026-03-13T14:00:00Z",
  "newest_event": "2026-03-13T14:59:47Z"
}
```

**Empty window semantics:**

```json
{
  "category": "verification",
  "window_minutes": 60,
  "applied_filters": {},
  "total_count": 0,
  "groups": [],
  "oldest_event": null,
  "newest_event": null
}
```

**Where it lives:** Added to existing `harness/src/harness/server.py`.

**Auth:** Same auth model as existing harness endpoints. No new auth surface.

**DB context selection:** The endpoint chooses tenant or admin context based on the query:
- When `tenant_id` is provided: call `set_tenant_context(tenant_id)` — tenant sees only their own metric events via RLS policy 1.
- When `tenant_id` is omitted (platform-wide view): call `set_admin_context()` — Cockpit sees all rows including platform-wide events via RLS policy 2.
This keeps the read contract consistent with the rest of the repo: tenant-scoped reads use tenant context, cross-tenant reads require admin elevation.

**Input validation:** `category` and `group_by` must be validated against hardcoded allowlists in the endpoint handler before any DB call. Parameterized queries only; no string interpolation.

**When `group_by` is omitted:** `groups` is an empty array and `total_count` reflects the ungrouped count for the category and filters.

**Error responses:**
- Validation errors (invalid category, invalid group_by, window out of range): HTTP 400 with `{"error": "<error_code>", "detail": "<human-readable message>"}`.
- Auth errors: HTTP 401 with the same shape.
- Upstream failures (Supabase timeout or 5xx on read): HTTP 503 with `{"error": "upstream_unavailable", "detail": "Metrics store temporarily unavailable"}`.
- No other error shapes in v1.

**What it does not do:**
- No streaming/websocket — poll-based is sufficient at this scale
- No aggregation beyond counts — histograms and percentiles come later if needed
- No alerting logic — alerting stays in harness internals, consuming the same table

## Section 5: TODOS.md Updates

**Closes:**
- P3 "Define Express V2 horizontal scaling story" — resolved by ADR 002

**Narrows scope on remaining open items:**
- P1 "Extract HVAC logic from V2 backend into industry pack format" — stays active, unchanged
- P2 "Define external service resilience patterns" — partially resolved; narrow remaining scope to Retell/Cal.com/Twilio resilience when those integrations land in this repo
- P3 "Define Cockpit alerting thresholds and channels" — partially resolved; narrow remaining work to production threshold tuning from baseline metrics collected via the metrics API

**Closes (already resolved in code and migrations, marking closed in TODOS.md):**
- P1 "Define compliance graph conflict resolution rule" — resolved in `supabase/migrations/006_compliance_conflict_resolution.sql`
- P2 "Define Inngest event validation schema" — resolved in implementation
- P2 "Define harness → Supabase write failure handling" — resolved in implementation
- P2 "Define PII redaction implementation approach" — resolved in implementation

These items are currently listed as open in TODOS.md but have been resolved through code and migrations. They do not have formal ADR files on disk. The TODOS.md update should mark them closed with references to the implementing code.

**End state:** 3 active TODOs (HVAC extraction, external service resilience, alert threshold tuning). 5 newly closed (Express V2 scaling + 4 already-resolved items marked closed).

## Deliverables Summary

| # | Deliverable | Type | File(s) |
|---|---|---|---|
| 1 | Express V2 scaling ADR | Documentation | `docs/decisions/002-express-v2-scaling.md` |
| 2 | Retrieval engine ADR finalization | Documentation | `docs/decisions/001-retrieval-engine.md` |
| 3 | Metrics write model | Migration + Python | `supabase/migrations/<next>_metric_events.sql`, `harness/src/harness/metrics.py` |
| 4 | Metrics read API | Python | `harness/src/harness/server.py` |
| 5 | TODOS.md cleanup | Documentation | `TODOS.md` |
