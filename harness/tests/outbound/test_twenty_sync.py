"""Tests for Twenty CRM sync."""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import json

from outbound.twenty_sync import (
    sync_prospect_to_crm,
    sync_call_outcome_to_crm,
    sync_stage_update_to_crm,
    _extract_id,
)


def test_extract_id_data_wrapper():
    assert _extract_id({"data": {"id": "abc"}}) == "abc"


def test_extract_id_flat():
    assert _extract_id({"id": "xyz"}) == "xyz"


def test_extract_id_none():
    assert _extract_id(None) is None
    assert _extract_id({}) is None


def test_sync_prospect_skips_when_no_config():
    """Sync gracefully skips when TWENTY_BASE_URL is not set."""
    result = sync_prospect_to_crm(
        {"business_name": "Test HVAC", "phone": "555-1234"},
        [{"signal_type": "paid_demand", "score": 85}],
    )
    assert result["synced"] is False
    assert "error" in result


@patch("outbound.twenty_sync._twenty_request")
def test_sync_prospect_creates_company_and_note(mock_request):
    mock_request.side_effect = [
        {"data": {"id": "company-123"}},  # POST /companies
        {"data": {"id": "note-456"}},     # POST /notes
        {},                                # POST /noteTargets
    ]

    prospect = {
        "business_name": "Johnson HVAC",
        "website": "johnsonhvac.com",
        "metro": "Phoenix",
        "phone": "(602) 555-0142",
        "total_score": 92,
        "tier": "a_lead",
        "trade": "hvac",
        "source": "leads_db",
    }
    signals = [
        {"signal_type": "paid_demand", "score": 85},
        {"signal_type": "after_hours_behavior", "score": 90},
    ]

    result = sync_prospect_to_crm(prospect, signals)
    assert result["synced"] is True
    assert result["twenty_company_id"] == "company-123"
    assert mock_request.call_count == 3


@patch("outbound.twenty_sync._twenty_request")
def test_sync_call_outcome_creates_note(mock_request):
    mock_request.side_effect = [
        {"data": {"id": "note-789"}},  # POST /notes
        {},                             # POST /noteTargets
    ]

    prospect = {"business_name": "Johnson HVAC"}
    call_record = {
        "outcome": "voicemail_left",
        "called_at": "2026-03-22T10:00:00Z",
        "notes": "Left message about after-hours coverage",
    }

    result = sync_call_outcome_to_crm(prospect, call_record, "company-123")
    assert result["synced"] is True
    assert result["note_created"] is True


@patch("outbound.twenty_sync._twenty_request")
def test_sync_interested_creates_opportunity(mock_request):
    mock_request.side_effect = [
        {"data": {"id": "note-789"}},  # POST /notes
        {},                             # POST /noteTargets
        {"data": {"id": "opp-111"}},   # POST /opportunities
    ]

    prospect = {"business_name": "Johnson HVAC"}
    call_record = {
        "outcome": "answered_interested",
        "called_at": "2026-03-22T10:00:00Z",
        "demo_scheduled": True,
    }

    result = sync_call_outcome_to_crm(prospect, call_record, "company-123")
    assert result["synced"] is True
    # Verify opportunity was created
    assert mock_request.call_count == 3
    opp_call = mock_request.call_args_list[2]
    assert opp_call[0][0] == "POST"
    assert opp_call[0][1] == "opportunities"


@patch("outbound.twenty_sync._twenty_request")
def test_sync_disqualified_creates_note(mock_request):
    mock_request.side_effect = [
        {"data": {"id": "note-999"}},  # POST /notes
        {},                             # POST /noteTargets
    ]

    prospect = {
        "business_name": "Bad Lead Inc",
        "disqualification_reason": "Franchise, not owner-operated",
    }

    result = sync_stage_update_to_crm(prospect, "disqualified", "company-123")
    assert result["synced"] is True


def test_sync_outcome_skips_without_company_id():
    result = sync_call_outcome_to_crm({}, {}, "")
    assert result["synced"] is False

    result = sync_stage_update_to_crm({}, "disqualified", "")
    assert result["synced"] is False
