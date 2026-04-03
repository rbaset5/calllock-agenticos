from __future__ import annotations

from typing import Any

from db.repository import list_alerts, list_incidents


VISIBLE_NOTIFICATION_OUTCOMES = {"operator_notify", "founder_notify"}


def build_detection_posture(*, tenant_id: str | None = None) -> dict[str, object]:
    alerts = list_alerts(tenant_id=tenant_id)
    incidents = list_incidents(tenant_id=tenant_id)
    alert_map = {
        alert["id"]: alert
        for alert in alerts
        if isinstance(alert, dict) and isinstance(alert.get("id"), str)
    }

    active_threads: list[dict[str, Any]] = []
    for incident in incidents:
        if not isinstance(incident, dict) or incident.get("status") == "resolved":
            continue
        current_alert = alert_map.get(incident.get("current_alert_id"))
        detection = ((current_alert or {}).get("metrics") or {}).get("detection", {})
        if not isinstance(detection, dict):
            continue
        notification_outcome = detection.get("notification_outcome")
        if notification_outcome not in VISIBLE_NOTIFICATION_OUTCOMES:
            continue
        active_threads.append(
            {
                "incident_id": incident["id"],
                "incident_key": incident["incident_key"],
                "workflow_status": incident.get("workflow_status"),
                "severity": incident.get("severity"),
                "current_alert_id": incident.get("current_alert_id"),
                "alert_type": incident.get("alert_type"),
                "incident_domain": incident.get("incident_domain"),
                "incident_category": incident.get("incident_category"),
                "notification_outcome": notification_outcome,
            }
        )

    return {
        "counts": {
            "open_threads": len(active_threads),
            "founder_visible_threads": sum(1 for thread in active_threads if thread["notification_outcome"] == "founder_notify"),
        },
        "active_threads": active_threads,
    }
