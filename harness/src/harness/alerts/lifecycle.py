from __future__ import annotations


ALERT_TRANSITIONS = {
    "open": {"acknowledged", "escalated", "resolved"},
    "acknowledged": {"escalated", "resolved"},
    "escalated": {"acknowledged", "resolved"},
    "resolved": set(),
}


def validate_alert_transition(current_status: str, target_status: str) -> None:
    allowed = ALERT_TRANSITIONS.get(current_status)
    if allowed is None:
        raise ValueError(f"Unknown alert status: {current_status}")
    if target_status not in allowed:
        raise ValueError(f"Invalid alert transition: {current_status} -> {target_status}")
