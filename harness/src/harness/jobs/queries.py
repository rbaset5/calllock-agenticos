from __future__ import annotations

from db.repository import list_jobs


def jobs_for_run(tenant_id: str, run_id: str) -> list[dict]:
    return list_jobs(tenant_id=tenant_id, run_id=run_id)
