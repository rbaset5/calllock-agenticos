"""Tests for the HVAC taxonomy tag classifier."""

from __future__ import annotations

from typing import Any

import pytest

from voice.extraction.tags import classify_call


def make_state(**overrides: Any) -> dict[str, Any]:
    state = {
        "call_id": "test",
        "appointment_booked": False,
        "booking_attempted": False,
        "is_safety_emergency": False,
        "is_urgent_escalation": False,
    }
    state.update(overrides)
    return state


@pytest.mark.parametrize(
    ("transcript", "category", "expected_tag"),
    [
        ("I smell gas in my kitchen, rotten egg smell", "HAZARD", "GAS_LEAK"),
        ("carbon monoxide detector is going off", "HAZARD", "CO_EVENT"),
        ("I want a quote on a new system", "REVENUE", "HOT_LEAD"),
    ],
)
def test_detects_expected_tag_from_transcript(
    transcript: str, category: str, expected_tag: str
) -> None:
    tags = classify_call(make_state(), transcript)
    assert expected_tag in tags[category]


def test_auto_upgrades_urgency_for_hazards() -> None:
    tags = classify_call(make_state(), "there is a gas smell, rotten egg smell")
    assert "CRITICAL_EVACUATE" in tags["URGENCY"]


def test_detects_service_type_tags() -> None:
    tags = classify_call(make_state(), "my air conditioner broken, blowing warm air")
    assert any(tag.startswith("REPAIR_") for tag in tags["SERVICE_TYPE"])


def test_returns_empty_arrays_for_empty_transcript() -> None:
    tags = classify_call(make_state())
    assert tags["HAZARD"] == []
    assert tags["SERVICE_TYPE"] == []


def test_does_not_return_hazard_tags_for_routine_maintenance() -> None:
    tags = classify_call(make_state(), "I need a seasonal tune-up for my AC")
    assert tags["HAZARD"] == []


def test_detects_non_customer_wrong_number_from_end_call_reason() -> None:
    tags = classify_call(make_state(end_call_reason="wrong_number"))
    assert "WRONG_NUMBER" in tags["NON_CUSTOMER"]


def test_detects_customer_tags_from_state_properties() -> None:
    tags = classify_call(make_state(property_type="commercial"))
    assert "COMMERCIAL_ACCT" in tags["CUSTOMER"]


def test_is_negation_aware_for_gas_smell() -> None:
    tags = classify_call(make_state(), "any gas smell? no gas smell reported")
    assert "GAS_LEAK" not in tags["HAZARD"]


@pytest.mark.parametrize(
    ("state_urgency", "transcript", "expected_tag"),
    [
        ("Urgent", "I need someone to come take a look at my unit", "URGENT_24HR"),
        ("Emergency", "The system is not working", "EMERGENCY_SAMEDAY"),
    ],
)
def test_emits_urgency_from_state_when_transcript_has_no_keyword_match(
    state_urgency: str, transcript: str, expected_tag: str
) -> None:
    tags = classify_call(make_state(urgency=state_urgency), transcript)
    assert expected_tag in tags["URGENCY"]


def test_does_not_duplicate_urgency_tags() -> None:
    tags = classify_call(
        make_state(urgency="Urgent"),
        "the system is barely working and running constantly",
    )
    assert tags["URGENCY"].count("URGENT_24HR") == 1


@pytest.mark.parametrize(
    ("transcript", "expected_tag"),
    [
        ("Agent: How can I help?\nUser: My AC stopped working this morning.", "DURATION_ACUTE"),
        ("Agent: What happened?\nUser: Started acting up yesterday.", "DURATION_RECENT"),
        ("Agent: How long?\nUser: Been going on a couple weeks now.", "DURATION_ONGOING"),
    ],
)
def test_emits_duration_tags_from_transcript(transcript: str, expected_tag: str) -> None:
    tags = classify_call(make_state(), transcript)
    assert expected_tag in tags["CONTEXT"]


def test_does_not_emit_duration_tag_without_temporal_phrase() -> None:
    tags = classify_call(make_state(), "Agent: How can I help?\nUser: My AC is broken.")
    assert [tag for tag in tags["CONTEXT"] if tag.startswith("DURATION_")] == []


def test_uses_problem_duration_category_from_state_over_transcript() -> None:
    tags = classify_call(
        make_state(problem_duration_category="ongoing"),
        "Agent: Hi.\nUser: Just happened this morning.",
    )
    assert "DURATION_ONGOING" in tags["CONTEXT"]
    assert "DURATION_ACUTE" not in tags["CONTEXT"]


@pytest.mark.parametrize(
    ("problem_description", "transcript"),
    [
        ("AC heating HVAC unit issue", "report issue with my AC heating HVAC unit"),
        ("my ac unit stopped working", "my ac unit stopped working"),
        ("hvac issue reported", "I have a hvac issue"),
    ],
)
def test_detects_repair_ac_from_common_phrasings(
    problem_description: str, transcript: str
) -> None:
    tags = classify_call(make_state(problem_description=problem_description), transcript)
    assert "REPAIR_AC" in tags["SERVICE_TYPE"]
