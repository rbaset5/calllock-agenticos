from __future__ import annotations

from typing import Any

from harness.incident_classification import classify_incident
from harness.incident_runbooks import build_runbook_execution_plan, build_runbook_progress, resolve_incident_runbook, summarize_runbook_progress


def build_incident_sync_payload(alert: dict[str, Any], tenant_config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = tenant_config or {}
    incident_key = f"{alert.get('tenant_id') or 'global'}:{alert['alert_type']}"
    classification = classify_incident(alert, config)
    runbook = resolve_incident_runbook(
        {
            "incident_key": incident_key,
            "tenant_id": alert.get("tenant_id"),
            "alert_type": alert["alert_type"],
            "severity": alert.get("severity", "medium"),
            "incident_domain": classification["incident_domain"],
            "incident_category": classification["incident_category"],
            "remediation_category": classification["remediation_category"],
            "incident_urgency": classification["incident_urgency"],
        },
        config,
    )
    initial_runbook_progress = build_runbook_progress(
        runbook.get("runbook_steps", []),
        existing_progress=None,
        reset=True,
    )
    return {
        "incident_key": incident_key,
        "tenant_id": alert.get("tenant_id"),
        "alert_type": alert["alert_type"],
        "severity": alert.get("severity", "medium"),
        "incident_domain": classification["incident_domain"],
        "incident_category": classification["incident_category"],
        "remediation_category": classification["remediation_category"],
        "incident_urgency": classification["incident_urgency"],
        "alert_id": alert["id"],
        "alert_status": alert.get("status", "open"),
        "alert_created_at": alert.get("created_at"),
        "alert_last_observed_at": alert.get("last_observed_at") or alert.get("resolved_at") or alert.get("created_at"),
        "alert_resolved_at": alert.get("resolved_at"),
        "alert_occurrence_count": int(alert.get("occurrence_count", 1)),
        **runbook,
        "initial_runbook_progress": initial_runbook_progress,
        "initial_runbook_progress_summary": summarize_runbook_progress(initial_runbook_progress),
        "initial_runbook_execution_plan": build_runbook_execution_plan(initial_runbook_progress),
    }
