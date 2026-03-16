"""Tests for lookup_caller tool handler."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from voice.tools.lookup_caller import lookup_caller


@pytest.fixture
def mock_db() -> MagicMock:
    """Mock database client that returns empty by default."""
    db = MagicMock()
    db.query_jobs_by_phone.return_value = []
    db.query_calls_by_phone.return_value = []
    db.query_bookings_by_phone.return_value = []
    return db


class TestLookupCallerFound:
    def test_returns_found_with_history(self, mock_db: MagicMock) -> None:
        mock_db.query_jobs_by_phone.return_value = [
            {"id": "job-1", "service_type": "AC Repair", "status": "completed", "created_at": "2026-03-10"},
        ]
        mock_db.query_calls_by_phone.return_value = [
            {"call_id": "call-1", "outcome": "booking_confirmed", "created_at": "2026-03-10"},
        ]
        mock_db.query_bookings_by_phone.return_value = [
            {"booking_id": "bk-1", "scheduled_at": "2026-03-20", "status": "confirmed"},
        ]

        result = lookup_caller(phone_number="+15125550101", db=mock_db)

        assert result["found"] is True
        assert len(result["jobs"]) == 1
        assert len(result["calls"]) == 1
        assert len(result["bookings"]) == 1

    def test_found_with_only_jobs(self, mock_db: MagicMock) -> None:
        mock_db.query_jobs_by_phone.return_value = [
            {"id": "job-1", "service_type": "Heating", "status": "completed", "created_at": "2026-03-01"},
        ]

        result = lookup_caller(phone_number="+15125550101", db=mock_db)

        assert result["found"] is True
        assert len(result["jobs"]) == 1
        assert result["calls"] == []
        assert result["bookings"] == []


class TestLookupCallerNotFound:
    def test_new_caller_returns_not_found(self, mock_db: MagicMock) -> None:
        result = lookup_caller(phone_number="+15125550101", db=mock_db)

        assert result["found"] is False
        assert result["jobs"] == []
        assert result["calls"] == []
        assert result["bookings"] == []


class TestLookupCallerLimits:
    def test_jobs_limited_to_10(self, mock_db: MagicMock) -> None:
        mock_db.query_jobs_by_phone.return_value = [
            {"id": f"job-{i}", "service_type": "AC", "status": "done", "created_at": "2026-03-01"}
            for i in range(15)
        ]

        result = lookup_caller(phone_number="+15125550101", db=mock_db)

        assert len(result["jobs"]) <= 10

    def test_calls_limited_to_5(self, mock_db: MagicMock) -> None:
        mock_db.query_calls_by_phone.return_value = [
            {"call_id": f"call-{i}", "outcome": "completed", "created_at": "2026-03-01"}
            for i in range(10)
        ]

        result = lookup_caller(phone_number="+15125550101", db=mock_db)

        assert len(result["calls"]) <= 5

    def test_bookings_limited_to_5(self, mock_db: MagicMock) -> None:
        mock_db.query_bookings_by_phone.return_value = [
            {"booking_id": f"bk-{i}", "scheduled_at": "2026-03-20", "status": "confirmed"}
            for i in range(10)
        ]

        result = lookup_caller(phone_number="+15125550101", db=mock_db)

        assert len(result["bookings"]) <= 5


class TestLookupCallerGracefulDegradation:
    def test_db_timeout_returns_not_found(self, mock_db: MagicMock) -> None:
        mock_db.query_jobs_by_phone.side_effect = TimeoutError("DB timeout")
        mock_db.query_calls_by_phone.side_effect = TimeoutError("DB timeout")
        mock_db.query_bookings_by_phone.side_effect = TimeoutError("DB timeout")

        result = lookup_caller(phone_number="+15125550101", db=mock_db)

        assert result["found"] is False

    def test_db_connection_error_returns_not_found(self, mock_db: MagicMock) -> None:
        mock_db.query_jobs_by_phone.side_effect = ConnectionError("DB unreachable")
        mock_db.query_calls_by_phone.side_effect = ConnectionError("DB unreachable")
        mock_db.query_bookings_by_phone.side_effect = ConnectionError("DB unreachable")

        result = lookup_caller(phone_number="+15125550101", db=mock_db)

        assert result["found"] is False

    def test_partial_db_failure_returns_available_data(self, mock_db: MagicMock) -> None:
        """If jobs query works but calls/bookings fail, return what we got."""
        mock_db.query_jobs_by_phone.return_value = [
            {"id": "job-1", "service_type": "AC", "status": "done", "created_at": "2026-03-01"},
        ]
        mock_db.query_calls_by_phone.side_effect = TimeoutError("DB timeout")
        mock_db.query_bookings_by_phone.side_effect = TimeoutError("DB timeout")

        result = lookup_caller(phone_number="+15125550101", db=mock_db)

        assert result["found"] is True
        assert len(result["jobs"]) == 1
        assert result["calls"] == []
        assert result["bookings"] == []

    def test_generic_exception_returns_not_found(self, mock_db: MagicMock) -> None:
        mock_db.query_jobs_by_phone.side_effect = RuntimeError("Unexpected")
        mock_db.query_calls_by_phone.side_effect = RuntimeError("Unexpected")
        mock_db.query_bookings_by_phone.side_effect = RuntimeError("Unexpected")

        result = lookup_caller(phone_number="+15125550101", db=mock_db)

        assert result["found"] is False
