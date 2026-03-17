"""Tests for urgency inference from transcript context."""

from __future__ import annotations

import pytest

from voice.extraction.urgency import infer_urgency_from_context


@pytest.mark.parametrize(
    ("problem_description", "transcript", "expected"),
    [
        ("I smell gas leak", None, "Emergency"),
        ("carbon monoxide detector going off", None, "Emergency"),
        ("smoke coming from the furnace", None, "Emergency"),
        ("water leak inside the house", None, "Urgent"),
        ("no heat at all, freezing", None, "Urgent"),
        ("no ac and it is 100 degrees", None, "Urgent"),
        ("I need an estimate for a new unit", None, "Estimate"),
        ("no rush, whenever you can get here", None, "Estimate"),
        ("need a tune-up this week", None, "Routine"),
        ("my AC is making a weird sound", None, "Routine"),
        (None, None, None),
        (None, None, None),
        ("routine issue", "gas leak detected", "Emergency"),
    ],
    ids=[
        "gas-leak",
        "carbon-monoxide",
        "smoke-fire",
        "water-leak",
        "no-heat",
        "no-ac",
        "estimate",
        "no-rush",
        "maintenance",
        "ambiguous-defaults-routine",
        "empty-input",
        "undefined-input",
        "combined-inputs",
    ],
)
def test_infer_urgency_from_context(
    problem_description: str | None, transcript: str | None, expected: str | None
) -> None:
    assert infer_urgency_from_context(problem_description, transcript) == expected
