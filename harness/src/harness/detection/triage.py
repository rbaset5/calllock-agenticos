from __future__ import annotations

from typing import Any


_SEVERITIES = {"low", "medium", "high", "critical"}


def build_detection_event(
    *,
    monitor_id: str,
    tenant_id: str | None,
    severity: str,
    raw_context: dict[str, object] | None = None,
) -> dict[str, object]:
    normalized_monitor_id = str(monitor_id)
    normalized_severity = _normalize_severity(severity)
    return {
        "source": "alerts",
        "surface": "voice" if normalized_monitor_id.startswith("voice_") else "product",
        "signal_type": normalized_monitor_id,
        "severity": normalized_severity,
        "tenant_id": tenant_id,
        "dedupe_key": f"{tenant_id or 'global'}:{normalized_monitor_id}",
        "raw_context": raw_context or {},
    }


def assess_detection_event(
    event: dict[str, object],
    *,
    has_open_issue: bool,
    in_flight_fix: bool,
) -> dict[str, str]:
    if has_open_issue or in_flight_fix:
        return {"outcome": "stand_down", "reason": "matching_issue_already_active"}

    signal_type = str(event.get("signal_type") or "")
    severity = _normalize_severity(event.get("severity"))
    if signal_type == "voice_safety_emergency_mismatch_signal":
        return {"outcome": "escalate", "reason": "safety_signal"}
    if severity == "low":
        return {"outcome": "suppress", "reason": "below_operational_threshold"}
    return {"outcome": "investigate", "reason": "new_meaningful_signal"}


def decide_notification(
    event: dict[str, object],
    assessment: dict[str, object] | None = None,
) -> dict[str, object]:
    decision = assessment or event
    outcome = str(decision.get("outcome") or event.get("outcome") or "investigate")
    severity = _normalize_severity(event.get("severity"))

    if outcome == "stand_down":
        return {"notification_outcome": "silent_stand_down", "channels": []}
    if outcome == "escalate" and severity == "critical":
        return {"notification_outcome": "founder_notify", "channels": ["dashboard", "email"]}
    if outcome == "escalate":
        return {"notification_outcome": "operator_notify", "channels": ["dashboard", "email"]}
    return {"notification_outcome": "internal_only", "channels": ["dashboard"]}


def _normalize_severity(value: Any) -> str:
    if not isinstance(value, str):
        return "medium"
    normalized = value.strip().lower()
    return normalized if normalized in _SEVERITIES else "medium"
