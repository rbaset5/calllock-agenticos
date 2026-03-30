"""Tests for CEO outbound tools."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from outbound.ceo_tools import (
    outbound_funnel_summary,
    outbound_prospect_lookup,
    outbound_signal_effectiveness,
    outbound_metro_performance,
)


NOW = datetime.now(timezone.utc)
RECENT_DISCOVERED_AT = (NOW - timedelta(days=2)).isoformat().replace("+00:00", "Z")
RECENT_CALLED_AT = (NOW - timedelta(days=1)).isoformat().replace("+00:00", "Z")


MOCK_PROSPECTS = [
    {
        "id": "p1",
        "business_name": "Johnson HVAC",
        "phone": "(602) 555-0142",
        "phone_normalized": "+16025550142",
        "metro": "Phoenix",
        "trade": "hvac",
        "stage": "interested",
        "total_score": 92,
        "score_tier": "a_lead",
        "discovered_at": RECENT_DISCOVERED_AT,
    },
    {
        "id": "p2",
        "business_name": "Desert Air",
        "phone": "(480) 555-0198",
        "phone_normalized": "+14805550198",
        "metro": "Phoenix",
        "trade": "hvac",
        "stage": "disqualified",
        "total_score": 25,
        "score_tier": "disqualified",
        "disqualification_reason": "Franchise",
        "discovered_at": RECENT_DISCOVERED_AT,
    },
    {
        "id": "p3",
        "business_name": "Cool Breeze",
        "phone": "(312) 555-0234",
        "phone_normalized": "+13125550234",
        "metro": "Chicago",
        "trade": "plumbing",
        "stage": "call_ready",
        "total_score": 71,
        "score_tier": "b_lead",
        "discovered_at": RECENT_DISCOVERED_AT,
    },
]

MOCK_CALLS = [
    {
        "prospect_id": "p1",
        "outcome": "answered_interested",
        "called_at": RECENT_CALLED_AT,
        "demo_scheduled": True,
        "call_hook_used": "after_hours_no_answer",
    },
    {
        "prospect_id": "p2",
        "outcome": "answered_not_interested",
        "called_at": RECENT_CALLED_AT,
        "notes": "Uses ServiceTitan",
    },
]

MOCK_SIGNALS = {
    "p1": [
        {"signal_type": "paid_demand", "score": 85, "signal_tier": 1},
        {"signal_type": "after_hours_behavior", "score": 90, "signal_tier": 1},
    ],
    "p2": [
        {"signal_type": "paid_demand", "score": 60, "signal_tier": 1},
    ],
}


@patch("outbound.ceo_tools.store")
def test_funnel_summary(mock_store):
    mock_store.list_outbound_prospects.return_value = MOCK_PROSPECTS
    mock_store.list_outbound_calls.return_value = MOCK_CALLS

    result = outbound_funnel_summary(days=7)
    assert result["total_prospects"] == 3
    assert result["calls_this_period"] == 2
    assert result["demos_scheduled"] == 1
    assert "interested" in result["pipeline_by_stage"]


@patch("outbound.ceo_tools.store")
def test_prospect_lookup_by_name(mock_store):
    mock_store.list_outbound_prospects.return_value = MOCK_PROSPECTS
    mock_store.list_prospect_signals.return_value = MOCK_SIGNALS["p1"]
    mock_store.list_outbound_calls.return_value = [MOCK_CALLS[0]]
    mock_store.list_call_tests.return_value = []

    result = outbound_prospect_lookup(business_name="Johnson")
    assert result["found"] is True
    assert result["prospect"]["business_name"] == "Johnson HVAC"
    assert len(result["signals"]) == 2
    assert len(result["calls"]) == 1


@patch("outbound.ceo_tools.store")
def test_prospect_lookup_not_found(mock_store):
    mock_store.list_outbound_prospects.return_value = MOCK_PROSPECTS

    result = outbound_prospect_lookup(business_name="Nonexistent")
    assert result["found"] is False


@patch("outbound.ceo_tools.store")
def test_signal_effectiveness(mock_store):
    mock_store.list_outbound_calls.return_value = MOCK_CALLS
    mock_store.list_outbound_prospects.return_value = MOCK_PROSPECTS
    mock_store.list_prospect_signals.side_effect = lambda prospect_id=None: MOCK_SIGNALS.get(prospect_id, [])

    result = outbound_signal_effectiveness()
    effectiveness = result["signal_effectiveness"]
    assert len(effectiveness) > 0
    # paid_demand appears in both p1 (interested) and p2 (not interested)
    paid = next(e for e in effectiveness if e["signal"] == "paid_demand")
    assert paid["total_calls"] == 2
    assert paid["positive_outcomes"] == 1


@patch("outbound.ceo_tools.store")
def test_metro_performance(mock_store):
    mock_store.list_outbound_calls.return_value = MOCK_CALLS
    mock_store.list_outbound_prospects.return_value = MOCK_PROSPECTS

    result = outbound_metro_performance()
    metros = result["metro_performance"]
    phoenix = next(m for m in metros if m["metro"] == "Phoenix")
    assert phoenix["total_calls"] == 2
    assert phoenix["total_prospects"] == 2
