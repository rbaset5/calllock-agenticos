from __future__ import annotations

from growth.dlq.service import resolve_dlq_entry, write_dlq_entry
from growth.memory import repository as growth_repository


def test_dlq_entry_is_written_once_on_final_failure() -> None:
    record = write_dlq_entry(
        {
            "tenant_id": "tenant-alpha",
            "event_type": "growth/touchpoint.logged",
            "event_payload": {"touchpoint_id": "tp-final-failure"},
            "error_class": "RuntimeError",
            "error_message": "retries_exhausted",
            "retry_count": 3,
            "max_retries": 3,
            "source_version": "test",
        }
    )

    entries = growth_repository.list_dlq_entries(tenant_id="tenant-alpha", unresolved_only=True)
    assert len(entries) == 1
    assert entries[0]["id"] == record["id"]


def test_dlq_entry_can_be_resolved() -> None:
    record = write_dlq_entry(
        {
            "tenant_id": "tenant-alpha",
            "event_type": "growth/lifecycle.transitioned",
            "event_payload": {"touchpoint_id": "tp-resolve"},
            "error_class": "RuntimeError",
            "error_message": "retries_exhausted",
            "retry_count": 3,
            "max_retries": 3,
            "source_version": "test",
        }
    )

    resolved = resolve_dlq_entry(record["id"], resolution="manual", resolved_by="operator-1")

    assert resolved["resolution"] == "manual"
    assert resolved["resolved_by"] == "operator-1"
    assert resolved["resolved_at"] is not None
