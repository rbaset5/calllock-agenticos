"""Tests for caller classification and traffic routing."""

from __future__ import annotations

from typing import Any

import pytest

from voice.classification.traffic import derive_caller_type, derive_primary_intent, route_call


def make_state(**overrides: Any) -> dict[str, Any]:
    state = {
        "appointment_booked": False,
        "end_call_reason": None,
        "callback_type": None,
        "problem_description": None,
        "property_type": None,
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


@pytest.mark.parametrize(
    ("state", "tags", "expected"),
    [
        (make_state(problem_description="AC not cooling"), {"SERVICE_TYPE": ["REPAIR_AC"], "CUSTOMER": [], "NON_CUSTOMER": [], "HAZARD": [], "URGENCY": [], "REVENUE": [], "RECOVERY": [], "LOGISTICS": [], "CONTEXT": []}, "residential"),
        (make_state(), {"SERVICE_TYPE": [], "CUSTOMER": [], "NON_CUSTOMER": ["JOB_APPLICANT"], "HAZARD": [], "URGENCY": [], "REVENUE": [], "RECOVERY": [], "LOGISTICS": [], "CONTEXT": []}, "job_applicant"),
        (make_state(), {"SERVICE_TYPE": [], "CUSTOMER": [], "NON_CUSTOMER": ["SPAM_TELEMARKETING"], "HAZARD": [], "URGENCY": [], "REVENUE": [], "RECOVERY": [], "LOGISTICS": [], "CONTEXT": []}, "spam"),
        (make_state(), empty_tags(), "unknown"),
    ],
)
def test_derive_caller_type(
    state: dict[str, Any], tags: dict[str, list[str]], expected: str
) -> None:
    assert derive_caller_type(state, tags) == expected


@pytest.mark.parametrize(
    ("state", "tags", "expected"),
    [
        (make_state(appointment_booked=True), empty_tags(), "booking_request"),
        (make_state(callback_type="billing"), empty_tags(), "admin_billing"),
        (make_state(end_call_reason="sales_lead"), empty_tags(), "new_lead"),
        (make_state(), {"HAZARD": [], "URGENCY": [], "SERVICE_TYPE": [], "REVENUE": [], "RECOVERY": ["CALLBACK_RISK"], "LOGISTICS": [], "CUSTOMER": [], "NON_CUSTOMER": [], "CONTEXT": []}, "active_job_issue"),
        (make_state(), {"HAZARD": [], "URGENCY": [], "SERVICE_TYPE": [], "REVENUE": [], "RECOVERY": [], "LOGISTICS": [], "CUSTOMER": [], "NON_CUSTOMER": ["VENDOR_SALES"], "CONTEXT": []}, "solicitation"),
    ],
)
def test_derive_primary_intent(
    state: dict[str, Any], tags: dict[str, list[str]], expected: str
) -> None:
    assert derive_primary_intent(state, tags) == expected


@pytest.mark.parametrize(
    ("caller_type", "primary_intent", "expected_route"),
    [
        ("residential", "service", "legitimate"),
        ("job_applicant", "solicitation", "vendor"),
        ("spam", "solicitation", "spam"),
        ("unknown", "unknown", "legitimate"),
    ],
)
def test_route_call(caller_type: str, primary_intent: str, expected_route: str) -> None:
    assert route_call(caller_type, primary_intent) == expected_route
