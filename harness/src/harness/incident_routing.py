from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from zoneinfo import ZoneInfo

from db.repository import list_incidents
from harness.incident_classification import incident_skill_lookup_keys


DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _normalize_rule_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _parse_iso(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _normalize_days(days: Any) -> set[str]:
    if not isinstance(days, list):
        return set(DAY_NAMES)
    normalized = set()
    for value in days:
        if isinstance(value, str):
            lowered = value.strip().lower()[:3]
            if lowered in DAY_NAMES:
                normalized.add(lowered)
    return normalized or set(DAY_NAMES)


def _is_available(assignee_id: str, tenant_config: dict[str, Any], *, now: datetime) -> bool:
    contacts = tenant_config.get("incident_assignees", {})
    if not isinstance(contacts, dict):
        return True
    contact = contacts.get(assignee_id, {})
    if not isinstance(contact, dict):
        return True
    availability = contact.get("availability")
    if not isinstance(availability, dict):
        return True

    timezone_name = contact.get("timezone") or tenant_config.get("timezone") or "UTC"
    try:
        local_now = now.astimezone(ZoneInfo(timezone_name))
    except Exception:
        local_now = now.astimezone(timezone.utc)
    allowed_days = _normalize_days(availability.get("days"))
    current_day = DAY_NAMES[local_now.weekday()]
    if current_day not in allowed_days:
        return False

    start_hour = availability.get("start_hour", 0)
    end_hour = availability.get("end_hour", 24)
    if isinstance(start_hour, bool) or not isinstance(start_hour, (int, float)):
        start_hour = 0
    if isinstance(end_hour, bool) or not isinstance(end_hour, (int, float)):
        end_hour = 24
    return int(start_hour) <= local_now.hour < int(end_hour)


def _rotation_candidates(tenant_config: dict[str, Any], *, now: datetime) -> list[str]:
    pool = tenant_config.get("incident_oncall_rotation", [])
    if not isinstance(pool, list):
        return []
    assignees = [assignee for assignee in pool if isinstance(assignee, str) and assignee]
    if not assignees:
        return []

    interval_hours = tenant_config.get("incident_rotation_interval_hours", 24)
    if isinstance(interval_hours, bool) or not isinstance(interval_hours, (int, float)) or interval_hours < 1:
        interval_hours = 24

    timezone_name = tenant_config.get("timezone") or "UTC"
    try:
        local_now = now.astimezone(ZoneInfo(timezone_name))
    except Exception:
        local_now = now.astimezone(timezone.utc)
    bucket = int(local_now.timestamp() // (int(interval_hours) * 3600))
    start_index = bucket % len(assignees)
    return assignees[start_index:] + assignees[:start_index]


def _active_loads(tenant_id: str | None, *, current_incident_id: str | None = None) -> dict[str, int]:
    loads: dict[str, int] = {}
    for incident in list_incidents(tenant_id=tenant_id):
        if incident.get("id") == current_incident_id:
            continue
        if incident.get("status") == "resolved" or incident.get("workflow_status") == "closed":
            continue
        assignee = incident.get("assigned_to")
        if not assignee:
            continue
        loads[assignee] = loads.get(assignee, 0) + 1
    return loads


def _assignee_capacity(assignee_id: str, tenant_config: dict[str, Any]) -> int:
    contacts = tenant_config.get("incident_assignees", {})
    contact = contacts.get(assignee_id, {}) if isinstance(contacts, dict) else {}
    value = contact.get("max_active_incidents", 1) if isinstance(contact, dict) else 1
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 1:
        return 1
    return int(value)


def _assignee_weight(assignee_id: str, tenant_config: dict[str, Any]) -> float:
    contacts = tenant_config.get("incident_assignees", {})
    contact = contacts.get(assignee_id, {}) if isinstance(contacts, dict) else {}
    value = contact.get("routing_weight", 1.0) if isinstance(contact, dict) else 1.0
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return 1.0
    return float(value)


def _required_skills(
    tenant_config: dict[str, Any],
    *,
    incident_type: str | None = None,
    incident_category: str | None = None,
    remediation_category: str | None = None,
    incident_domain: str | None = None,
    alert_type: str | None = None,
) -> set[str]:
    rules = tenant_config.get("incident_skill_requirements", {})
    if not isinstance(rules, dict):
        return set()
    normalized_rules = {
        _normalize_rule_key(key): value
        for key, value in rules.items()
        if isinstance(key, str) and isinstance(value, list)
    }
    for lookup_key in incident_skill_lookup_keys(
        incident_type=incident_type,
        incident_category=incident_category,
        remediation_category=remediation_category,
        incident_domain=incident_domain,
        alert_type=alert_type,
    ):
        skills = normalized_rules.get(lookup_key)
        if isinstance(skills, list):
            return {skill for skill in skills if isinstance(skill, str) and skill}
    return set()


def _skill_gap(
    assignee_id: str,
    tenant_config: dict[str, Any],
    *,
    incident_type: str | None,
    incident_category: str | None,
    remediation_category: str | None,
    incident_domain: str | None,
    alert_type: str | None,
) -> int:
    required = _required_skills(
        tenant_config,
        incident_type=incident_type,
        incident_category=incident_category,
        remediation_category=remediation_category,
        incident_domain=incident_domain,
        alert_type=alert_type,
    )
    if not required:
        return 0
    contacts = tenant_config.get("incident_assignees", {})
    contact = contacts.get(assignee_id, {}) if isinstance(contacts, dict) else {}
    skills = contact.get("skills", []) if isinstance(contact, dict) else []
    if not isinstance(skills, list):
        skills = []
    assignee_skills = {skill for skill in skills if isinstance(skill, str) and skill}
    return len(required - assignee_skills)


def resolve_assignee(
    preferred_assignee: str | None,
    tenant_config: dict[str, Any],
    *,
    incident_type: str | None = None,
    incident_category: str | None = None,
    remediation_category: str | None = None,
    incident_domain: str | None = None,
    alert_type: str | None = None,
    now_iso: str | None = None,
    current_incident_id: str | None = None,
) -> tuple[str | None, str]:
    now = _parse_iso(now_iso) or datetime.now(timezone.utc)
    contacts = tenant_config.get("incident_assignees", {})
    default_assignee = tenant_config.get("incident_default_assignee")
    loads = _active_loads(tenant_config.get("tenant_id"), current_incident_id=current_incident_id)
    queue = []
    if preferred_assignee:
        queue.append((preferred_assignee, "preferred"))
    if default_assignee and default_assignee != preferred_assignee:
        queue.append((default_assignee, "default"))

    rotation_candidates = _rotation_candidates(tenant_config, now=now)
    ranked_rotation = sorted(
        enumerate(rotation_candidates),
        key=lambda item: (
            _skill_gap(
                item[1],
                tenant_config,
                incident_type=incident_type,
                incident_category=incident_category,
                remediation_category=remediation_category,
                incident_domain=incident_domain,
                alert_type=alert_type,
            ),
            loads.get(item[1], 0) / max(_assignee_capacity(item[1], tenant_config), 1),
            -_assignee_weight(item[1], tenant_config),
            item[0],
        ),
    )
    for position, (_, assignee_id) in enumerate(ranked_rotation):
        if assignee_id not in {preferred_assignee, default_assignee}:
            queue.append((assignee_id, "rotation_primary" if position == 0 else f"rotation_fallback:{position}"))

    seen: set[str] = set()
    while queue:
        assignee_id, source = queue.pop(0)
        if not assignee_id or assignee_id in seen:
            continue
        seen.add(assignee_id)
        if _is_available(assignee_id, tenant_config, now=now):
            return assignee_id, source if source != "preferred" else "preferred_available"
        contact = contacts.get(assignee_id, {}) if isinstance(contacts, dict) else {}
        fallback = contact.get("fallback_assignee") if isinstance(contact, dict) else None
        if fallback and fallback not in seen:
            queue.append((fallback, f"fallback_from:{assignee_id}"))

    return preferred_assignee or default_assignee, "no_available_assignee"


def resolve_reassign_after_reminders(tenant_config: dict[str, Any]) -> int:
    value = tenant_config.get("incident_reassign_after_reminders", 2)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 1:
        return 2
    return int(value)
