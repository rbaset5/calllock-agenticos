from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from db.repository import list_alerts, list_approval_requests, list_audit_logs, list_customer_content, list_experiments, list_incidents, list_jobs, list_kill_switches, list_scheduler_backlog
from harness.resilience.recovery_journal import journal_root
from observability.langsmith_tracer import trace_root


def _local_trace_count() -> int:
    root = trace_root()
    if not root.exists():
        return 0
    count = 0
    for path in root.rglob("local-traces.jsonl"):
        if path.is_file():
            count += sum(1 for _ in path.open("r", encoding="utf-8"))
    return count


def _recovery_entry_count() -> int:
    root = journal_root()
    if not root.exists():
        return 0
    count = 0
    for path in root.rglob("*.jsonl"):
        if path.is_file():
            count += sum(1 for _ in path.open("r", encoding="utf-8"))
    return count


def _parse_iso(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def cockpit_overview() -> dict:
    jobs = list_jobs()
    alerts = list_alerts()
    incidents = list_incidents()
    unresolved_alerts = [alert for alert in alerts if alert.get("status", "open") != "resolved"]
    return {
        "portfolio_kpis": {
            "jobs_total": len(jobs),
            "jobs_failed": sum(1 for job in jobs if job["status"] == "failed"),
            "alerts_open": len(unresolved_alerts),
            "alerts_escalated": sum(1 for alert in alerts if alert.get("status") == "escalated"),
            "alert_occurrences_total": sum(int(alert.get("occurrence_count", 1)) for alert in alerts),
            "incidents_open": sum(1 for incident in incidents if incident.get("status") != "resolved"),
            "incidents_acknowledged": sum(1 for incident in incidents if incident.get("workflow_status") == "acknowledged"),
            "incident_reminders_sent": sum(int(incident.get("reminder_count", 0)) for incident in incidents),
            "local_trace_count": _local_trace_count(),
            "recovery_entry_count": _recovery_entry_count(),
            "audit_log_count": len(list_audit_logs()),
            "approval_request_count": len(list_approval_requests(status="pending")),
            "scheduler_backlog_pending": len(list_scheduler_backlog(status="pending")),
            "scheduler_backlog_claimed": len(list_scheduler_backlog(status="claimed")),
        },
        "kill_switches": list_kill_switches(active_only=True),
        "alerts": alerts,
        "incidents": incidents,
        "experiments": list_experiments(),
        "content_records": len(list_customer_content("00000000-0000-0000-0000-000000000001")),
    }


def cockpit_scheduler_view(*, now_iso: str | None = None) -> dict:
    now = _parse_iso(now_iso) or datetime.now(timezone.utc)
    backlog = list_scheduler_backlog()
    scheduler_logs = [
        log
        for log in list_audit_logs()
        if log["action_type"].startswith("schedule.")
    ]
    counts = {
        "pending": sum(1 for entry in backlog if entry["status"] == "pending"),
        "claimed": sum(1 for entry in backlog if entry["status"] == "claimed"),
        "completed": sum(1 for entry in backlog if entry["status"] == "completed"),
        "expired": sum(1 for entry in backlog if entry["status"] == "expired"),
    }
    pending_entries = []
    expiring_claims = []
    for entry in backlog:
        payload = entry.get("payload", {})
        base = {
            "id": entry["id"],
            "tenant_id": entry["tenant_id"],
            "tenant_slug": payload.get("tenant_slug"),
            "job_type": entry["job_type"],
            "scheduled_start_at": entry["scheduled_for"],
            "lateness_minutes": payload.get("lateness_minutes", 0),
            "claimed_by": entry.get("claimed_by"),
            "claim_expires_at": entry.get("claim_expires_at"),
        }
        if entry["status"] == "pending":
            pending_entries.append(base)
        elif entry["status"] == "claimed":
            claim_expires_at = _parse_iso(entry.get("claim_expires_at"))
            if claim_expires_at and claim_expires_at <= now + timedelta(minutes=15):
                expiring_claims.append(
                    {
                        **base,
                        "minutes_until_expiry": max(0, int((claim_expires_at - now).total_seconds() // 60)),
                    }
                )
    pending_entries.sort(key=lambda item: (-item["lateness_minutes"], item["scheduled_start_at"], item.get("tenant_slug") or ""))
    expiring_claims.sort(key=lambda item: (item["minutes_until_expiry"], item["scheduled_start_at"]))
    recent_activity = sorted(
        scheduler_logs,
        key=lambda item: item["created_at"],
        reverse=True,
    )[:10]
    return {
        "counts": counts,
        "oldest_pending": pending_entries[:10],
        "claims_expiring_soon": expiring_claims[:10],
        "recent_activity": recent_activity,
    }
