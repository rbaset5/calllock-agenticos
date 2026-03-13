from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

from db.repository import (
    claim_scheduler_backlog_entries,
    count_active_jobs,
    get_tenant_config,
    list_audit_logs,
    list_scheduler_backlog,
    list_tenants,
    update_scheduler_backlog_entry,
    upsert_scheduler_backlog_entry,
)


DEFAULT_SCHEDULE = {
    "timezone": "UTC",
    "retention_local_hour": 3,
    "tenant_eval_local_hour": 4,
    "max_schedule_lag_hours": 24,
}
SCHEDULE_BUCKET_MINUTES = 15
SCHEDULE_BUCKET_COUNT = 4
DEFAULT_CLAIM_TTL_SECONDS = 600


def _resolved_timezone_name(timezone_name: str | None) -> str:
    candidate = timezone_name or DEFAULT_SCHEDULE["timezone"]
    if ZoneInfo is None:
        return DEFAULT_SCHEDULE["timezone"]
    try:
        ZoneInfo(candidate)
    except Exception:
        return DEFAULT_SCHEDULE["timezone"]
    return candidate


def _local_hour(utc_dt: datetime, timezone_name: str) -> int:
    if ZoneInfo is None:
        return utc_dt.hour
    return utc_dt.astimezone(ZoneInfo(timezone_name)).hour


def _local_minute(utc_dt: datetime, timezone_name: str) -> int:
    if ZoneInfo is None:
        return utc_dt.minute
    return utc_dt.astimezone(ZoneInfo(timezone_name)).minute


def _scheduled_hour(config: dict[str, Any], job_type: str) -> int:
    if job_type == "retention":
        return config.get("retention_local_hour", DEFAULT_SCHEDULE["retention_local_hour"])
    if job_type == "tenant_eval":
        return config.get("tenant_eval_local_hour", DEFAULT_SCHEDULE["tenant_eval_local_hour"])
    raise ValueError(f"Unsupported job_type: {job_type}")


def _schedulable_tenant(tenant: dict[str, Any]) -> bool:
    return tenant.get("status", "active") == "active"


def _schedule_key(tenant: dict[str, Any]) -> str:
    return tenant.get("slug") or tenant["id"]


def _scheduled_bucket(tenant: dict[str, Any]) -> int:
    key = _schedule_key(tenant)
    return sum(ord(char) for char in key) % SCHEDULE_BUCKET_COUNT


def _scheduled_minute(tenant: dict[str, Any]) -> int:
    return _scheduled_bucket(tenant) * SCHEDULE_BUCKET_MINUTES


def _bucket_for_minute(minute: int) -> int:
    return minute // SCHEDULE_BUCKET_MINUTES


def _scheduled_time_window(*, now: datetime, timezone_name: str, schedule_hour: int, schedule_minute: int) -> tuple[datetime, datetime]:
    if ZoneInfo is None:
        local_now = now
    else:
        local_now = now.astimezone(ZoneInfo(timezone_name))
    scheduled_local = local_now.replace(hour=schedule_hour, minute=schedule_minute, second=0, microsecond=0)
    next_scheduled_local = scheduled_local + timedelta(days=1)
    return scheduled_local.astimezone(timezone.utc), next_scheduled_local.astimezone(timezone.utc)


def _action_type_for(job_type: str) -> str:
    if job_type == "retention":
        return "retention.run"
    if job_type == "tenant_eval":
        return "eval.run"
    raise ValueError(f"Unsupported job_type: {job_type}")


def _audit_log_matches_job_type(log: dict[str, Any], job_type: str) -> bool:
    if job_type == "retention":
        return log.get("action_type") == "retention.run"
    if job_type == "tenant_eval":
        return log.get("action_type") == "eval.run" and log.get("reason") == "Run tenant eval suite"
    return False


def _latest_completion_since_schedule(
    *,
    tenant_id: str,
    job_type: str,
    scheduled_start_utc: datetime,
    next_scheduled_start_utc: datetime,
) -> str | None:
    logs = list_audit_logs(tenant_id=tenant_id, action_type=_action_type_for(job_type))
    matching = []
    for log in logs:
        if not _audit_log_matches_job_type(log, job_type):
            continue
        created_at = datetime.fromisoformat(log["created_at"].replace("Z", "+00:00"))
        if scheduled_start_utc <= created_at < next_scheduled_start_utc:
            matching.append(created_at)
    if not matching:
        return None
    return max(matching).isoformat()


def _claim_expired(entry: dict[str, Any], now: datetime) -> bool:
    claim_expires_at = entry.get("claim_expires_at")
    if not claim_expires_at:
        return True
    return datetime.fromisoformat(claim_expires_at.replace("Z", "+00:00")) <= now


def reconcile_scheduler_backlog(*, job_type: str, utc_iso: str | None = None) -> list[dict[str, Any]]:
    now = datetime.fromisoformat(utc_iso.replace("Z", "+00:00")) if utc_iso else datetime.now(timezone.utc)
    existing_entries = {
        (entry["tenant_id"], entry["job_type"], entry["scheduled_for"]): entry
        for entry in list_scheduler_backlog(job_type=job_type)
    }
    entries: list[dict[str, Any]] = []
    for tenant in list_tenants():
        if not _schedulable_tenant(tenant):
            continue
        config = get_tenant_config(tenant["id"])
        configured_timezone = config.get("timezone", DEFAULT_SCHEDULE["timezone"])
        resolved_timezone = _resolved_timezone_name(configured_timezone)
        local_hour = _local_hour(now, resolved_timezone)
        local_minute = _local_minute(now, resolved_timezone)
        schedule_hour = _scheduled_hour(config, job_type)
        schedule_minute = _scheduled_minute(tenant)
        scheduled_start_utc, next_scheduled_start_utc = _scheduled_time_window(
            now=now,
            timezone_name=resolved_timezone,
            schedule_hour=schedule_hour,
            schedule_minute=schedule_minute,
        )
        if now < scheduled_start_utc:
            continue
        max_schedule_lag_hours = config.get("max_schedule_lag_hours", DEFAULT_SCHEDULE["max_schedule_lag_hours"])
        existing_entry = existing_entries.get((tenant["id"], job_type, scheduled_start_utc.isoformat()))
        completed_at = _latest_completion_since_schedule(
            tenant_id=tenant["id"],
            job_type=job_type,
            scheduled_start_utc=scheduled_start_utc,
            next_scheduled_start_utc=next_scheduled_start_utc,
        )
        if completed_at is not None:
            status = "completed"
            claimed_by = None
            claimed_at = None
            claim_expires_at = None
        elif existing_entry and existing_entry.get("status") == "claimed" and not _claim_expired(existing_entry, now):
            status = "claimed"
            claimed_by = existing_entry.get("claimed_by")
            claimed_at = existing_entry.get("claimed_at")
            claim_expires_at = existing_entry.get("claim_expires_at")
        elif now - scheduled_start_utc > timedelta(hours=max_schedule_lag_hours):
            status = "expired"
            claimed_by = None
            claimed_at = None
            claim_expires_at = None
        else:
            status = "pending"
            claimed_by = None
            claimed_at = None
            claim_expires_at = None
        active_job_count = count_active_jobs(tenant["id"])
        max_active_jobs = config.get("max_active_jobs", 5)
        lateness = now - scheduled_start_utc
        entry = upsert_scheduler_backlog_entry(
            {
                "tenant_id": tenant["id"],
                "job_type": job_type,
                "scheduled_for": scheduled_start_utc.isoformat(),
                "status": status,
                "scheduled_timezone": resolved_timezone,
                "scheduled_hour": schedule_hour,
                "scheduled_minute": schedule_minute,
                "last_seen_at": now.isoformat(),
                "completed_at": completed_at,
                "claimed_by": claimed_by,
                "claimed_at": claimed_at,
                "claim_expires_at": claim_expires_at,
                "payload": {
                    "tenant_slug": tenant.get("slug"),
                    "tenant_name": tenant.get("name"),
                    "configured_timezone": configured_timezone,
                    "local_hour": local_hour,
                    "local_minute": local_minute,
                    "schedule_bucket": _bucket_for_minute(schedule_minute),
                    "active_job_count": active_job_count,
                    "max_active_jobs": max_active_jobs,
                    "capacity_remaining": max(0, max_active_jobs - active_job_count),
                    "catch_up": lateness.total_seconds() > 0,
                    "lateness_minutes": int(lateness.total_seconds() // 60),
                },
            }
        )
        entries.append(
            {
                "id": entry["id"],
                "tenant_id": tenant["id"],
                "tenant_slug": tenant.get("slug"),
                "tenant_name": tenant.get("name"),
                "timezone": resolved_timezone,
                "configured_timezone": configured_timezone,
                "job_type": job_type,
                "status": status,
                "local_hour": local_hour,
                "local_minute": local_minute,
                "scheduled_hour": schedule_hour,
                "scheduled_minute": schedule_minute,
                "scheduled_start_at": scheduled_start_utc.isoformat(),
                "schedule_bucket": _bucket_for_minute(schedule_minute),
                "claimed_by": claimed_by,
                "claimed_at": claimed_at,
                "claim_expires_at": claim_expires_at,
                "active_job_count": active_job_count,
                "max_active_jobs": max_active_jobs,
                "capacity_remaining": max(0, max_active_jobs - active_job_count),
                "catch_up": lateness.total_seconds() > 0,
                "lateness_minutes": int(lateness.total_seconds() // 60),
                "completed_at": completed_at,
            }
        )
    return entries


def list_scheduler_backlog_entries(
    *,
    tenant_id: str | None = None,
    job_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    entries = list_scheduler_backlog(tenant_id=tenant_id, job_type=job_type, status=status)
    normalized = []
    for entry in entries:
        payload = entry.get("payload", {})
        normalized.append(
            {
                "id": entry["id"],
                "tenant_id": entry["tenant_id"],
                "job_type": entry["job_type"],
                "status": entry["status"],
                "scheduled_start_at": entry["scheduled_for"],
                "scheduled_hour": entry["scheduled_hour"],
                "scheduled_minute": entry["scheduled_minute"],
                "timezone": entry.get("scheduled_timezone"),
                "last_seen_at": entry.get("last_seen_at"),
                "claimed_by": entry.get("claimed_by"),
                "claimed_at": entry.get("claimed_at"),
                "claim_expires_at": entry.get("claim_expires_at"),
                "completed_at": entry.get("completed_at"),
                **payload,
            }
        )
    return normalized


def due_tenants(*, job_type: str, utc_iso: str | None = None, max_tenants: int | None = None) -> list[dict[str, Any]]:
    due = [entry for entry in reconcile_scheduler_backlog(job_type=job_type, utc_iso=utc_iso) if entry["status"] == "pending"]
    due = sorted(
        due,
        key=lambda item: (
            -item["lateness_minutes"],
            item["active_job_count"] / max(item["max_active_jobs"], 1),
            item["scheduled_minute"],
            item.get("tenant_slug") or "",
            item["tenant_id"],
        ),
    )
    if max_tenants is not None:
        return due[:max_tenants]
    return due


def claim_due_tenants(
    *,
    job_type: str,
    utc_iso: str | None = None,
    max_tenants: int | None = None,
    claimer_id: str = "scheduler",
    claim_ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
) -> list[dict[str, Any]]:
    now = datetime.fromisoformat(utc_iso.replace("Z", "+00:00")) if utc_iso else datetime.now(timezone.utc)
    reconcile_scheduler_backlog(job_type=job_type, utc_iso=utc_iso)
    claimed_rows = claim_scheduler_backlog_entries(
        job_type=job_type,
        claimed_before_iso=now.isoformat(),
        max_entries=max_tenants or 100,
        claimer_id=claimer_id,
        claim_ttl_seconds=claim_ttl_seconds,
    )
    claimed_ids = {row["id"] for row in claimed_rows}
    claimed_index = {row["id"]: row for row in claimed_rows}
    normalized = []
    for entry in list_scheduler_backlog_entries(job_type=job_type, status="claimed"):
        if entry["id"] not in claimed_ids:
            continue
        row = claimed_index[entry["id"]]
        normalized.append(
            {
                **entry,
                "status": row["status"],
                "claimed_by": row.get("claimed_by"),
                "claimed_at": row.get("claimed_at"),
                "claim_expires_at": row.get("claim_expires_at"),
            }
        )
    normalized.sort(
        key=lambda item: (
            -item["lateness_minutes"],
            item["active_job_count"] / max(item["max_active_jobs"], 1),
            item["scheduled_minute"],
            item.get("tenant_slug") or "",
            item["tenant_id"],
        )
    )
    return normalized


def finalize_scheduler_claim(
    *,
    entry_id: str,
    action: str,
    actor_id: str,
    utc_iso: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    now = datetime.fromisoformat(utc_iso.replace("Z", "+00:00")) if utc_iso else datetime.now(timezone.utc)
    entries = list_scheduler_backlog_entries()
    entry = next(item for item in entries if item["id"] == entry_id)
    payload_updates = dict(entry.get("payload", {}))
    if note:
        payload_updates["scheduler_note"] = note
    if action == "complete":
        updated = update_scheduler_backlog_entry(
            entry_id,
            {
                "status": "completed",
                "completed_at": now.isoformat(),
                "claimed_by": None,
                "claimed_at": None,
                "claim_expires_at": None,
                "payload": payload_updates,
            },
        )
    elif action == "release":
        updated = update_scheduler_backlog_entry(
            entry_id,
            {
                "status": "pending",
                "claimed_by": None,
                "claimed_at": None,
                "claim_expires_at": None,
                "payload": payload_updates,
            },
        )
    else:
        raise ValueError(f"Unsupported finalize action: {action}")
    return next(item for item in list_scheduler_backlog_entries() if item["id"] == updated["id"])


def heartbeat_scheduler_claim(
    *,
    entry_id: str,
    actor_id: str,
    utc_iso: str | None = None,
    claim_ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
) -> dict[str, Any]:
    now = datetime.fromisoformat(utc_iso.replace("Z", "+00:00")) if utc_iso else datetime.now(timezone.utc)
    entry = next(item for item in list_scheduler_backlog_entries() if item["id"] == entry_id)
    if entry["status"] != "claimed":
        raise ValueError(f"Cannot heartbeat scheduler entry in status {entry['status']}")
    if entry.get("claimed_by") not in {None, actor_id}:
        raise ValueError(f"Scheduler entry is claimed by {entry.get('claimed_by')}, not {actor_id}")
    updated = update_scheduler_backlog_entry(
        entry_id,
        {
            "claimed_by": actor_id,
            "claimed_at": entry.get("claimed_at") or now.isoformat(),
            "claim_expires_at": (now + timedelta(seconds=claim_ttl_seconds)).isoformat(),
        },
    )
    return next(item for item in list_scheduler_backlog_entries() if item["id"] == updated["id"])


def sweep_stale_scheduler_claims(*, utc_iso: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    now = datetime.fromisoformat(utc_iso.replace("Z", "+00:00")) if utc_iso else datetime.now(timezone.utc)
    released: list[dict[str, Any]] = []
    for entry in list_scheduler_backlog_entries(status="claimed"):
        claim_expires_at = entry.get("claim_expires_at")
        if not claim_expires_at:
            continue
        if datetime.fromisoformat(claim_expires_at.replace("Z", "+00:00")) > now:
            continue
        released.append(
            {
                "id": entry["id"],
                "tenant_id": entry["tenant_id"],
                "tenant_slug": entry.get("tenant_slug"),
                "job_type": entry["job_type"],
                "claimed_by": entry.get("claimed_by"),
                "claim_expires_at": claim_expires_at,
            }
        )
        if not dry_run:
            update_scheduler_backlog_entry(
                entry["id"],
                {
                    "status": "pending",
                    "claimed_by": None,
                    "claimed_at": None,
                    "claim_expires_at": None,
                },
            )
    return {
        "evaluated_at": now.isoformat(),
        "released_count": len(released),
        "released": released,
        "dry_run": dry_run,
    }


def override_scheduler_claim(
    *,
    entry_id: str,
    action: str,
    actor_id: str,
    utc_iso: str | None = None,
    note: str = "",
    new_claimer_id: str | None = None,
    claim_ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
) -> dict[str, Any]:
    now = datetime.fromisoformat(utc_iso.replace("Z", "+00:00")) if utc_iso else datetime.now(timezone.utc)
    entry = next(item for item in list_scheduler_backlog_entries() if item["id"] == entry_id)
    if entry["status"] in {"completed", "expired"}:
        raise ValueError(f"Cannot override scheduler entry in status {entry['status']}")
    payload_updates = dict(entry.get("payload", {}))
    if note:
        payload_updates["override_note"] = note
    if action == "force_release":
        updated = update_scheduler_backlog_entry(
            entry_id,
            {
                "status": "pending",
                "claimed_by": None,
                "claimed_at": None,
                "claim_expires_at": None,
                "payload": payload_updates,
            },
        )
    elif action == "force_claim":
        effective_claimer = new_claimer_id or actor_id
        updated = update_scheduler_backlog_entry(
            entry_id,
            {
                "status": "claimed",
                "claimed_by": effective_claimer,
                "claimed_at": now.isoformat(),
                "claim_expires_at": (now + timedelta(seconds=claim_ttl_seconds)).isoformat(),
                "payload": payload_updates,
            },
        )
    else:
        raise ValueError(f"Unsupported override action: {action}")
    return next(item for item in list_scheduler_backlog_entries() if item["id"] == updated["id"])
