"""Regression tests for live Supabase caller-history lookups."""

from __future__ import annotations

import pytest

from db import supabase_repository


def test_caller_history_uses_call_records_when_optional_sources_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = [
        {
            "tenant_id": "tenant-ace-001",
            "phone_number": "+15125550101",
            "extracted_fields": {"customer_name": "John Smith"},
        }
    ]
    requested_tables: list[str] = []

    def fake_request(method: str, table: str, **kwargs: object) -> list[dict[str, object]]:
        requested_tables.append(table)
        if table == "call_records":
            return calls
        raise RuntimeError(f"schema mismatch for {table}")

    monkeypatch.setattr(supabase_repository, "_request", fake_request)

    result = supabase_repository.get_caller_history("tenant-ace-001", "+15125550101")

    assert requested_tables == ["call_records", "jobs", "bookings"]
    assert result == {"jobs": [], "calls": calls, "bookings": []}


def test_caller_history_surfaces_call_records_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(method: str, table: str, **kwargs: object) -> list[dict[str, object]]:
        raise TimeoutError(f"{table} timed out")

    monkeypatch.setattr(supabase_repository, "_request", fake_request)

    with pytest.raises(TimeoutError, match="call_records timed out"):
        supabase_repository.get_caller_history("tenant-ace-001", "+15125550101")
