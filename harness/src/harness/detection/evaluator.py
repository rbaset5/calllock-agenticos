from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from db.repository import (
    create_alert_and_sync_incident,
    get_tenant_config,
    list_alerts,
    list_incidents,
    list_jobs,
    list_scheduler_backlog,
    update_alert_and_sync_incident,
)
from harness.alerts.notifier import notify
from harness.alerts.recovery import auto_resolve_recovered_alerts
from harness.alerts.suppression import suppress_duplicate_alert
from harness.alerts.thresholds import resolve_thresholds
from harness.detection.catalog import load_voice_monitor_catalog
from harness.detection.dispatch import build_detection_dispatches
from harness.detection.triage import assess_detection_event, build_detection_event, decide_notification
from harness.dispatch import dispatch_job_requests


def _rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _parse_iso(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def evaluate_detection(*, tenant_id: str | None = None, window_minutes: int = 15) -> list[dict[str, Any]]:
    tenant_config = get_tenant_config(tenant_id) if tenant_id else {}
    thresholds = resolve_thresholds(tenant_config)
    now = datetime.now(timezone.utc)

    generic_alerts, generic_metrics = _evaluate_operational_alerts(
        tenant_id=tenant_id,
        window_minutes=window_minutes,
        now=now,
        tenant_config=tenant_config,
        thresholds=thresholds,
    )
    detection_alerts = _evaluate_voice_detection(
        tenant_id=tenant_id,
        window_minutes=window_minutes,
        now=now,
        tenant_config=tenant_config,
    )
    recovered_alerts = auto_resolve_recovered_alerts(
        metrics=generic_metrics,
        thresholds=thresholds,
        tenant_id=tenant_id,
        tenant_config=tenant_config,
        now_iso=now.isoformat(),
    )
    return [*generic_alerts, *detection_alerts, *recovered_alerts]


def list_recent_call_records(*, limit: int = 50) -> list[dict[str, Any]]:
    try:
        from voice.services.health_check import list_recent_call_records as _list_recent_call_records
    except Exception:
        return []

    return _list_recent_call_records(limit=limit)


def _evaluate_operational_alerts(
    *,
    tenant_id: str | None,
    window_minutes: int,
    now: datetime,
    tenant_config: dict[str, Any],
    thresholds: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    jobs = list_jobs(tenant_id=tenant_id)
    backlog = list_scheduler_backlog(tenant_id=tenant_id)
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

    alerts: list[dict[str, Any]] = []
    for alert_type, threshold in thresholds.items():
        value = metrics[alert_type]
        if value < threshold:
            continue
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
    return alerts, metrics


def _evaluate_voice_detection(
    *,
    tenant_id: str | None,
    window_minutes: int,
    now: datetime,
    tenant_config: dict[str, Any],
) -> list[dict[str, Any]]:
    catalog = load_voice_monitor_catalog()
    rows = _filter_rows_for_tenant(list_recent_call_records(limit=_voice_row_limit(catalog)), tenant_id=tenant_id)
    if not rows:
        return []

    incidents = list_incidents(tenant_id=tenant_id, status="open")
    open_issue_keys = {
        str(incident.get("incident_key"))
        for incident in incidents
        if isinstance(incident, dict) and incident.get("incident_key")
    }
    alerts: list[dict[str, Any]] = []
    for monitor in catalog["monitors"]:
        threshold = monitor["effective_threshold"]
        monitor_window_minutes = int(threshold["window_minutes"])
        monitor_rows = _recent_rows_within_window(rows, window_minutes=monitor_window_minutes, now=now)
        if len(monitor_rows) < int(threshold["min_sample_size"]):
            continue
        voice_metrics = _compute_voice_metrics(monitor_rows)
        metric_name = str(threshold["metric"])
        metric_value = float(voice_metrics.get(metric_name, 0.0))
        if not _threshold_breached(metric_value, threshold):
            continue

        event = build_detection_event(
            monitor_id=str(monitor["monitor_id"]),
            tenant_id=tenant_id,
            severity=str(monitor["severity"]),
            raw_context={
                "metric": metric_name,
                "metric_value": metric_value,
                "sample_size": len(monitor_rows),
                "window_minutes": monitor_window_minutes,
            },
        )
        assessment = assess_detection_event(
            event,
            has_open_issue=event["dedupe_key"] in open_issue_keys,
            in_flight_fix=False,
        )
        notification = decide_notification(event, assessment)
        detection_meta = {
            "monitor_id": monitor["monitor_id"],
            "triage_outcome": assessment["outcome"],
            "triage_reason": assessment["reason"],
            "notification_outcome": notification["notification_outcome"],
            "channels": notification["channels"],
            "dedupe_key": event["dedupe_key"],
        }
        enriched_metrics = {
            "metric_name": metric_name,
            "metric_value": metric_value,
            "sample_size": len(monitor_rows),
            "window_minutes": monitor_window_minutes,
            "threshold": threshold["value"],
            "threshold_operator": threshold["operator"],
            "min_sample_size": threshold["min_sample_size"],
            "detection": detection_meta,
        }
        payload = {
            "tenant_id": tenant_id,
            "alert_type": monitor["alert_type"],
            "severity": monitor["severity"],
            "message": f"{monitor['summary']} ({metric_value} {threshold['operator']} {threshold['value']})",
            "metrics": enriched_metrics,
            "occurrence_count": 1,
            "last_observed_at": now.isoformat(),
        }

        if assessment["outcome"] == "stand_down":
            alert = suppress_duplicate_alert(
                tenant_id=tenant_id,
                alert_type=str(monitor["alert_type"]),
                metrics=enriched_metrics,
                tenant_config=tenant_config,
                now_iso=now.isoformat(),
            )
            if alert is None:
                alert = create_alert_and_sync_incident(payload)
        else:
            alert = create_alert_and_sync_incident(payload)

        alert["notification"] = notify(alert, tenant_config)
        if tenant_id:
            requests = build_detection_dispatches(alert)
            if requests:
                dispatch_result = dispatch_job_requests(
                    requests=requests,
                    origin_worker_id="voice-truth",
                    tenant_id=tenant_id,
                    inngest_client=None,
                    supabase_client=None,
                )
                alert["detection_dispatch"] = {
                    "dispatched": list(dispatch_result.dispatched),
                    "queued": list(dispatch_result.queued),
                    "blocked": list(dispatch_result.blocked),
                }
        alerts.append(alert)
    alerts.extend(
        _auto_resolve_recovered_detection_alerts(
            rows=rows,
            now=now,
            tenant_id=tenant_id,
            tenant_config=tenant_config,
        )
    )
    return alerts


def _filter_rows_for_tenant(rows: Iterable[dict[str, Any]], *, tenant_id: str | None) -> list[dict[str, Any]]:
    if tenant_id is None:
        return [row for row in rows if isinstance(row, dict)]
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_tenant = row.get("tenant_id")
        if row_tenant == tenant_id:
            filtered.append(row)
    return filtered


def _voice_row_limit(catalog: Mapping[str, Any]) -> int:
    monitors = catalog.get("monitors", [])
    max_sample_size = 0
    for monitor in monitors:
        if not isinstance(monitor, Mapping):
            continue
        threshold = monitor.get("effective_threshold") or monitor.get("threshold") or {}
        if isinstance(threshold, Mapping):
            sample_size = threshold.get("min_sample_size")
            if isinstance(sample_size, (int, float)) and sample_size > max_sample_size:
                max_sample_size = int(sample_size)
    return max(200, max_sample_size * 10)


def _recent_rows_within_window(
    rows: Iterable[Mapping[str, Any]],
    *,
    window_minutes: int,
    now: datetime,
) -> list[Mapping[str, Any]]:
    cutoff = now - timedelta(minutes=window_minutes)
    recent_rows: list[Mapping[str, Any]] = []
    for row in rows:
        created_at = _parse_iso(row.get("created_at"))
        if created_at is None or created_at >= cutoff:
            recent_rows.append(row)
    return recent_rows


def _compute_voice_metrics(rows: list[Mapping[str, Any]]) -> dict[str, float]:
    total = len(rows)
    empty_structured_output_count = 0
    required_field_missing_count = 0
    warning_count = 0
    route_missing_count = 0
    safety_mismatch_count = 0

    for row in rows:
        extracted_fields = row.get("extracted_fields")
        extracted = extracted_fields if isinstance(extracted_fields, Mapping) else {}
        if not _has_meaningful_mapping(extracted):
            empty_structured_output_count += 1
        if any(not _has_meaningful_value(_field_value(row, field_name)) for field_name in ("customer_phone", "urgency_tier", "route")):
            required_field_missing_count += 1
        if _has_warnings(row):
            warning_count += 1
        if not _has_meaningful_value(_field_value(row, "route")):
            route_missing_count += 1
        if _has_safety_emergency_mismatch(row):
            safety_mismatch_count += 1

    return {
        "empty_structured_output_rate": _rate(empty_structured_output_count, total),
        "required_field_missing_rate": _rate(required_field_missing_count, total),
        "warning_rate": _rate(warning_count, total),
        "route_missing_rate": _rate(route_missing_count, total),
        "safety_emergency_mismatch_rate": _rate(safety_mismatch_count, total),
    }


def _field_value(row: Mapping[str, Any], field_name: str) -> Any:
    extracted_fields = row.get("extracted_fields")
    if isinstance(extracted_fields, Mapping) and field_name in extracted_fields:
        return extracted_fields[field_name]
    fallback_column = {"customer_phone": "phone_number"}.get(field_name, field_name)
    return row.get(fallback_column)


def _has_meaningful_mapping(value: object) -> bool:
    if not isinstance(value, Mapping) or not value:
        return False
    return any(_has_meaningful_value(item) for item in value.values())


def _has_meaningful_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _has_warnings(row: Mapping[str, Any]) -> bool:
    warnings = _field_value(row, "scorecard_warnings")
    return isinstance(warnings, list) and len(warnings) > 0


def _has_safety_emergency_mismatch(row: Mapping[str, Any]) -> bool:
    direct_flag = row.get("safety_emergency_mismatch")
    if isinstance(direct_flag, bool):
        return direct_flag

    extracted_value = _field_value(row, "safety_emergency")
    for candidate in (
        row.get("expected_safety_emergency"),
        row.get("manual_safety_emergency"),
        ((row.get("raw_retell_payload") or {}).get("expected_extraction") or {}).get("safety_emergency"),
        ((row.get("raw_retell_payload") or {}).get("manual_review") or {}).get("safety_emergency"),
    ):
        if isinstance(candidate, bool):
            return bool(_has_meaningful_value(extracted_value)) and bool(extracted_value) != candidate
    return False


def _threshold_breached(metric_value: float, threshold: Mapping[str, Any]) -> bool:
    operator = threshold["operator"]
    target = float(threshold["value"])
    if operator == ">=":
        return metric_value >= target
    if operator == ">":
        return metric_value > target
    if operator == "<=":
        return metric_value <= target
    if operator == "<":
        return metric_value < target
    raise ValueError(f"Unsupported threshold operator: {operator}")


def _auto_resolve_recovered_detection_alerts(
    *,
    rows: list[Mapping[str, Any]],
    now: datetime,
    tenant_id: str | None,
    tenant_config: dict[str, Any],
) -> list[dict[str, Any]]:
    from harness.alerts.recovery import resolve_recovery_cooldown_minutes

    cooldown_minutes = resolve_recovery_cooldown_minutes(tenant_config)
    resolved_alerts: list[dict[str, Any]] = []
    for alert in list_alerts(tenant_id=tenant_id):
        if alert.get("status", "open") == "resolved":
            continue
        metrics = alert.get("metrics") or {}
        detection = metrics.get("detection") or {}
        if not isinstance(metrics, Mapping) or not isinstance(detection, Mapping):
            continue
        metric_name = metrics.get("metric_name")
        if not isinstance(metric_name, str):
            continue

        monitor_rows = _recent_rows_within_window(
            rows,
            window_minutes=int(metrics.get("window_minutes") or 0),
            now=now,
        )
        min_sample_size = int(metrics.get("min_sample_size") or 0)
        if len(monitor_rows) < min_sample_size:
            continue
        current_metrics = _compute_voice_metrics(monitor_rows)
        current_value = float(current_metrics.get(metric_name, 0.0))
        threshold = {
            "operator": metrics.get("threshold_operator", ">="),
            "value": metrics.get("threshold", 0.0),
        }
        if _threshold_breached(current_value, threshold):
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
                "resolved_by": "system:detection-recovery",
                "resolution_notes": f"Automatically resolved after {quiet_minutes} minutes below threshold",
                "metrics": {
                    **dict(metrics),
                    "recovered_value": current_value,
                    "cooldown_minutes": cooldown_minutes,
                },
            },
        )
        resolved_alerts.append(updated)
    return resolved_alerts
