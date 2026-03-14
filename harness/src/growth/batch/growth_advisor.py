from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from growth.engine.wedge_fitness import compute_and_persist_wedge_fitness
from growth.idempotency.keys import monday_snapshot_week
from growth.memory import repository as growth_repository


def run_growth_advisor_batch(
    tenant_id: str,
    *,
    source_version: str,
    wedges: list[str] | None = None,
    context: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    runtime = now or datetime.now(timezone.utc)
    wedge_list = wedges or growth_repository.list_growth_wedges(tenant_id=tenant_id) or ["hvac"]
    snapshots = [
        compute_and_persist_wedge_fitness(
            tenant_id,
            wedge,
            source_version=source_version,
            context=context or {},
            now=runtime,
        )
        for wedge in wedge_list
    ]
    unresolved_dlq = growth_repository.list_dlq_entries(tenant_id=tenant_id, unresolved_only=True)
    return {
        "tenant_id": tenant_id,
        "snapshot_week": monday_snapshot_week(runtime).isoformat(),
        "snapshots": snapshots,
        "dlq_depth": len(unresolved_dlq),
    }
