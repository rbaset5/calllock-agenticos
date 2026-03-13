from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from db.repository import create_alert_and_sync_incident, get_tenant_config, list_jobs, list_scheduler_backlog
from harness.alerts.notifier import notify
from harness.alerts.recovery import auto_resolve_recovered_alerts
from harness.alerts.suppression import suppress_duplicate_alert
from harness.alerts.thresholds import resolve_thresholds


def _rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _parse_iso(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def evaluate_alerts(*, tenant_id: str | None = None, window_minutes: int = 15) -> list[dict[str, Any]]:
    tenant_config = get_tenant_config(tenant_id) if tenant_id else {}
    thresholds = resolve_thresholds(tenant_config)
    jobs = list_jobs(tenant_id=tenant_id)
    backlog = list_scheduler_backlog(tenant_id=tenant_id)
    now = datetime.now(timezone.utc)
    total = len(jobs)
    blocked = sum(1 for job in jobs if job.get("result", {}).get("policy_verdict") == "deny")
    failed = sum(1 for job in jobs if job.get("status") == "failed")
    verification_failures = sum(1 for job in jobs if not job.get("result", {}).get("verification", {}).get("passed", True))
    external_errors = sum(1 for job in jobs if "external_error" in str(job.get("result", {})).lower())
    stale_claims = 0
    oldest_pending_age_minutes = 0
    for entry in backlog:
        if entry.get("status") == "claimed":
            claim_expires_at = _parse_iso(entry.get("claim_expires_at"))
            if claim_expires_at and claim_expires_at <= now + timedelta(minutes=window_minutes):
                stale_claims += 1
        elif entry.get("status") == "pending":
            scheduled_for = _parse_iso(entry.get("scheduled_for"))
            if scheduled_for is not None:
                oldest_pending_age_minutes = max(
                    oldest_pending_age_minutes,
                    int((now - scheduled_for).total_seconds() // 60),
                )

    metrics = {
        "policy_block_rate": _rate(blocked, total),
        "worker_metric_degradation": _rate(verification_failures, total),
        "job_failure_spike": failed,
        "external_service_error": external_errors,
        "scheduler_stale_claims": stale_claims,
        "scheduler_backlog_age": oldest_pending_age_minutes,
        "window_minutes": window_minutes,
    }

    alerts = []
    for alert_type, threshold in thresholds.items():
        value = metrics[alert_type]
        if value >= threshold:
            enriched_metrics = {**metrics, "applied_thresholds": thresholds, "threshold": threshold}
            suppressed = suppress_duplicate_alert(
                tenant_id=tenant_id,
                alert_type=alert_type,
                metrics=enriched_metrics,
                tenant_config=tenant_config,
                now_iso=now.isoformat(),
            )
            if suppressed is not None:
                alerts.append(suppressed)
                continue
            alert = create_alert_and_sync_incident(
                {
                    "tenant_id": tenant_id,
                    "alert_type": alert_type,
                    "severity": "high" if alert_type != "external_service_error" else "medium",
                    "message": f"{alert_type} threshold breached ({value} >= {threshold})",
                    "metrics": enriched_metrics,
                    "occurrence_count": 1,
                    "last_observed_at": now.isoformat(),
                }
            )
            alert["notification"] = notify(alert, tenant_config)
            alerts.append(alert)
    recovered_alerts = auto_resolve_recovered_alerts(
        metrics=metrics,
        thresholds=thresholds,
        tenant_id=tenant_id,
        tenant_config=tenant_config,
        now_iso=now.isoformat(),
    )
    alerts.extend(recovered_alerts)
    return alerts
