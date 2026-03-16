from __future__ import annotations

import os
from typing import Any

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from db.repository import create_job
from harness.resilience.recovery_journal import write_recovery_entry


def _dispatch_inngest_event(event_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    endpoint = os.getenv("INNGEST_EVENT_URL")
    if not endpoint or httpx is None:
        return {"dispatched": False, "reason": "INNGEST_EVENT_URL not configured"}
    try:
        response = httpx.post(
            endpoint,
            json={"name": event_name, "data": payload},
            headers={"Authorization": f"Bearer {os.getenv('INNGEST_EVENT_KEY', '')}"} if os.getenv("INNGEST_EVENT_KEY") else {},
            timeout=10.0,
        )
        response.raise_for_status()
        return {"dispatched": True, "status_code": response.status_code}
    except Exception as exc:
        recovery_path = write_recovery_entry(
            "inngest-dispatch",
            {"event_name": event_name, "payload": payload, "error": str(exc)},
        )
        return {"dispatched": False, "reason": str(exc), "recovery_path": recovery_path}


def dispatch_job_requests(
    job_requests: list[dict[str, Any]],
    *,
    tenant_id: str,
    origin_worker_id: str,
    origin_run_id: str,
) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for request in job_requests:
        payload = {
            "tenant_id": tenant_id,
            "origin_worker_id": origin_worker_id,
            "origin_run_id": origin_run_id,
            "job_type": request.get("job_type", "async_task"),
            "status": request.get("status", "queued"),
            "idempotency_key": request["idempotency_key"],
            "payload": request.get("payload", {}),
            "source_call_id": request.get("source_call_id"),
            "supersedes_job_id": request.get("supersedes_job_id"),
            "created_by": request.get("created_by", origin_worker_id),
        }
        job = create_job(payload)
        job["dispatch"] = _dispatch_inngest_event(
            "harness/job-dispatch",
            {
                "job_id": job["id"],
                "tenant_id": tenant_id,
                "origin_run_id": origin_run_id,
                "job_type": job["job_type"],
                "payload": job["payload"],
            },
        )
        jobs.append(job)
    return jobs
