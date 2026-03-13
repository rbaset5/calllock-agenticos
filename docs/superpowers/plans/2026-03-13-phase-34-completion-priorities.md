# Phase 3-4 Completion Priorities Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close documentation gaps (2 ADRs), build an operational metrics surface (Supabase table + FastAPI endpoint), wire emit calls into pipeline nodes, and clean up TODOS.md to reflect actual repo state.

**Architecture:** Docs-first, then metrics. Two ADR files resolve open architectural questions. A `metric_events` Supabase table with a best-effort emitter class provides the write model. A single `get_metric_snapshot()` RPC function handles context-setting and aggregation in one transaction. A `/metrics/snapshot` FastAPI endpoint on the existing harness server provides the Cockpit-ready read API. Emit calls are wired into policy_gate, verification, and persist nodes. TODOS.md is updated to reflect 5 closures and 3 narrowed active items.

**Tech Stack:** Python (FastAPI, httpx), PostgreSQL (Supabase migrations, RLS, PL/pgSQL RPC), Markdown (ADRs)

**Spec:** `docs/superpowers/specs/2026-03-13-phase-34-completion-priorities-design.md`

---

## Eng Review Findings (applied during execution)

1. **CRITICAL: Two-transaction RLS bug.** Original plan made two HTTP requests (POST /rpc/set_tenant_context + GET /metric_events). Transaction-local set_config expires between requests, so RLS returns 0 rows. **Fix:** Single `get_metric_snapshot()` RPC function sets context and queries in one transaction.
2. **VALID_CATEGORIES duplicated.** Defined in both metrics.py and server.py. **Fix:** Define once in metrics.py, import in server.py.
3. **Missing RPC failure test.** Only GET failure was tested; POST (RPC call) is a distinct failure path. **Fix:** Added `test_snapshot_returns_503_on_rpc_failure`.
4. **Client-side aggregation.** Original plan fetched all rows and counted in Python. **Fix:** Server-side COUNT/GROUP BY in the RPC function.
5. **Migration number.** Original plan used 007; production repo has migrations up to 044. **Fix:** Use 045.
6. **Emit wiring is not a TODO.** Shipping metrics infra without emit sites produces an inert system. **Fix:** Wire emit calls into pipeline nodes as part of this implementation.

---

## File Structure (updated)

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `docs/decisions/002-express-v2-scaling.md` | Express V2 scaling ADR |
| Modify | `docs/decisions/001-retrieval-engine.md` | Retrieval engine ADR finalization |
| Create | `supabase/migrations/045_metric_events.sql` | metric_events table, RLS, set_admin_context(), get_metric_snapshot() RPC |
| Create | `harness/src/harness/metrics.py` | MetricsEmitter class + VALID_CATEGORIES (single source of truth) |
| Modify | `harness/src/harness/server.py` | /metrics/snapshot endpoint (imports VALID_CATEGORIES from metrics.py) |
| Modify | `harness/src/harness/nodes/policy_gate.py` | Emit on deny |
| Modify | `harness/src/harness/nodes/verification.py` | Emit on failure |
| Modify | `harness/src/harness/nodes/persist.py` | Emit on write failure |
| Modify | `TODOS.md` | Close resolved items, narrow remaining scope |
| Create | `harness/tests/test_metrics.py` | Tests for emitter, snapshot endpoint, RPC failure |

---

## Chunk 1: Documentation (Tasks 1-2)

### Task 1: Express V2 Scaling ADR

**Files:**
- Create: `docs/decisions/002-express-v2-scaling.md`

- [ ] **Step 1: Write the ADR**

```markdown
# ADR 002: Express V2 Horizontal Scaling

Status: Accepted

## Context

Express V2 on Render handles webhook ingress from Retell AI and serves API routes. It parses webhooks and emits Inngest events — stateless and lightweight. The harness runs as a separate Render service.

Current load is 1 contractor × 3 trades = low tens of calls/day. At 10 tenants × 3 trades, Express V2 still operates well within single-instance capacity for a Node.js server.

## Decision

Express V2 remains single-instance by default.

Revisit when, over a sustained window, any of these hold:

- Webhook p95 latency > 2s
- CPU > 80%
- Memory pressure or restarts appear
- Webhook backlog or 5xx rate rises materially

When triggered: run multiple stateless instances behind the platform load balancer, preserving statelessness and idempotent webhook handling.

## Consequences

- No scaling infrastructure needed now
- Scaling triggers are documented and measurable
- Scaling Express V2 is only useful if the bottleneck is actually ingress — if Inngest, the harness, or downstream services are the choke point, adding Express instances will not help
```

- [ ] **Step 2: Commit**

```bash
git add docs/decisions/002-express-v2-scaling.md
git commit -m "docs: add Express V2 scaling ADR (002)

Accepts single-instance default with multi-signal scaling triggers.
Documents that scaling ingress only helps if ingress is the bottleneck."
```

### Task 2: Retrieval Engine ADR Finalization

**Files:**
- Modify: `docs/decisions/001-retrieval-engine.md`

- [ ] **Step 1: Update the ADR from Proposed to Accepted**

Replace the entire contents of `docs/decisions/001-retrieval-engine.md` with:

```markdown
# ADR 001: Retrieval Engine Evaluation

Status: Accepted

## Context

The architecture spec called for evaluating QMD (Query-over-Markdown, a hybrid retrieval index combining structured YAML frontmatter queries with full-text search) or an equivalent during Phase 1.

## Decision

Accept the current file-backed retrieval approach. The knowledge volume is small enough that a heavier retrieval layer is not justified.

Current approach: file-backed retrieval via markdown/YAML traversal, wiki-link resolution, and context assembly prioritization.

## Upgrade Trigger

Revisit when:

- Measured retrieval p95 > 500ms
- Relevance is observably poor
- Context assembly starts dropping important nodes under budget pressure

Evaluate QMD or another hybrid index only when a trigger is hit.

## Consequences

- No new retrieval infrastructure needed now
- Upgrade path is documented and tied to observable metrics
- The metrics API (ADR pending) will make retrieval p95 measurable
```

- [ ] **Step 2: Commit**

```bash
git add docs/decisions/001-retrieval-engine.md
git commit -m "docs: finalize retrieval engine ADR (001) as Accepted

Accepts file-backed retrieval with upgrade triggers tied to
observable metrics: p95 > 500ms, poor relevance, or budget pressure."
```

---

## Chunk 2: Metrics Write Model (Tasks 3-4)

### Task 3: Database Migration

**Files:**
- Create: `supabase/migrations/007_metric_events.sql`

Reference existing patterns:
- `supabase/migrations/005_rls_policies.sql` — for `set_tenant_context()` and RLS policy syntax
- `supabase/migrations/001_tenants.sql` — for table creation pattern

- [ ] **Step 1: Write the migration**

```sql
-- metric_events: operational metrics for alert threshold derivation
create table public.metric_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references public.tenants(id),
  run_id uuid,
  job_id uuid,
  worker_id text,
  category text not null,
  event_name text not null,
  dimensions jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index idx_metric_events_category_tenant_time
  on public.metric_events (category, tenant_id, created_at);

-- RLS
alter table public.metric_events enable row level security;
alter table public.metric_events force row level security;

-- Policy 1: tenant-scoped reads
create policy metric_events_tenant_isolation on public.metric_events
  using (tenant_id = public.current_tenant_id());

-- Policy 2: admin/platform reads (all rows including null tenant_id)
create policy metric_events_admin_access on public.metric_events
  using (current_setting('app.is_admin', true) = 'true');

-- Admin context helper (mirrors set_tenant_context from 005)
create or replace function public.set_admin_context()
returns void
language sql
as $$
  select set_config('app.is_admin', 'true', true);
$$;
```

- [ ] **Step 2: Verify migration numbering**

Run: `ls supabase/migrations/`
Expected: files 001 through 006 exist, 007 does not.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/007_metric_events.sql
git commit -m "feat: add metric_events table with RLS and admin context

Creates metric_events for operational metrics (policy blocks,
verification failures, job failures, external service errors).
Adds set_admin_context() for Cockpit-level reads."
```

### Task 4: MetricsEmitter Class

**Files:**
- Create: `harness/src/harness/metrics.py`
- Create: `harness/tests/test_metrics.py`

Reference existing patterns:
- `harness/src/db/supabase_repository.py` — for `_headers()`, `_base_url()`, `_raise_for_status()` helpers
- `harness/tests/test_server.py` — for test style (plain pytest, no classes)

- [ ] **Step 1: Write the failing tests for the emitter**

Create `harness/tests/test_metrics.py`:

```python
import logging

import pytest

from harness.metrics import MetricsEmitter


def test_emit_returns_none_on_success() -> None:
    emitter = MetricsEmitter()
    result = emitter.emit(
        category="policy_gate",
        event_name="blocked",
        tenant_id="tenant-alpha",
        run_id="run-1",
    )
    assert result is None


def test_emit_skips_write_when_category_is_none(caplog) -> None:
    emitter = MetricsEmitter()
    with caplog.at_level(logging.WARNING, logger="harness.metrics"):
        emitter.emit(category=None, event_name="blocked")
    assert "category" in caplog.text.lower()


def test_emit_skips_write_when_event_name_is_none(caplog) -> None:
    emitter = MetricsEmitter()
    with caplog.at_level(logging.WARNING, logger="harness.metrics"):
        emitter.emit(category="policy_gate", event_name=None)
    assert "event_name" in caplog.text.lower()


def _make_emitter_with_failing_post(monkeypatch, exception):
    """Helper: configure emitter to raise the given exception on post."""
    import httpx

    def _fail_post(*args, **kwargs):
        raise exception

    emitter = MetricsEmitter()
    monkeypatch.setattr(httpx, "post", _fail_post)
    monkeypatch.setenv("SUPABASE_URL", "http://fake")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")
    return emitter


def test_emit_swallows_timeout_exception(monkeypatch, caplog) -> None:
    """Emitter must never crash the pipeline on timeout."""
    import httpx

    emitter = _make_emitter_with_failing_post(monkeypatch, httpx.TimeoutException("connection timed out"))
    with caplog.at_level(logging.ERROR, logger="harness.metrics"):
        result = emitter.emit(category="verification", event_name="block", tenant_id="t-1", run_id="r-1")
    assert result is None
    assert "timeout" in caplog.text.lower() or "timed out" in caplog.text.lower()


def test_emit_swallows_connect_error(monkeypatch, caplog) -> None:
    """Emitter must never crash the pipeline on connection refused."""
    import httpx

    emitter = _make_emitter_with_failing_post(monkeypatch, httpx.ConnectError("connection refused"))
    with caplog.at_level(logging.ERROR, logger="harness.metrics"):
        result = emitter.emit(category="policy_gate", event_name="blocked", tenant_id="t-1")
    assert result is None
    assert "connect" in caplog.text.lower() or "refused" in caplog.text.lower()


def test_emit_swallows_http_status_error(monkeypatch, caplog) -> None:
    """Emitter must never crash the pipeline on 5xx response."""
    import httpx

    response = httpx.Response(500, request=httpx.Request("POST", "http://fake"))
    emitter = _make_emitter_with_failing_post(monkeypatch, httpx.HTTPStatusError("server error", request=response.request, response=response))
    with caplog.at_level(logging.ERROR, logger="harness.metrics"):
        result = emitter.emit(category="job_failure", event_name="timeout", tenant_id="t-1")
    assert result is None
    assert "error" in caplog.text.lower()


VALID_CATEGORIES = ["policy_gate", "verification", "job_failure", "external_service"]


@pytest.mark.parametrize("category", VALID_CATEGORIES)
def test_emit_accepts_all_valid_categories(category: str) -> None:
    emitter = MetricsEmitter()
    result = emitter.emit(category=category, event_name="test")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd harness && python -m pytest tests/test_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'harness.metrics'`

- [ ] **Step 3: Write the MetricsEmitter implementation**

Create `harness/src/harness/metrics.py`:

```python
from __future__ import annotations

import logging
from typing import Any

import httpx

from db.supabase_repository import _base_url, _headers, is_configured

logger = logging.getLogger("harness.metrics")

VALID_CATEGORIES = frozenset(
    ["policy_gate", "verification", "job_failure", "external_service"]
)


class MetricsEmitter:
    """Best-effort metrics emitter. Loss is acceptable; crash is not."""

    def emit(
        self,
        *,
        category: str | None,
        event_name: str | None,
        tenant_id: str | None = None,
        run_id: str | None = None,
        job_id: str | None = None,
        worker_id: str | None = None,
        dimensions: dict[str, Any] | None = None,
    ) -> None:
        if not category:
            logger.warning("emit skipped: category is required", extra={"event_name": event_name})
            return None
        if not event_name:
            logger.warning("emit skipped: event_name is required", extra={"category": category})
            return None
        if not is_configured():
            return None

        payload = {
            "tenant_id": tenant_id,
            "run_id": run_id,
            "job_id": job_id,
            "worker_id": worker_id,
            "category": category,
            "event_name": event_name,
            "dimensions": dimensions or {},
        }
        try:
            httpx.post(
                f"{_base_url()}/metric_events",
                headers={**_headers(), "Prefer": "return=minimal"},
                json=payload,
                timeout=10.0,
            )
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError, TypeError) as exc:
            logger.error(
                "emit failed: %s",
                str(exc),
                extra={
                    "category": category,
                    "event_name": event_name,
                    "tenant_id": tenant_id,
                    "run_id": run_id,
                    "job_id": job_id,
                    "worker_id": worker_id,
                    "error_type": type(exc).__name__,
                    "error_detail": str(exc),
                },
            )
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd harness && python -m pytest tests/test_metrics.py -v`
Expected: All 9 tests PASS (success, nil category, nil event_name, timeout, connect error, HTTP status error, and 4 parametrized categories).

- [ ] **Step 5: Commit**

```bash
git add harness/src/harness/metrics.py harness/tests/test_metrics.py
git commit -m "feat: add MetricsEmitter with best-effort write and failure contract

Emitter swallows all write failures, logs structured errors via
harness.metrics logger. Validates category and event_name locally.
Never crashes the pipeline."
```

---

## Chunk 3: Metrics Read API (Tasks 5-6)

### Task 5: Snapshot Endpoint Tests

**Files:**
- Modify: `harness/tests/test_metrics.py` (append)

- [ ] **Step 1: Write failing tests for the snapshot endpoint**

Append to `harness/tests/test_metrics.py`:

```python
from fastapi.testclient import TestClient

from harness.server import app


def test_snapshot_returns_empty_window() -> None:
    client = TestClient(app)
    response = client.get("/metrics/snapshot", params={"category": "policy_gate"})
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "policy_gate"
    assert data["window_minutes"] == 60
    assert data["total_count"] == 0
    assert data["groups"] == []
    assert data["oldest_event"] is None
    assert data["newest_event"] is None
    assert "applied_filters" in data


def test_snapshot_rejects_invalid_category() -> None:
    client = TestClient(app)
    response = client.get("/metrics/snapshot", params={"category": "invalid"})
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "invalid_category"
    assert "detail" in data


def test_snapshot_rejects_invalid_group_by() -> None:
    client = TestClient(app)
    response = client.get(
        "/metrics/snapshot",
        params={"category": "policy_gate", "group_by": "dimensions"},
    )
    assert response.status_code == 400


def test_snapshot_rejects_window_out_of_range() -> None:
    client = TestClient(app)
    response = client.get(
        "/metrics/snapshot",
        params={"category": "policy_gate", "window": "2000"},
    )
    assert response.status_code == 400


def test_snapshot_requires_category() -> None:
    client = TestClient(app)
    response = client.get("/metrics/snapshot")
    assert response.status_code == 400


def test_snapshot_requires_auth_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_EVENT_SECRET", "test-secret")
    client = TestClient(app)
    response = client.get("/metrics/snapshot", params={"category": "policy_gate"})
    assert response.status_code == 401

    authorized = client.get(
        "/metrics/snapshot",
        params={"category": "policy_gate"},
        headers={"Authorization": "Bearer test-secret"},
    )
    assert authorized.status_code == 200


def test_snapshot_returns_503_on_upstream_failure(monkeypatch) -> None:
    import httpx as _httpx

    monkeypatch.setenv("SUPABASE_URL", "http://fake")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")

    def _fail_get(*args, **kwargs):
        raise _httpx.TimeoutException("upstream timed out")

    monkeypatch.setattr(_httpx, "get", _fail_get)
    client = TestClient(app)
    response = client.get("/metrics/snapshot", params={"category": "policy_gate"})
    assert response.status_code == 503
    data = response.json()
    assert data["error"] == "upstream_unavailable"


def test_snapshot_auth_error_shape(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_EVENT_SECRET", "test-secret")
    client = TestClient(app)
    response = client.get("/metrics/snapshot", params={"category": "policy_gate"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "auth_failed"
    assert "detail" in data


def test_snapshot_includes_applied_filters() -> None:
    client = TestClient(app)
    response = client.get(
        "/metrics/snapshot",
        params={
            "category": "verification",
            "tenant_id": "tenant-alpha",
            "group_by": "event_name",
            "window": "30",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["applied_filters"]["tenant_id"] == "tenant-alpha"
    assert data["applied_filters"]["group_by"] == "event_name"
    assert data["window_minutes"] == 30
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `cd harness && python -m pytest tests/test_metrics.py::test_snapshot_returns_empty_window -v`
Expected: FAIL — 404 (endpoint does not exist yet).

### Task 6: Snapshot Endpoint Implementation

**Files:**
- Modify: `harness/src/harness/server.py`

Reference existing patterns:
- `validate_event_auth()` at `server.py:62-68` — for auth reuse
- `harness/src/db/supabase_repository.py` — for Supabase query patterns

- [ ] **Step 1: Add the snapshot endpoint to server.py**

Add these imports near the top of `server.py` (after the existing imports, inside the `try` block that imports FastAPI):

```python
try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
except Exception:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]
```

Add this import at the top level (not inside try/except):

```python
from datetime import datetime, timedelta, timezone
```

Also update `validate_event_auth` to return a structured error shape matching the spec:

```python
def validate_event_auth(request: Request) -> None:
    expected = os.getenv("HARNESS_EVENT_SECRET")
    if not expected:
        return
    authorization = request.headers.get("authorization", "")
    if authorization != f"Bearer {expected}":
        return JSONResponse(
            status_code=401,
            content={"error": "auth_failed", "detail": "Invalid event secret"},
        )
```

Wait — `validate_event_auth` is also used by existing endpoints that expect it to raise. Instead, add a new helper for the metrics endpoint that returns a JSONResponse directly. Keep the existing `validate_event_auth` unchanged for backward compatibility.

**Revised approach:** Add a `_check_event_auth` helper that returns a JSONResponse or None, used only by the metrics endpoint. Keep `validate_event_auth` unchanged.

Add these inside the `if FastAPI:` block, after the existing `process_call_event` endpoint:

```python
    VALID_CATEGORIES = frozenset(
        ["policy_gate", "verification", "job_failure", "external_service"]
    )
    VALID_GROUP_BY = frozenset(["event_name", "worker_id", "tenant_id"])

    def _error_response(status_code: int, error: str, detail: str) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"error": error, "detail": detail})

    def _check_metrics_auth(request: Request) -> JSONResponse | None:
        expected = os.getenv("HARNESS_EVENT_SECRET")
        if not expected:
            return None
        authorization = request.headers.get("authorization", "")
        if authorization != f"Bearer {expected}":
            return _error_response(401, "auth_failed", "Invalid event secret")
        return None

    def _query_metric_snapshot(
        *,
        category: str,
        tenant_id: str | None,
        cutoff: datetime,
        group_by: str | None,
    ) -> dict[str, Any] | JSONResponse:
        """Query metric_events via Supabase REST API or return empty for local mode."""
        from db.repository import using_supabase

        if not using_supabase():
            return {"total_count": 0, "groups": [], "oldest_event": None, "newest_event": None}

        import httpx as _httpx
        from db.supabase_repository import _base_url, _headers

        # Set DB context: tenant-scoped or admin
        try:
            if tenant_id:
                _httpx.post(
                    f"{_base_url()}/rpc/set_tenant_context",
                    headers=_headers(),
                    json={"tenant_uuid": tenant_id},
                    timeout=10.0,
                )
            else:
                _httpx.post(
                    f"{_base_url()}/rpc/set_admin_context",
                    headers=_headers(),
                    json={},
                    timeout=10.0,
                )
        except (_httpx.TimeoutException, _httpx.HTTPStatusError, _httpx.ConnectError):
            return _error_response(503, "upstream_unavailable", "Metrics store temporarily unavailable")

        params: dict[str, str] = {
            "category": f"eq.{category}",
            "created_at": f"gte.{cutoff.isoformat()}",
            "select": "id,created_at" + (f",{group_by}" if group_by else ""),
            "order": "created_at.asc",
        }
        if tenant_id:
            params["tenant_id"] = f"eq.{tenant_id}"

        try:
            response = _httpx.get(
                f"{_base_url()}/metric_events",
                params=params,
                headers=_headers(),
                timeout=10.0,
            )
            response.raise_for_status()
        except (_httpx.TimeoutException, _httpx.HTTPStatusError, _httpx.ConnectError):
            return _error_response(503, "upstream_unavailable", "Metrics store temporarily unavailable")

        rows = response.json()
        total_count = len(rows)

        if total_count == 0:
            return {"total_count": 0, "groups": [], "oldest_event": None, "newest_event": None}

        oldest_event = rows[0]["created_at"]
        newest_event = rows[-1]["created_at"]

        groups: list[dict[str, Any]] = []
        if group_by:
            counts: dict[str, int] = {}
            for row in rows:
                key = str(row.get(group_by, "unknown"))
                counts[key] = counts.get(key, 0) + 1
            groups = [{"key": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]

        return {
            "total_count": total_count,
            "groups": groups,
            "oldest_event": oldest_event,
            "newest_event": newest_event,
        }

    @app.get("/metrics/snapshot")
    def metrics_snapshot(request: Request, category: str | None = None, tenant_id: str | None = None, window: int = 60, group_by: str | None = None):
        auth_error = _check_metrics_auth(request)
        if auth_error:
            return auth_error

        if not category:
            return _error_response(400, "missing_category", "category is required")
        if category not in VALID_CATEGORIES:
            return _error_response(400, "invalid_category", f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}")
        if group_by and group_by not in VALID_GROUP_BY:
            return _error_response(400, "invalid_group_by", f"group_by must be one of: {', '.join(sorted(VALID_GROUP_BY))}")
        if window < 1 or window > 1440:
            return _error_response(400, "invalid_window", "window must be between 1 and 1440 minutes")

        applied_filters: dict[str, Any] = {}
        if tenant_id:
            applied_filters["tenant_id"] = tenant_id
        if group_by:
            applied_filters["group_by"] = group_by

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window)

        result = _query_metric_snapshot(
            category=category,
            tenant_id=tenant_id,
            cutoff=cutoff,
            group_by=group_by,
        )

        # If result is a JSONResponse (error), return it directly
        if isinstance(result, JSONResponse):
            return result

        return {
            "category": category,
            "window_minutes": window,
            "applied_filters": applied_filters,
            **result,
        }
```

- [ ] **Step 2: Run all metrics tests**

Run: `cd harness && python -m pytest tests/test_metrics.py -v`
Expected: All tests PASS (emitter tests + snapshot tests).

- [ ] **Step 3: Run full test suite to verify no regressions**

Run: `cd harness && python -m pytest -v`
Expected: All existing tests still pass.

- [ ] **Step 4: Commit**

```bash
git add harness/src/harness/server.py harness/tests/test_metrics.py
git commit -m "feat: add /metrics/snapshot endpoint with validation and error contract

Returns metric event counts with optional grouping and time window.
Uses tenant context for scoped reads, admin context for platform-wide.
Returns 400 for invalid params, 401 for auth, 503 for upstream failures."
```

---

## Chunk 4: TODOS.md Cleanup (Task 7)

### Task 7: Update TODOS.md

**Files:**
- Modify: `TODOS.md`

- [ ] **Step 1: Rewrite TODOS.md**

Replace the entire contents of `TODOS.md` with:

```markdown
# TODOS

Items identified during architecture reviews (2026-03-12).
Updated 2026-03-13: closed resolved items, narrowed remaining scope.

## Active

### P1 — Extract HVAC logic from V2 backend into industry pack format
**What:** The existing V2 backend has hardcoded HVAC logic (117 smart tags, emergency tiers, service taxonomy, urgency rules). This needs to be extracted into the spec's industry pack format.
**Why:** This is the bridge from current state to target architecture for the industry pack layer. Without it, the industry pack concept remains theoretical.
**Effort:** L
**Depends on:** Section 0 (Current State) being finalized, Industry Pack format being stable.
**Source:** CEO review, Section 1A (Bridge Gap).

### P2 — Define external service resilience patterns (narrowed)
**What:** Define fallback behavior when Retell AI, Cal.com, or Twilio are unavailable.
**Why:** All three are production SPOFs with no fallback story. Supabase resilience is covered by the harness write-failure handling already implemented.
**Scope:** Deferred until Retell/Cal.com/Twilio integration clients exist in this repo. Define resilience patterns alongside the integration code, not speculatively.
**Effort:** M
**Source:** CEO review, Section 1F (Single Points of Failure).

### P3 — Tune Cockpit alerting thresholds from production baselines
**What:** Define specific threshold values for the four alert types (policy gate block rate, worker metric degradation, job failure spikes, external service errors) using observed baselines from the metrics API.
**Why:** Thresholds need baseline data from actual deployment, not guesses.
**Prerequisite:** Metrics API deployed and collecting data from production traffic.
**Effort:** S
**Source:** Eng review, Section 3 (Alerting).

## Closed

### ~~P3 — Define Express V2 horizontal scaling story~~
**Resolved by:** `docs/decisions/002-express-v2-scaling.md` (ADR 002)

### ~~P1 — Define compliance graph conflict resolution rule~~
**Resolved by:** `supabase/migrations/006_compliance_conflict_resolution.sql`

### ~~P2 — Define Inngest event validation schema~~
**Resolved by:** Inngest event schema implementation in `inngest/src/events/schemas.ts`

### ~~P2 — Define harness → Supabase write failure handling~~
**Resolved by:** Harness persistence node and repository error handling in `harness/src/harness/nodes/persist.py` and `harness/src/db/supabase_repository.py`

### ~~P2 — Define PII redaction implementation approach~~
**Resolved by:** Pattern-matching PII redactor in `harness/src/observability/pii_redactor.py` and verification node checks in `harness/src/harness/nodes/verification.py`
```

- [ ] **Step 2: Commit**

```bash
git add TODOS.md
git commit -m "docs: close 5 resolved TODOs, narrow remaining 3 to actionable scope

Closes: Express V2 scaling (ADR 002), compliance conflict resolution,
Inngest event validation, Supabase write failures, PII redaction.
Narrows: external service resilience to when integrations land,
alerting thresholds to production baseline tuning."
```

- [ ] **Step 3: Run validation scripts to ensure no breakage**

Run: `node scripts/validate-knowledge.ts && node scripts/validate-worker-specs.ts && node scripts/validate-packs.ts`
Expected: All pass (TODOS.md is not validated by these, but confirms repo integrity).

- [ ] **Step 4: Final commit with plan reference**

```bash
git add -A
git status
# Only commit if there are unstaged changes from linting or formatting
```
