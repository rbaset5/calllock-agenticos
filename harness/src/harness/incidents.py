from __future__ import annotations

from typing import Any

from db.repository import get_tenant_config, sync_incident_from_alert
from harness.incident_sync_payload import build_incident_sync_payload


def incident_key_for_alert(alert: dict[str, Any]) -> str:
    tenant_id = alert.get("tenant_id") or "global"
    return f"{tenant_id}:{alert['alert_type']}"


def record_incident_from_alert(alert: dict[str, Any]) -> dict[str, Any]:
    tenant_config = get_tenant_config(alert["tenant_id"]) if alert.get("tenant_id") else {}
    return sync_incident_from_alert(build_incident_sync_payload(alert, tenant_config))
