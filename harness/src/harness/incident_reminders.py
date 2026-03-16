from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from db.repository import get_tenant_config, list_incidents, update_incident_reminder
from harness.audit import log_audit_event
from harness.incident_notifications import notify_incident
from harness.incident_routing import resolve_assignee, resolve_reassign_after_reminders


def _parse_iso(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _resolve_reminder_minutes(tenant_config: dict[str, Any] | None = None) -> int:
    value = (tenant_config or {}).get("incident_reminder_minutes", 60)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 1:
        return 60
    return int(value)


def send_incident_reminders(*, tenant_id: str | None = None, now_iso: str | None = None) -> list[dict[str, Any]]:
    now = _parse_iso(now_iso) or datetime.now(timezone.utc)
    reminders = []
    for incident in list_incidents(tenant_id=tenant_id):
        if incident.get("workflow_status") not in {"acknowledged", "investigating"}:
            continue
        if not incident.get("assigned_to"):
            continue

        tenant_config = get_tenant_config(incident["tenant_id"]) if incident.get("tenant_id") else {}
        reminder_minutes = _resolve_reminder_minutes(tenant_config)
        reference = _parse_iso(incident.get("last_reminded_at") or incident.get("last_reviewed_at") or incident.get("started_at"))
        if reference is None:
            continue
        elapsed_minutes = max(0, int((now - reference).total_seconds() // 60))
        if elapsed_minutes < reminder_minutes:
            continue

        reminder_count = int(incident.get("reminder_count", 0)) + 1
        assignee, reason = resolve_assignee(
            incident.get("assigned_to"),
            tenant_config,
            incident_type=incident.get("alert_type"),
            incident_category=incident.get("incident_category"),
            remediation_category=incident.get("remediation_category"),
            incident_domain=incident.get("incident_domain"),
            alert_type=incident.get("alert_type"),
            now_iso=now.isoformat(),
            current_incident_id=incident.get("id"),
        )
        reassign_after = resolve_reassign_after_reminders(tenant_config)
        if reminder_count >= reassign_after:
            contacts = tenant_config.get("incident_assignees", {})
            current_contact = contacts.get(incident.get("assigned_to"), {}) if isinstance(contacts, dict) else {}
            threshold_target = None
            if isinstance(current_contact, dict):
                threshold_target = current_contact.get("fallback_assignee")
            if not threshold_target:
                threshold_target = tenant_config.get("incident_default_assignee")
            threshold_assignee, threshold_reason = resolve_assignee(
                threshold_target,
                tenant_config,
                incident_type=incident.get("alert_type"),
                incident_category=incident.get("incident_category"),
                remediation_category=incident.get("remediation_category"),
                incident_domain=incident.get("incident_domain"),
                alert_type=incident.get("alert_type"),
                now_iso=now.isoformat(),
                current_incident_id=incident.get("id"),
            )
            if threshold_assignee:
                assignee = threshold_assignee
                reason = "reminder_threshold" if threshold_assignee != incident.get("assigned_to") else threshold_reason
        updates: dict[str, Any] = {
            "last_reminded_at": now.isoformat(),
            "reminder_count": reminder_count,
        }
        assignment_history_entry = None
        if assignee and (
            assignee != incident.get("assigned_to")
            or reminder_count >= reassign_after
        ):
            updates["assigned_to"] = assignee
            updates["last_assignment_reason"] = reason if assignee != incident.get("assigned_to") else "reminder_threshold"
            assignment_history_entry = {
                "at": now.isoformat(),
                "from": incident.get("assigned_to"),
                "to": assignee,
                "reason": updates["last_assignment_reason"],
            }

        updated = update_incident_reminder(
            incident["id"],
            actor_id="system:incident-reminder",
            reminder_count=updates["reminder_count"],
            last_reminded_at=updates["last_reminded_at"],
            assigned_to=updates.get("assigned_to"),
            last_assignment_reason=updates.get("last_assignment_reason"),
            assignment_history_entry=assignment_history_entry,
        )
        updated["notification"] = notify_incident(updated, tenant_config, reminder=True)
        log_audit_event(
            action_type="incident.reminder_sent",
            actor_id="system:incident-reminder",
            reason=f"Reminder sent after {elapsed_minutes} minutes",
            tenant_id=updated.get("tenant_id"),
            target_type="incident",
            target_id=updated["id"],
            payload={"elapsed_minutes": elapsed_minutes, "assigned_to": updated.get("assigned_to"), "routing_reason": updated.get("last_assignment_reason")},
        )
        reminders.append(updated)
    return reminders
