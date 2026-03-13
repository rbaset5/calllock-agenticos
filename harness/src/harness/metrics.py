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
