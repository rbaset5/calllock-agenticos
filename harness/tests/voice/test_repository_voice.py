"""Tests for voice CRUD operations in the repository layer."""

from __future__ import annotations

import pytest

from db.local_repository import reset_local_state
from db import repository


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_local_state()


class TestInsertCallRecord:
    def test_insert_creates_record(self) -> None:
        result = repository.insert_call_record(
            tenant_id="tenant-ace-001",
            call_id="call-001",
            retell_call_id="ret-001",
            raw_payload={"transcript": "hello"},
        )

        assert result["call_id"] == "call-001"
        assert result["retell_call_id"] == "ret-001"
        assert result["tenant_id"] == "tenant-ace-001"
        assert result["extraction_status"] == "pending"

    def test_duplicate_insert_returns_none(self) -> None:
        repository.insert_call_record(
            tenant_id="tenant-ace-001",
            call_id="call-001",
            retell_call_id="ret-001",
            raw_payload={"transcript": "hello"},
        )

        result = repository.insert_call_record(
            tenant_id="tenant-ace-001",
            call_id="call-001",
            retell_call_id="ret-001",
            raw_payload={"transcript": "hello again"},
        )

        assert result is None


class TestUpdateCallRecordExtraction:
    def test_updates_extracted_fields(self) -> None:
        repository.insert_call_record(
            tenant_id="tenant-ace-001",
            call_id="call-001",
            retell_call_id="ret-001",
            raw_payload={},
        )

        result = repository.update_call_record_extraction(
            tenant_id="tenant-ace-001",
            call_id="call-001",
            extracted_fields={
                "customer_name": "John Smith",
                "urgency_tier": "urgent",
                "quality_score": 75.5,
                "tags": ["AC_NOT_COOLING"],
                "route": "legitimate",
                "extraction_status": "complete",
            },
        )

        assert result["extraction_status"] == "complete"
        assert result["extracted_fields"]["customer_name"] == "John Smith"

    def test_missing_record_raises(self) -> None:
        with pytest.raises(KeyError):
            repository.update_call_record_extraction(
                tenant_id="tenant-ace-001",
                call_id="nonexistent",
                extracted_fields={"extraction_status": "complete"},
            )


class TestGetCallerHistory:
    def test_returns_empty_for_new_caller(self) -> None:
        result = repository.get_caller_history(
            tenant_id="tenant-ace-001",
            phone="+15125550101",
        )

        assert result["jobs"] == []
        assert result["calls"] == []
        assert result["bookings"] == []


class TestGetVoiceApiKeys:
    def test_returns_empty_list(self) -> None:
        result = repository.get_voice_api_keys()
        assert result == []
