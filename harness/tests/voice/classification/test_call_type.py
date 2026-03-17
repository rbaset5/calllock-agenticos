"""Tests for urgency-to-dashboard mapping."""

from __future__ import annotations

import pytest

from voice.classification.call_type import map_urgency_to_dashboard


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"urgency_tier": "LifeSafety"}, "emergency"),
        ({"urgency_tier": "Urgent"}, "high"),
        ({"urgency_tier": "Routine"}, "medium"),
        ({"urgency_tier": "Estimate"}, "low"),
        ({"end_call_reason": "safety_emergency"}, "emergency"),
        ({"end_call_reason": "urgent_escalation"}, "high"),
        ({"urgency_level": "Emergency"}, "emergency"),
        ({"urgency_level": "Urgent"}, "high"),
        ({"urgency_level": "Routine"}, "medium"),
        ({"urgency_level": "Estimate"}, "low"),
        ({"urgency_tier": "LifeSafety", "urgency_level": "Routine"}, "emergency"),
        ({}, "low"),
        ({"urgency_tier": "Estimate", "end_call_reason": "safety_emergency"}, "emergency"),
    ],
)
def test_map_urgency_to_dashboard(payload: dict[str, str], expected: str) -> None:
    assert map_urgency_to_dashboard(**payload) == expected
