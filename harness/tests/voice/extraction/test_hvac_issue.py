"""Tests for HVAC issue type inference."""

from __future__ import annotations

import pytest

from voice.extraction.hvac_issue import infer_hvac_issue_type


@pytest.mark.parametrize(
    ("problem_description", "transcript", "expected"),
    [
        ("water leak near the unit", None, "Leaking"),
        ("AC is not cooling at all", None, "No Cool"),
        ("no heat coming from the vents", None, "No Heat"),
        ("loud banging noise from the unit", None, "Noisy System"),
        ("musty smell from the vents", None, "Odor"),
        ("unit won't start at all", None, "Not Running"),
        ("thermostat is blank", None, "Thermostat"),
        ("need a seasonal tune-up", None, "Maintenance"),
        (None, None, None),
        ("I have a question about my bill", None, None),
        ("some problem", "water puddle inside the house", "Leaking"),
    ],
)
def test_infer_hvac_issue_type(
    problem_description: str | None, transcript: str | None, expected: str | None
) -> None:
    assert infer_hvac_issue_type(problem_description, transcript) == expected
