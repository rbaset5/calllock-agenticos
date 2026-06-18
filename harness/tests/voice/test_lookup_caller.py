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

    def test_clean_prior_full_name_sets_first_name_contract(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.return_value = {
            "jobs": [],
            "calls": [
                {
                    "call_id": "call-1",
                    "created_at": "2026-03-10",
                    "extracted_fields": {"customer_name": "John Smith"},
                }
            ],
            "bookings": [],
        }

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert result["known_caller"] == {
            "first_name": "John",
            "full_name": "John Smith",
            "confidence": "high",
            "source": "call_records",
            "last_seen_at": "2026-03-10",
        }
        assert result["customerName"] == "John"
        assert result["zipCode"] == ""
        assert result["lookupStatus"] == "found"

    def test_repeated_matching_first_name_is_high_confidence(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.return_value = {
            "jobs": [{"id": "job-1", "customer_name": "sarah", "created_at": "2026-03-09"}],
            "calls": [
                {
                    "call_id": "call-1",
                    "created_at": "2026-03-10",
                    "extracted_fields": {"customer_name": " Sarah "},
                }
            ],
            "bookings": [],
        }

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert result["known_caller"]["first_name"] == "Sarah"
        assert result["known_caller"]["confidence"] == "high"
        assert result["customerName"] == "Sarah"

    def test_conflicting_names_suppress_spoken_name(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.return_value = {
            "jobs": [],
            "calls": [
                {"call_id": "call-1", "created_at": "2026-03-10", "extracted_fields": {"customer_name": "John Smith"}},
                {"call_id": "call-2", "created_at": "2026-03-09", "extracted_fields": {"customer_name": "Maria Smith"}},
            ],
            "bookings": [],
        }

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert result["known_caller"] is None
        assert result["customerName"] == ""
        assert result["lookupStatus"] == "found"

    @pytest.mark.parametrize(
        "customer_name",
        [
            "Chris from",
            "ACE Cooling",
            "unknown",
            "N/A",
            "Mr. Smith",
            "O'Neil",
            "A",
            "",
        ],
    )
    def test_junk_or_ambiguous_names_do_not_get_spoken(self, mock_db: MagicMock, customer_name: str) -> None:
        mock_db.get_caller_history.return_value = {
            "jobs": [],
            "calls": [{"call_id": "call-1", "extracted_fields": {"customer_name": customer_name}}],
            "bookings": [],
        }

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert result["known_caller"] is None
        assert result["customerName"] == ""

    def test_malformed_extracted_fields_do_not_break_lookup(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.return_value = {
            "jobs": [],
            "calls": [{"call_id": "call-1", "extracted_fields": None}],
            "bookings": [],
        }

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert result["found"] is True
        assert result["known_caller"] is None
        assert result["customerName"] == ""

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
        assert result["known_caller"] is None
        assert result["customerName"] == ""
        assert result["zipCode"] == ""
        assert result["lookupStatus"] == "not_found"


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
        assert result["known_caller"] is None
        assert result["customerName"] == ""
        assert result["lookupStatus"] == "error"

    def test_db_connection_error_returns_not_found(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.side_effect = ConnectionError("DB unreachable")

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert result["found"] is False
        assert result["known_caller"] is None
        assert result["customerName"] == ""
        assert result["lookupStatus"] == "error"

    def test_generic_exception_returns_not_found(self, mock_db: MagicMock) -> None:
        mock_db.get_caller_history.side_effect = RuntimeError("Unexpected")

        result = lookup_caller(phone_number="+15125550101", tenant_id=_TENANT, db=mock_db)

        assert result["found"] is False
        assert result["known_caller"] is None
        assert result["customerName"] == ""
        assert result["lookupStatus"] == "error"
