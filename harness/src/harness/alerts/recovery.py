from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from db.repository import get_tenant_config, list_alerts, update_alert_and_sync_incident
from harness.audit import log_audit_event


DEFAULT_RECOVERY_COOLDOWN_MINUTES = 15


def _parse_iso(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def resolve_recovery_cooldown_minutes(tenant_config: dict[str, Any] | None = None) -> int:
    value = (tenant_config or {}).get("alert_recovery_cooldown_minutes", DEFAULT_RECOVERY_COOLDOWN_MINUTES)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return DEFAULT_RECOVERY_COOLDOWN_MINUTES
    return int(value)


def auto_resolve_recovered_alerts(
    *,
    metrics: dict[str, Any],
    thresholds: dict[str, float],
    tenant_id: str | None = None,
    tenant_config: dict[str, Any] | None = None,
    now_iso: str | None = None,
) -> list[dict[str, Any]]:
    now = _parse_iso(now_iso) or datetime.now(timezone.utc)
    config = tenant_config or (get_tenant_config(tenant_id) if tenant_id else {})
    cooldown_minutes = resolve_recovery_cooldown_minutes(config)
    resolved_alerts = []

    for alert in list_alerts(tenant_id=tenant_id):
        if alert.get("status", "open") == "resolved":
            continue
        alert_type = alert.get("alert_type")
        if alert_type not in thresholds or alert_type not in metrics:
            continue
        if metrics[alert_type] >= thresholds[alert_type]:
            continue

        last_observed_at = _parse_iso(alert.get("last_observed_at") or alert.get("created_at"))
        if last_observed_at is None:
            continue
        quiet_minutes = max(0, int((now - last_observed_at).total_seconds() // 60))
        if quiet_minutes < cooldown_minutes:
            continue

        updated = update_alert_and_sync_incident(
            alert["id"],
            {
                "status": "resolved",
                "resolved_at": now.isoformat(),
                "resolved_by": "system:auto-recovery",
                "resolution_notes": f"Automatically resolved after {quiet_minutes} minutes below threshold",
                "metrics": {
                    **metrics,
                    "applied_thresholds": thresholds,
                    "threshold": thresholds[alert_type],
                    "recovered_value": metrics[alert_type],
                    "cooldown_minutes": cooldown_minutes,
                },
            },
        )
        log_audit_event(
            action_type="alert.auto_resolved",
            actor_id="system:auto-recovery",
            reason=updated["resolution_notes"],
            tenant_id=updated.get("tenant_id"),
            target_type="alert",
            target_id=updated["id"],
            payload={"quiet_minutes": quiet_minutes, "alert_type": alert_type},
        )
        resolved_alerts.append(updated)

    return resolved_alerts
