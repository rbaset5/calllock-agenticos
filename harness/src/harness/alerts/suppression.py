from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from db.repository import list_alerts, update_alert_and_sync_incident


DEFAULT_SUPPRESSION_WINDOW_MINUTES = 60


def _parse_iso(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def resolve_suppression_window_minutes(tenant_config: dict[str, Any] | None = None) -> int:
    value = (tenant_config or {}).get("alert_suppression_window_minutes", DEFAULT_SUPPRESSION_WINDOW_MINUTES)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return DEFAULT_SUPPRESSION_WINDOW_MINUTES
    return int(value)


def suppress_duplicate_alert(
    *,
    tenant_id: str | None,
    alert_type: str,
    metrics: dict[str, Any],
    tenant_config: dict[str, Any],
    now_iso: str | None = None,
) -> dict[str, Any] | None:
    now = _parse_iso(now_iso) or datetime.now(timezone.utc)
    suppression_window = resolve_suppression_window_minutes(tenant_config)
    candidates = [
        alert
        for alert in list_alerts(tenant_id=tenant_id)
        if alert.get("alert_type") == alert_type and alert.get("status", "open") != "resolved"
    ]
    candidates.sort(
        key=lambda alert: alert.get("last_observed_at") or alert.get("created_at") or "",
        reverse=True,
    )
    if not candidates:
        return None

    candidate = candidates[0]
    reference_time = _parse_iso(candidate.get("last_observed_at") or candidate.get("created_at"))
    if reference_time is None:
        return None

    age_minutes = max(0, int((now - reference_time).total_seconds() // 60))
    if age_minutes > suppression_window:
        return None

    updated = update_alert_and_sync_incident(
        candidate["id"],
        {
            "metrics": metrics,
            "last_observed_at": now.isoformat(),
            "occurrence_count": int(candidate.get("occurrence_count", 1)) + 1,
        },
    )
    updated["suppressed_duplicate"] = True
    updated["notification"] = {
        "alert_id": updated["id"],
        "delivered": False,
        "channels": [{"channel": "suppressed", "delivered": False, "reason": "duplicate_within_suppression_window"}],
    }
    return updated
