from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from db.repository import get_tenant_config, list_alerts, update_alert_and_sync_incident
from harness.alerts.notifier import notify
from harness.audit import log_audit_event


DEFAULT_ESCALATION_POLICY = {
    "open": {"high": 30, "medium": 60, "low": 120},
    "acknowledged": {"high": 120, "medium": 240, "low": 480},
}


def _parse_iso(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def resolve_escalation_policy(tenant_config: dict[str, Any] | None = None) -> dict[str, dict[str, int]]:
    policy = {
        status: dict(severities)
        for status, severities in DEFAULT_ESCALATION_POLICY.items()
    }
    overrides = (tenant_config or {}).get("alert_escalation_policy", {})
    if not isinstance(overrides, dict):
        return policy

    for status, severities in overrides.items():
        if status not in policy or not isinstance(severities, dict):
            continue
        for severity, minutes in severities.items():
            if severity not in policy[status]:
                continue
            if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or minutes < 0:
                continue
            policy[status][severity] = int(minutes)
    return policy


def _age_minutes(alert: dict[str, Any], *, now: datetime) -> int:
    reference_timestamp = alert.get("acknowledged_at") if alert.get("status") == "acknowledged" else alert.get("created_at")
    reference_time = _parse_iso(reference_timestamp)
    if reference_time is None:
        return 0
    return max(0, int((now - reference_time).total_seconds() // 60))


def auto_escalate_alerts(*, tenant_id: str | None = None, now_iso: str | None = None) -> list[dict[str, Any]]:
    now = _parse_iso(now_iso) or datetime.now(timezone.utc)
    escalated_alerts = []
    for alert in list_alerts(tenant_id=tenant_id):
        status = alert.get("status", "open")
        if status not in ("open", "acknowledged"):
            continue

        config = get_tenant_config(alert["tenant_id"]) if alert.get("tenant_id") else {}
        policy = resolve_escalation_policy(config)
        severity = alert.get("severity", "medium")
        threshold_minutes = policy.get(status, {}).get(severity)
        if threshold_minutes is None:
            continue

        age_minutes = _age_minutes(alert, now=now)
        if age_minutes < threshold_minutes:
            continue

        updated = update_alert_and_sync_incident(
            alert["id"],
            {
                "status": "escalated",
                "escalated_at": now.isoformat(),
                "escalated_by": "system:auto-escalation",
                "resolution_notes": f"Automatically escalated after {age_minutes} minutes in {status} state",
            },
        )
        updated["notification"] = notify(updated, config)
        log_audit_event(
            action_type="alert.auto_escalated",
            actor_id="system:auto-escalation",
            reason=updated["resolution_notes"],
            tenant_id=updated.get("tenant_id"),
            target_type="alert",
            target_id=updated["id"],
            payload={"threshold_minutes": threshold_minutes, "age_minutes": age_minutes, "status_before": status},
        )
        escalated_alerts.append(updated)
    return escalated_alerts
