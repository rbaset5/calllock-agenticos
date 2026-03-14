from __future__ import annotations

from growth.memory import repository as growth_repository


def write_dlq_entry(payload: dict[str, object]) -> dict[str, object]:
    return growth_repository.insert_dlq_entry(payload)


def resolve_dlq_entry(entry_id: str, *, resolution: str, resolved_by: str) -> dict[str, object]:
    return growth_repository.resolve_dlq_entry(
        entry_id,
        {"resolution": resolution, "resolved_by": resolved_by},
    )
