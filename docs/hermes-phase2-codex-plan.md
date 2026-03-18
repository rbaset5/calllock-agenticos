# Hermes Phase 2 — Shadow Mode on eng-ai-voice

## Goal

Run eng-ai-voice through BOTH `call_llm()` AND `run_hermes_worker()` on
every invocation. Compare outputs field-by-field. Always return the baseline
(`call_llm`) result. Log comparison metrics for graduation decision.

After this plan:
- Shadow mode infrastructure exists in `base.py:run_worker()`
- eng-ai-voice runs both engines when `shadow_hermes_eng-ai-voice: true`
- Comparison results logged to `shadow_comparisons` Supabase table
- Shadow report aggregation query exists for graduation review
- All existing tests pass + new shadow mode tests

## Prerequisites

- Hermes Phase 1 complete (adapter, feature flags, skill pipeline)
- hermes-agent importable (installed via git clone at deploy time)

---

## Task 1: Shadow Comparisons Table

### File: `supabase/migrations/056_shadow_comparisons.sql`

**Create this file:**

```sql
-- Shadow mode comparison results for Hermes rollout.
-- Each row records a field-by-field comparison between
-- call_llm() baseline and run_hermes_worker() for a single run.

create table shadow_comparisons (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id),
    worker_id text not null,
    run_id text not null,
    task_type text,

    -- Baseline (call_llm) result
    baseline_output jsonb not null,

    -- Hermes result
    hermes_output jsonb,
    hermes_error text,           -- null if Hermes succeeded

    -- Comparison metrics
    field_match_count integer,   -- fields where values match
    field_total integer,         -- total fields compared
    field_match_rate numeric(5,4), -- match_count / total

    -- Performance
    baseline_latency_ms integer,
    hermes_latency_ms integer,
    hermes_iterations integer,

    created_at timestamptz not null default now()
);

alter table shadow_comparisons enable row level security;
alter table shadow_comparisons force row level security;
create policy shadow_comparisons_tenant on shadow_comparisons
    using (tenant_id = current_setting('app.current_tenant')::uuid);

-- Index for aggregation queries
create index idx_shadow_comparisons_worker_created
    on shadow_comparisons (worker_id, created_at desc);

comment on table shadow_comparisons is
    'Shadow mode comparison results between call_llm baseline and Hermes worker runs';
```

### Verification

```bash
ls supabase/migrations/056_shadow_comparisons.sql && echo "Migration file exists"
```

---

## Task 2: Shadow Mode in run_worker()

### File: `harness/src/harness/graphs/workers/base.py`

**Change:** Add a shadow mode path that runs BOTH engines and compares.

Find the `run_worker` function. The current structure is:

```python
# Hermes path (feature flag)
# Existing LLM path
# Deterministic fallback
```

Replace the Hermes path block with a shadow-aware version. The new logic:

1. Check for `shadow_hermes_{worker_id}` flag (shadow mode)
2. If shadow: run baseline first, then Hermes, compare, log, return baseline
3. If not shadow: check `hermes_worker_{worker_id}` flag (direct Hermes mode)
4. Else: existing `call_llm` path

Add these imports at the top of the file:

```python
import time
import logging

logger = logging.getLogger(__name__)
```

Replace the run_worker function body (keep the signature):

```python
def run_worker(
    task: dict[str, Any],
    *,
    worker_id: str,
    deterministic_builder: Callable[[dict[str, Any]], dict[str, Any]],
    llm_enabled: bool = True,
) -> dict[str, Any]:
    worker_spec = task.get("worker_spec") or load_worker_spec(worker_id)
    output_fields = expected_output_fields(worker_spec)
    deterministic_mode = task.get("tenant_config", {}).get("deterministic_mode", False)
    feature_flags = task.get("feature_flags", {})

    # Shadow mode: run BOTH engines, compare, return baseline
    if (llm_enabled and not deterministic_mode
            and feature_flags.get(f"shadow_hermes_{worker_id}", False)):
        return _run_shadow_mode(task, worker_id=worker_id, worker_spec=worker_spec,
                                output_fields=output_fields,
                                deterministic_builder=deterministic_builder)

    # Hermes path: multi-turn agent loop (per-worker opt-in)
    if (llm_enabled and not deterministic_mode
            and feature_flags.get(f"hermes_worker_{worker_id}", False)):
        try:
            from harness.hermes_adapter import run_hermes_worker
            generated = run_hermes_worker(task, worker_id=worker_id, worker_spec=worker_spec)
            return ensure_output_shape(generated, output_fields)
        except Exception:
            pass  # fall through to existing LLM path

    # Existing LLM path: single-shot call_llm
    if llm_enabled and not deterministic_mode and feature_flags.get("llm_workers_enabled", True):
        try:
            generated = call_llm(build_prompt(task, worker_spec, output_fields), output_fields)
            return ensure_output_shape(generated, output_fields)
        except Exception:
            pass

    return ensure_output_shape(deterministic_builder(task), output_fields)


def _run_shadow_mode(
    task: dict[str, Any],
    *,
    worker_id: str,
    worker_spec: dict[str, Any],
    output_fields: list[str],
    deterministic_builder: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Run both call_llm and Hermes, compare, return baseline result."""

    # 1. Run baseline (call_llm)
    baseline_start = time.monotonic()
    try:
        baseline = call_llm(build_prompt(task, worker_spec, output_fields), output_fields)
        baseline = ensure_output_shape(baseline, output_fields)
    except Exception:
        baseline = ensure_output_shape(deterministic_builder(task), output_fields)
    baseline_ms = int((time.monotonic() - baseline_start) * 1000)

    # 2. Run Hermes (best-effort, never blocks baseline return)
    hermes_output = None
    hermes_error = None
    hermes_ms = 0
    hermes_iterations = 0
    try:
        from harness.hermes_adapter import run_hermes_worker
        hermes_start = time.monotonic()
        hermes_output = run_hermes_worker(task, worker_id=worker_id, worker_spec=worker_spec)
        hermes_output = ensure_output_shape(hermes_output, output_fields)
        hermes_ms = int((time.monotonic() - hermes_start) * 1000)
    except Exception as e:
        hermes_error = f"{type(e).__name__}: {e}"
        logger.warning("Shadow Hermes failed for %s: %s", worker_id, hermes_error)

    # 3. Compare field-by-field
    comparison = _compare_outputs(baseline, hermes_output, output_fields)

    # 4. Log comparison (best-effort, don't fail the run)
    try:
        _log_shadow_comparison(
            task=task,
            worker_id=worker_id,
            baseline=baseline,
            hermes_output=hermes_output,
            hermes_error=hermes_error,
            comparison=comparison,
            baseline_ms=baseline_ms,
            hermes_ms=hermes_ms,
            hermes_iterations=hermes_iterations,
        )
    except Exception as e:
        logger.warning("Failed to log shadow comparison: %s", e)

    # 5. Always return baseline
    return baseline


def _compare_outputs(
    baseline: dict[str, Any],
    hermes: dict[str, Any] | None,
    output_fields: list[str],
) -> dict[str, Any]:
    """Compare two outputs field-by-field."""
    if hermes is None:
        return {"match_count": 0, "total": len(output_fields), "match_rate": 0.0, "mismatches": output_fields}

    match_count = 0
    mismatches = []
    for field in output_fields:
        b_val = baseline.get(field)
        h_val = hermes.get(field)
        if b_val == h_val:
            match_count += 1
        elif isinstance(b_val, str) and isinstance(h_val, str) and b_val.strip().lower() == h_val.strip().lower():
            match_count += 1  # case-insensitive string match
        else:
            mismatches.append(field)

    total = len(output_fields)
    return {
        "match_count": match_count,
        "total": total,
        "match_rate": match_count / total if total > 0 else 0.0,
        "mismatches": mismatches,
    }


def _log_shadow_comparison(
    *,
    task: dict[str, Any],
    worker_id: str,
    baseline: dict[str, Any],
    hermes_output: dict[str, Any] | None,
    hermes_error: str | None,
    comparison: dict[str, Any],
    baseline_ms: int,
    hermes_ms: int,
    hermes_iterations: int,
) -> None:
    """Log shadow comparison to Supabase (best-effort)."""
    import json

    try:
        from harness.graphs.workers.base import _get_repository
        repo = _get_repository()
    except Exception:
        # No repository available — log to stdout instead
        logger.info(
            "Shadow comparison [%s]: match_rate=%.2f baseline_ms=%d hermes_ms=%d error=%s",
            worker_id, comparison["match_rate"], baseline_ms, hermes_ms, hermes_error,
        )
        return

    tenant_id = task.get("tenant_id", "")
    run_id = task.get("run_id", "")
    task_type = task.get("task_context", {}).get("task_type", "")

    repo.insert("shadow_comparisons", {
        "tenant_id": tenant_id,
        "worker_id": worker_id,
        "run_id": run_id,
        "task_type": task_type,
        "baseline_output": json.dumps(baseline),
        "hermes_output": json.dumps(hermes_output) if hermes_output else None,
        "hermes_error": hermes_error,
        "field_match_count": comparison["match_count"],
        "field_total": comparison["total"],
        "field_match_rate": comparison["match_rate"],
        "baseline_latency_ms": baseline_ms,
        "hermes_latency_ms": hermes_ms,
        "hermes_iterations": hermes_iterations,
    })
```

If `_get_repository` doesn't exist, create a simple helper:

```python
def _get_repository():
    """Get the active repository for logging. Returns None if unavailable."""
    from db.supabase_repository import SupabaseRepository
    return SupabaseRepository()
```

### Verification

```bash
cd harness && PYTHONPATH=src python -m pytest tests/ -x -q 2>&1 | tail -10
```

---

## Task 3: Shadow Mode Tests

### File: `harness/tests/test_shadow_mode.py`

**Create this file:**

```python
"""Tests for shadow mode comparison logic."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import the comparison function directly
from harness.graphs.workers.base import _compare_outputs


class TestCompareOutputs:
    def test_exact_match(self):
        baseline = {"summary": "all good", "status": "green"}
        hermes = {"summary": "all good", "status": "green"}
        result = _compare_outputs(baseline, hermes, ["summary", "status"])
        assert result["match_count"] == 2
        assert result["match_rate"] == 1.0
        assert result["mismatches"] == []

    def test_partial_match(self):
        baseline = {"summary": "all good", "status": "green"}
        hermes = {"summary": "all good", "status": "yellow"}
        result = _compare_outputs(baseline, hermes, ["summary", "status"])
        assert result["match_count"] == 1
        assert result["match_rate"] == 0.5
        assert result["mismatches"] == ["status"]

    def test_no_match(self):
        baseline = {"summary": "all good", "status": "green"}
        hermes = {"summary": "bad", "status": "red"}
        result = _compare_outputs(baseline, hermes, ["summary", "status"])
        assert result["match_count"] == 0
        assert result["match_rate"] == 0.0

    def test_hermes_none(self):
        baseline = {"summary": "all good", "status": "green"}
        result = _compare_outputs(baseline, None, ["summary", "status"])
        assert result["match_count"] == 0
        assert result["match_rate"] == 0.0
        assert result["mismatches"] == ["summary", "status"]

    def test_case_insensitive_string_match(self):
        baseline = {"summary": "All Good"}
        hermes = {"summary": "all good"}
        result = _compare_outputs(baseline, hermes, ["summary"])
        assert result["match_count"] == 1
        assert result["match_rate"] == 1.0

    def test_empty_fields(self):
        result = _compare_outputs({}, {}, [])
        assert result["match_count"] == 0
        assert result["match_rate"] == 0.0
        assert result["mismatches"] == []

    def test_none_values_match(self):
        baseline = {"summary": None}
        hermes = {"summary": None}
        result = _compare_outputs(baseline, hermes, ["summary"])
        assert result["match_count"] == 1
```

### Verification

```bash
cd harness && PYTHONPATH=src python -m pytest tests/test_shadow_mode.py -x -q
```

---

## Task 4: Shadow Graduation Query

### File: `scripts/shadow-graduation-report.sql`

**Create this file:**

```sql
-- Shadow Mode Graduation Report
-- Run this query to check if a worker is ready to switch from
-- call_llm() baseline to Hermes primary.
--
-- Graduation criteria:
--   field_match_rate >= 0.95 across 50+ runs
--   hermes_error rate < 5%
--   p95 hermes_latency_ms <= 30000
--   hermes cost <= 5x baseline (estimated from iterations)

select
    worker_id,
    count(*) as total_runs,
    count(*) filter (where hermes_error is null) as hermes_successes,
    count(*) filter (where hermes_error is not null) as hermes_failures,
    round(100.0 * count(*) filter (where hermes_error is null) / count(*), 1) as success_rate_pct,
    round(avg(field_match_rate)::numeric, 4) as avg_match_rate,
    round(min(field_match_rate)::numeric, 4) as min_match_rate,
    percentile_cont(0.5) within group (order by field_match_rate) as median_match_rate,
    round(avg(baseline_latency_ms)::numeric, 0) as avg_baseline_ms,
    round(avg(hermes_latency_ms)::numeric, 0) as avg_hermes_ms,
    percentile_cont(0.95) within group (order by hermes_latency_ms) as p95_hermes_ms,
    round(avg(hermes_iterations)::numeric, 1) as avg_iterations,
    -- Graduation check
    case
        when count(*) >= 50
            and avg(field_match_rate) >= 0.95
            and 100.0 * count(*) filter (where hermes_error is null) / count(*) >= 95
            and percentile_cont(0.95) within group (order by hermes_latency_ms) <= 30000
        then 'READY'
        else 'NOT READY'
    end as graduation_status
from shadow_comparisons
where created_at > now() - interval '30 days'
group by worker_id
order by worker_id;
```

### Verification

```bash
ls scripts/shadow-graduation-report.sql && echo "Graduation query exists"
```

---

## Task 5: Run Full Test Suite

### Verification

```bash
cd harness && PYTHONPATH=src python -m pytest tests/ -x -q 2>&1 | tail -20
node scripts/validate-worker-specs.ts
python scripts/validate-contracts.py
```

---

## Execution Order

```
Task 1  →  Shadow comparisons Supabase table
Task 2  →  Shadow mode logic in base.py:run_worker()
Task 3  →  Shadow mode comparison tests
Task 4  →  Graduation report SQL query
Task 5  →  Full test suite verification
```

One commit per task. Verify after each. Stop on first failure.

## Post-Implementation State

After all 5 tasks:
- Shadow mode exists: `feature_flags: {"shadow_hermes_eng-ai-voice": true}`
- Both engines run on every eng-ai-voice invocation
- Field-by-field comparison logged to `shadow_comparisons` table
- Graduation query available to review readiness
- Baseline result always returned (zero risk to production)
- All existing tests pass + new shadow comparison tests

## What This Does NOT Do

1. **Switch eng-ai-voice to Hermes** — that happens after graduation criteria are met
2. **CEO agent** — that's Phase 3
3. **Discord projector** — that's Phase 3
4. **Skill candidate activation** — stub exists, not active yet
5. **Cost tracking** — estimated from iterations, not exact token counting
