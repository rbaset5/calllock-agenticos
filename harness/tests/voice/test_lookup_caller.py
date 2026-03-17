"""Tests for lookup_caller tool handler."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from voice.tools.lookup_caller import lookup_caller

_TENANT = "tenant-ace-001"


@pytest.fixture
def mock_db() -> MagicMock:
    """Mock database client that returns empty caller history by default."""
    db = MagicMock()
    db.get_caller_history.return_value = {"jobs": [], "calls": [], "bookings": []}
    return db


class TestLookupCallerFound:
    def test_returns_found_with_history(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.return_value = {
            "jobs": [{"id": "job-1", "service_type": "AC Repair", "status": "completed", "created_at": "2026-03-10"}],
            "calls": [{"call_id": "call-1", "outcome": "booking_confirmed", "created_at": "2026-03-10"}],
            "bookings": [{"booking_id": "bk-1", "scheduled_at": "2026-03-20", "status": "confirmed"}],
        }

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert result["found"] is True
        assert len(result["jobs"]) == 1
        assert len(result["calls"]) == 1
        assert len(result["bookings"]) == 1
        mock_db.get_caller_history.assert_called_once_with(_TENANT, "+15125550101")

    def test_found_with_only_jobs(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.return_value = {
            "jobs": [{"id": "job-1", "service_type": "Heating", "status": "completed", "created_at": "2026-03-01"}],
            "calls": [],
            "bookings": [],
        }

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert result["found"] is True
        assert len(result["jobs"]) == 1
        assert result["calls"] == []
        assert result["bookings"] == []


class TestLookupCallerNotFound:
    def test_new_caller_returns_not_found(self, mock_db: MagicMock) -> None:
        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert result["found"] is False
        assert result["jobs"] == []
        assert result["calls"] == []
        assert result["bookings"] == []


class TestLookupCallerLimits:
    def test_jobs_limited_to_10(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.return_value = {
            "jobs": [{"id": f"job-{i}", "service_type": "AC", "status": "done", "created_at": "2026-03-01"} for i in range(15)],
            "calls": [],
            "bookings": [],
        }

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert len(result["jobs"]) <= 10

    def test_calls_limited_to_5(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.return_value = {
            "jobs": [],
            "calls": [{"call_id": f"call-{i}", "outcome": "completed", "created_at": "2026-03-01"} for i in range(10)],
            "bookings": [],
        }

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert len(result["calls"]) <= 5

    def test_bookings_limited_to_5(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.return_value = {
            "jobs": [],
            "calls": [],
            "bookings": [{"booking_id": f"bk-{i}", "scheduled_at": "2026-03-20", "status": "confirmed"} for i in range(10)],
        }

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert len(result["bookings"]) <= 5


class TestLookupCallerGracefulDegradation:
    def test_db_timeout_returns_not_found(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.side_effect = TimeoutError("DB timeout")

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert result["found"] is False

    def test_db_connection_error_returns_not_found(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.side_effect = ConnectionError("DB unreachable")

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert result["found"] is False

    def test_generic_exception_returns_not_found(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.side_effect = RuntimeError("Unexpected")

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert result["found"] is False
