"""Tests for revenue tier classification."""

from __future__ import annotations

from typing import Any

import pytest

from voice.classification.revenue import estimate_revenue


def make_state(**overrides: Any) -> dict[str, Any]:
    state = {"call_id": "call-123"}
    state.update(overrides)
    return state


@pytest.mark.parametrize(
    ("state", "transcript", "expected_tier", "expected_signal"),
    [
        (make_state(problem_description="Need a new unit", equipment_age="16 years old"), None, "replacement", "16+ years old"),
        (make_state(problem_description="compressor is dead"), None, "major_repair", "Major component: compressor"),
        (make_state(problem_description="blower motor failed"), None, "standard_repair", "Component: motor"),
        (make_state(problem_description="need seasonal maintenance"), None, "minor", "Service: maintenance"),
        (make_state(problem_description="system not working"), None, "diagnostic", "Insufficient signal"),
    ],
)
def test_estimate_revenue(
    state: dict[str, Any],
    transcript: str | None,
    expected_tier: str,
    expected_signal: str,
) -> None:
    result = estimate_revenue(state, transcript)
    assert result["tier"] == expected_tier
    assert expected_signal in result["signals"]


def test_replacement_wins_over_standard_repair_when_r22_present() -> None:
    result = estimate_revenue(
        make_state(problem_description="needs refrigerant recharge", equipment_age="12 years old"),
        "This is an r-22 system",
    )
    assert result["tier"] == "replacement"
    assert "R-22/Freon system" in result["signals"]
