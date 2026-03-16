"""Urgency mapping helpers for dashboard display."""

from __future__ import annotations


def map_urgency_to_dashboard(
    urgency_tier: str | None = None,
    urgency_level: str | None = None,
    end_call_reason: str | None = None,
) -> str:
    if end_call_reason == "safety_emergency":
        return "emergency"
    if end_call_reason == "urgent_escalation":
        return "high"

    if urgency_tier:
        tier_map = {
            "LifeSafety": "emergency",
            "Urgent": "high",
            "Routine": "medium",
            "Estimate": "low",
        }
        return tier_map.get(urgency_tier, "low")

    if urgency_level:
        level_map = {
            "Emergency": "emergency",
            "Urgent": "high",
            "Routine": "medium",
            "Estimate": "low",
        }
        return level_map.get(urgency_level, "low")

    return "low"


__all__ = ["map_urgency_to_dashboard"]
