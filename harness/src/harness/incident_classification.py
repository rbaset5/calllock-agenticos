from __future__ import annotations

import re
from typing import Any


_SEVERITY_TO_URGENCY = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}

_DEFAULT_RULES = [
    {
        "match": {"alert_type_prefix": "scheduler_"},
        "incident_domain": "operations",
        "incident_category": "scheduler_health",
        "remediation_category": "scheduler_recovery",
    },
    {
        "match": {"alert_type_contains": "scheduler"},
        "incident_domain": "operations",
        "incident_category": "scheduler_health",
        "remediation_category": "scheduler_recovery",
    },
    {
        "match": {"alert_type_prefix": "job_"},
        "incident_domain": "operations",
        "incident_category": "worker_reliability",
        "remediation_category": "worker_debugging",
    },
    {
        "match": {"alert_type_contains": "worker"},
        "incident_domain": "operations",
        "incident_category": "worker_reliability",
        "remediation_category": "worker_debugging",
    },
    {
        "match": {"alert_type_contains": "verification"},
        "incident_domain": "operations",
        "incident_category": "worker_reliability",
        "remediation_category": "worker_debugging",
    },
    {
        "match": {"alert_type_contains": "policy"},
        "incident_domain": "governance",
        "incident_category": "policy_enforcement",
        "remediation_category": "policy_review",
    },
    {
        "match": {"alert_type_contains": "compliance"},
        "incident_domain": "governance",
        "incident_category": "policy_enforcement",
        "remediation_category": "policy_review",
    },
    {
        "match": {"alert_type": "external_service_error"},
        "incident_domain": "integrations",
        "incident_category": "vendor_dependency",
        "remediation_category": "vendor_escalation",
    },
]


def _normalize_label(value: Any, *, fallback: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return fallback
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or fallback


def _normalize_optional_label(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return _normalize_label(value, fallback="")


def _normalize_severity(value: Any) -> str:
    severity = _normalize_label(value, fallback="medium")
    return severity if severity in _SEVERITY_TO_URGENCY else "medium"


def _matches_rule(rule: dict[str, Any], alert: dict[str, Any]) -> bool:
    match = rule.get("match", {})
    if not isinstance(match, dict):
        return False
    alert_type = _normalize_label(alert.get("alert_type"), fallback="")
    severity = _normalize_severity(alert.get("severity"))

    exact_type = _normalize_optional_label(match.get("alert_type"))
    if exact_type and alert_type != exact_type:
        return False

    prefix = _normalize_optional_label(match.get("alert_type_prefix"))
    if prefix and not alert_type.startswith(prefix):
        return False

    contains = _normalize_optional_label(match.get("alert_type_contains"))
    if contains and contains not in alert_type:
        return False

    exact_severity = _normalize_optional_label(match.get("severity"))
    if exact_severity and severity != exact_severity:
        return False

    return any(
        key in match
        for key in ("alert_type", "alert_type_prefix", "alert_type_contains", "severity")
    )


def classify_incident(alert: dict[str, Any], tenant_config: dict[str, Any] | None = None) -> dict[str, str]:
    normalized_alert_type = _normalize_label(alert.get("alert_type"), fallback="generic_alert")
    severity = _normalize_severity(alert.get("severity"))
    classification = {
        "incident_domain": "general",
        "incident_category": normalized_alert_type,
        "remediation_category": "manual_review",
        "incident_urgency": _SEVERITY_TO_URGENCY[severity],
    }

    configured_rules = (tenant_config or {}).get("incident_classification_rules", [])
    rules: list[dict[str, Any]] = []
    if isinstance(configured_rules, list):
        rules.extend(rule for rule in configured_rules if isinstance(rule, dict))
    rules.extend(_DEFAULT_RULES)

    for rule in rules:
        if not _matches_rule(rule, alert):
            continue
        classification["incident_domain"] = _normalize_label(rule.get("incident_domain"), fallback=classification["incident_domain"])
        classification["incident_category"] = _normalize_label(rule.get("incident_category"), fallback=classification["incident_category"])
        classification["remediation_category"] = _normalize_label(
            rule.get("remediation_category"),
            fallback=classification["remediation_category"],
        )
        if rule.get("incident_urgency") or rule.get("urgency"):
            classification["incident_urgency"] = _normalize_label(
                rule.get("incident_urgency") or rule.get("urgency"),
                fallback=classification["incident_urgency"],
            )
        break

    return classification


def incident_skill_lookup_keys(
    *,
    incident_type: str | None = None,
    incident_category: str | None = None,
    remediation_category: str | None = None,
    incident_domain: str | None = None,
    alert_type: str | None = None,
) -> list[str]:
    keys: list[str] = []
    for value in (incident_category, remediation_category, incident_domain, incident_type, alert_type):
        normalized = _normalize_optional_label(value)
        if normalized and normalized not in keys:
            keys.append(normalized)
    return keys
