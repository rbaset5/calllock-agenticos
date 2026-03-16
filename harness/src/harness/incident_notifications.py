from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from harness.notifications.email_delivery import deliver_email
from harness.notifications.pager_delivery import deliver_pager
from harness.notifications.sms_delivery import deliver_sms


REPO_ROOT = Path(__file__).resolve().parents[3]


def _incident_root() -> Path:
    base = os.getenv("CALLLOCK_INCIDENT_ROOT")
    if base:
        return Path(base)
    return REPO_ROOT / ".context" / "incidents"


def _resolve_channels(tenant_config: dict[str, Any]) -> list[str]:
    channels = tenant_config.get("incident_notification_channels", ["dashboard"])
    if not isinstance(channels, list):
        return ["dashboard"]
    resolved = []
    for channel in channels:
        if isinstance(channel, str) and channel not in resolved:
            resolved.append(channel)
    return resolved or ["dashboard"]


def _incident_payload(incident: dict[str, Any], *, reminder: bool) -> dict[str, Any]:
    return {
        "id": incident["id"],
        "incident_revision": incident.get("incident_revision"),
        "tenant_id": incident.get("tenant_id"),
        "incident_key": incident["incident_key"],
        "alert_type": incident["alert_type"],
        "incident_domain": incident.get("incident_domain"),
        "incident_category": incident.get("incident_category"),
        "remediation_category": incident.get("remediation_category"),
        "incident_urgency": incident.get("incident_urgency"),
        "runbook_id": incident.get("runbook_id"),
        "runbook_title": incident.get("runbook_title"),
        "runbook_steps": incident.get("runbook_steps", []),
        "runbook_progress": incident.get("runbook_progress", []),
        "runbook_progress_summary": incident.get("runbook_progress_summary", {}),
        "runbook_execution_plan": incident.get("runbook_execution_plan", {}),
        "completion_policy": incident.get("completion_policy", {}),
        "status": incident.get("status"),
        "workflow_status": incident.get("workflow_status"),
        "assigned_to": incident.get("assigned_to"),
        "current_episode": incident.get("current_episode"),
        "occurrence_count": incident.get("occurrence_count"),
        "reminder": reminder,
    }


def _deliver_dashboard(incident: dict[str, Any], *, reminder: bool) -> dict[str, Any]:
    root = _incident_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / "dashboard.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_incident_payload(incident, reminder=reminder), sort_keys=True))
        handle.write("\n")
    return {"channel": "dashboard", "delivered": True, "destination": str(path)}


def _deliver_assignee_webhook(incident: dict[str, Any], tenant_config: dict[str, Any], *, reminder: bool) -> dict[str, Any]:
    assignee = incident.get("assigned_to")
    contacts = tenant_config.get("incident_assignees", {})
    contact = contacts.get(assignee, {}) if isinstance(contacts, dict) and assignee else {}
    webhook_url = contact.get("webhook_url")
    if not webhook_url:
        return {"channel": "assignee_webhook", "delivered": False, "reason": "missing_assignee_webhook"}
    if httpx is None:
        return {"channel": "assignee_webhook", "delivered": False, "reason": "httpx_unavailable"}
    try:
        response = httpx.post(webhook_url, json=_incident_payload(incident, reminder=reminder), timeout=5.0)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover
        return {"channel": "assignee_webhook", "delivered": False, "destination": webhook_url, "reason": str(exc)}
    return {"channel": "assignee_webhook", "delivered": True, "destination": webhook_url}


def _deliver_assignee_email(incident: dict[str, Any], tenant_config: dict[str, Any], *, reminder: bool) -> dict[str, Any]:
    assignee = incident.get("assigned_to")
    contacts = tenant_config.get("incident_assignees", {})
    contact = contacts.get(assignee, {}) if isinstance(contacts, dict) and assignee else {}
    recipient = contact.get("email")
    return deliver_email(
        category="incidents",
        recipients=recipient,
        subject=f"[{incident.get('incident_urgency', 'medium').upper()}] {incident.get('incident_category') or incident.get('alert_type')}",
        payload=_incident_payload(incident, reminder=reminder),
    ) | {"channel": "assignee_email"}


def _deliver_assignee_sms(incident: dict[str, Any], tenant_config: dict[str, Any], *, reminder: bool) -> dict[str, Any]:
    assignee = incident.get("assigned_to")
    contacts = tenant_config.get("incident_assignees", {})
    contact = contacts.get(assignee, {}) if isinstance(contacts, dict) and assignee else {}
    recipient = contact.get("phone")
    return deliver_sms(
        category="incidents",
        recipients=recipient,
        message=(
            f"[{incident.get('incident_urgency', 'medium').upper()}] "
            f"{incident.get('incident_category') or incident.get('alert_type')}"
        ),
        payload=_incident_payload(incident, reminder=reminder),
    ) | {"channel": "assignee_sms"}


def _deliver_assignee_pager(incident: dict[str, Any], tenant_config: dict[str, Any], *, reminder: bool) -> dict[str, Any]:
    assignee = incident.get("assigned_to")
    contacts = tenant_config.get("incident_assignees", {})
    contact = contacts.get(assignee, {}) if isinstance(contacts, dict) and assignee else {}
    target = contact.get("pager_target")
    return deliver_pager(
        category="incidents",
        targets=target,
        summary=(
            f"{incident.get('incident_category') or incident.get('alert_type')}"
            f" assigned to {assignee or 'unassigned'}"
        ),
        severity=incident.get("incident_urgency", "medium"),
        payload=_incident_payload(incident, reminder=reminder),
    ) | {"channel": "assignee_pager"}


def notify_incident(incident: dict[str, Any], tenant_config: dict[str, Any] | None = None, *, reminder: bool = False) -> dict[str, Any]:
    config = tenant_config or {}
    attempts = []
    for channel in _resolve_channels(config):
        if channel == "dashboard":
            attempts.append(_deliver_dashboard(incident, reminder=reminder))
            continue
        if channel == "assignee_webhook":
            attempts.append(_deliver_assignee_webhook(incident, config, reminder=reminder))
            continue
        if channel == "assignee_email":
            attempts.append(_deliver_assignee_email(incident, config, reminder=reminder))
            continue
        if channel == "assignee_sms":
            attempts.append(_deliver_assignee_sms(incident, config, reminder=reminder))
            continue
        if channel == "assignee_pager":
            attempts.append(_deliver_assignee_pager(incident, config, reminder=reminder))
            continue
        attempts.append({"channel": channel, "delivered": False, "reason": "unsupported_channel"})
    return {
        "incident_id": incident["id"],
        "delivered": any(attempt.get("delivered", False) for attempt in attempts),
        "channels": attempts,
    }
