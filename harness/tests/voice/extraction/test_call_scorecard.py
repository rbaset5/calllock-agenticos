"""Tests for call quality scorecard generation."""

from __future__ import annotations

from typing import Any

from voice.extraction.call_scorecard import build_call_scorecard


def make_state(**overrides: Any) -> dict[str, Any]:
    state = {
        "call_id": "test-call-123",
        "appointment_booked": False,
        "booking_attempted": False,
        "is_safety_emergency": False,
        "is_urgent_escalation": False,
    }
    state.update(overrides)
    return state


def empty_tags() -> dict[str, list[str]]:
    return {
        "HAZARD": [],
        "URGENCY": [],
        "SERVICE_TYPE": [],
        "REVENUE": [],
        "RECOVERY": [],
        "LOGISTICS": [],
        "CUSTOMER": [],
        "NON_CUSTOMER": [],
        "CONTEXT": [],
    }


def test_returns_zero_score_for_empty_state_with_no_tags() -> None:
    scorecard = build_call_scorecard(make_state(), empty_tags())

    assert scorecard["call_id"] == "test-call-123"
    assert scorecard["score"] == 0
    assert scorecard["fields"]["has_customer_name"] is False
    assert scorecard["fields"]["has_customer_phone"] is False
    assert scorecard["fields"]["has_service_address"] is False
    assert scorecard["fields"]["has_problem_description"] is False
    assert scorecard["fields"]["has_urgency"] is False
    assert scorecard["fields"]["has_booking_or_callback"] is False
    assert scorecard["fields"]["tag_count"] == 0


def test_returns_full_score_for_complete_state_with_tags() -> None:
    tags = empty_tags()
    tags["SERVICE_TYPE"] = ["REPAIR_AC"]
    tags["URGENCY"] = ["EMERGENCY_SAMEDAY"]
    tags["CUSTOMER"] = ["NEW_CUSTOMER"]

    scorecard = build_call_scorecard(
        make_state(
            customer_name="Jonas Smith",
            customer_phone="+16155551234",
            service_address="123 Main St",
            problem_description="AC not cooling",
            urgency="Urgent",
            appointment_booked=True,
        ),
        tags,
    )

    assert scorecard["score"] == 100
    assert scorecard["fields"]["has_customer_name"] is True
    assert scorecard["fields"]["has_customer_phone"] is True
    assert scorecard["fields"]["has_service_address"] is True
    assert scorecard["fields"]["has_problem_description"] is True
    assert scorecard["fields"]["has_urgency"] is True
    assert scorecard["fields"]["has_booking_or_callback"] is True
    assert scorecard["fields"]["tag_count"] == 3


def test_gives_partial_score_for_partial_data() -> None:
    tags = empty_tags()
    tags["SERVICE_TYPE"] = ["REPAIR_HEATING"]

    scorecard = build_call_scorecard(
        make_state(
            customer_name="Sarah",
            customer_phone="+16155551234",
            problem_description="Heater broken",
        ),
        tags,
    )

    assert 0 < scorecard["score"] < 100
    assert scorecard["fields"]["has_customer_name"] is True
    assert scorecard["fields"]["has_customer_phone"] is True
    assert scorecard["fields"]["has_service_address"] is False
    assert scorecard["fields"]["has_problem_description"] is True
    assert scorecard["fields"]["has_urgency"] is False
    assert scorecard["fields"]["has_booking_or_callback"] is False
    assert scorecard["fields"]["tag_count"] == 1


def test_counts_callback_as_booking_or_callback() -> None:
    scorecard = build_call_scorecard(
        make_state(end_call_reason="callback_later", callback_type="service"),
        empty_tags(),
    )
    assert scorecard["fields"]["has_booking_or_callback"] is True


def test_includes_warning_for_zero_tags() -> None:
    scorecard = build_call_scorecard(make_state(customer_name="Test"), empty_tags())
    assert "zero-tags" in scorecard["warnings"]


def test_includes_warning_for_callback_gap() -> None:
    scorecard = build_call_scorecard(
        make_state(
            customer_phone="+16155551234",
            problem_description="AC broken",
            appointment_booked=False,
        ),
        empty_tags(),
    )
    assert "callback-gap" in scorecard["warnings"]


def test_does_not_include_callback_gap_for_wrong_number() -> None:
    scorecard = build_call_scorecard(
        make_state(end_call_reason="wrong_number", appointment_booked=False),
        empty_tags(),
    )
    assert "callback-gap" not in scorecard["warnings"]


def test_does_not_include_callback_gap_when_booked() -> None:
    scorecard = build_call_scorecard(make_state(appointment_booked=True), empty_tags())
    assert "callback-gap" not in scorecard["warnings"]


def test_does_not_include_callback_gap_when_callback_created() -> None:
    scorecard = build_call_scorecard(
        make_state(end_call_reason="callback_later", callback_type="service"),
        empty_tags(),
    )
    assert "callback-gap" not in scorecard["warnings"]


def test_does_not_include_zero_tags_warning_when_tags_exist() -> None:
    tags = empty_tags()
    tags["SERVICE_TYPE"] = ["REPAIR_AC"]
    scorecard = build_call_scorecard(make_state(), tags)
    assert "zero-tags" not in scorecard["warnings"]
