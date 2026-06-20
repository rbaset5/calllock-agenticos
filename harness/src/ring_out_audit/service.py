from __future__ import annotations

import csv
from datetime import datetime, time, timedelta, timezone
from io import StringIO
import random
from typing import Any
from zoneinfo import ZoneInfo

from db.repository import (
    create_ring_out_outcome,
    get_ring_out_attempt,
    get_tenant,
    list_ring_out_attempts,
    list_ring_out_prospects,
    list_scheduler_backlog,
    update_ring_out_attempt,
    update_ring_out_prospect,
    update_scheduler_backlog_entry,
    upsert_ring_out_attempt,
    upsert_ring_out_prospect,
    upsert_scheduler_backlog_entry,
)
from harness.control_plane.kill_switches import evaluate_kill_switches
from ring_out_audit.provider import CALL_TIMEOUT_SECONDS, RingOutProvider, provider_from_env


JOB_TYPE = "ring_out_audit_attempt"
WORKER_ID = "ring_out_audit"
IMPORT_CAP = 1000
MAX_ATTEMPTS_PER_PROSPECT = 3
LOCAL_WINDOW_START = time(0, 15)
LOCAL_WINDOW_END = time(4, 45)
WINDOW_SECONDS = (
    LOCAL_WINDOW_END.hour * 3600
    + LOCAL_WINDOW_END.minute * 60
    - LOCAL_WINDOW_START.hour * 3600
    - LOCAL_WINDOW_START.minute * 60
)
ATTEMPT_DAY_OFFSETS = (1, 4, 7)
REQUIRED_COLUMNS = ("prospect_id", "business_name", "phone", "timezone", "source_batch")
DECISIVE_OUTCOMES = {
    "ring_out_confirmed",
    "after_hours_voicemail",
    "covered_after_hours",
    "answered_before_timeout",
    "carrier_failed",
    "blocked_or_rejected",
    "invalid_number",
}
EXPORT_COLUMNS = (
    "prospect_id",
    "business_name",
    "phone",
    "timezone",
    "attempt_count",
    "first_decisive_outcome",
    "ringing_duration_seconds",
    "estimated_rings",
    "target_segment",
    "priority_score",
    "sales_angle",
)


def _parse_utc(value: str | None) -> datetime:
    if value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _duration_seconds(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return default


def _estimated_rings(duration_seconds: int) -> int:
    if duration_seconds <= 0:
        return 0
    return max(1, round(duration_seconds / 1.5))


def _score_outcome(outcome: str) -> dict[str, Any]:
    mapping = {
        "ring_out_confirmed": {
            "target_segment": "highest",
            "priority_score": 100,
            "sales_angle": "I called after hours and it rang until nobody picked up.",
        },
        "after_hours_voicemail": {
            "target_segment": "strong",
            "priority_score": 80,
            "sales_angle": "Their after-hours coverage drops to voicemail instead of qualifying and booking the caller.",
        },
        "covered_after_hours": {
            "target_segment": "deprioritized",
            "priority_score": 20,
            "sales_angle": "They appear to have after-hours coverage, so only pursue if other buying signals are strong.",
        },
        "answered_before_timeout": {
            "target_segment": "deprioritized",
            "priority_score": 10,
            "sales_angle": "The line answered before the ring-out threshold, so missed-call pain is not proven.",
        },
        "carrier_failed": {
            "target_segment": "no_score",
            "priority_score": 0,
            "sales_angle": "",
        },
        "blocked_or_rejected": {
            "target_segment": "no_score",
            "priority_score": 0,
            "sales_angle": "",
        },
        "invalid_number": {
            "target_segment": "no_score",
            "priority_score": 0,
            "sales_angle": "",
        },
        "ambiguous_failure": {
            "target_segment": "no_score",
            "priority_score": 0,
            "sales_angle": "",
        },
    }
    return mapping.get(outcome, mapping["ambiguous_failure"])


def _read_csv_rows(csv_text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(StringIO(csv_text))
    columns = tuple(reader.fieldnames or ())
    missing = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing:
        raise ValueError(f"Missing required CSV columns: {', '.join(missing)}")
    rows = [{key: (row.get(key) or "").strip() for key in REQUIRED_COLUMNS} for row in reader]
    if len(rows) > IMPORT_CAP:
        raise ValueError(f"Ring-out audit import is capped at {IMPORT_CAP} prospects per week")
    for index, row in enumerate(rows, start=2):
        empty = [key for key, value in row.items() if not value]
        if empty:
            raise ValueError(f"CSV row {index} has empty required fields: {', '.join(empty)}")
        try:
            ZoneInfo(row["timezone"])
        except Exception as exc:
            raise ValueError(f"CSV row {index} has invalid timezone: {row['timezone']}") from exc
    return rows


def _candidate_local_datetime(
    *,
    now_utc: datetime,
    prospect_timezone: str,
    day_offset: int,
    rng: random.Random,
) -> datetime:
    tz = ZoneInfo(prospect_timezone)
    base_local = now_utc.astimezone(tz).date() + timedelta(days=day_offset)
    seconds = rng.randint(0, WINDOW_SECONDS)
    start_seconds = LOCAL_WINDOW_START.hour * 3600 + LOCAL_WINDOW_START.minute * 60
    total_seconds = start_seconds + seconds
    hour = total_seconds // 3600
    minute = (total_seconds % 3600) // 60
    second = total_seconds % 60
    return datetime.combine(base_local, time(hour, minute, second), tzinfo=tz)


def _unique_scheduled_time(
    *,
    now_utc: datetime,
    prospect_timezone: str,
    day_offset: int,
    rng: random.Random,
    used_utc_values: set[str],
) -> tuple[datetime, datetime]:
    local_dt = _candidate_local_datetime(
        now_utc=now_utc,
        prospect_timezone=prospect_timezone,
        day_offset=day_offset,
        rng=rng,
    )
    start_seconds = LOCAL_WINDOW_START.hour * 3600 + LOCAL_WINDOW_START.minute * 60
    end_seconds = LOCAL_WINDOW_END.hour * 3600 + LOCAL_WINDOW_END.minute * 60
    while _iso_utc(local_dt) in used_utc_values:
        total_seconds = local_dt.hour * 3600 + local_dt.minute * 60 + local_dt.second + 1
        if total_seconds > end_seconds:
            total_seconds = start_seconds
        local_dt = local_dt.replace(
            hour=total_seconds // 3600,
            minute=(total_seconds % 3600) // 60,
            second=total_seconds % 60,
        )
    utc_dt = local_dt.astimezone(timezone.utc)
    used_utc_values.add(_iso_utc(utc_dt))
    return local_dt, utc_dt


def import_prospects_csv(
    csv_text: str,
    *,
    tenant_id: str,
    now_iso: str | None = None,
    random_seed: int | None = None,
) -> dict[str, Any]:
    rows = _read_csv_rows(csv_text)
    now_utc = _parse_utc(now_iso)
    tenant = get_tenant(tenant_id)
    canonical_tenant_id = tenant["id"]
    tenant_slug = tenant.get("slug", tenant_id)
    rng = random.Random(random_seed)
    existing_backlog = list_scheduler_backlog(job_type=JOB_TYPE)
    used_utc_values = {entry["scheduled_for"] for entry in existing_backlog}
    prospects_imported = 0
    attempts_scheduled = 0

    for row_index, row in enumerate(rows):
        prospect = upsert_ring_out_prospect(
            {
                "tenant_id": canonical_tenant_id,
                "tenant_slug": tenant_slug,
                "prospect_id": row["prospect_id"],
                "business_name": row["business_name"],
                "phone": row["phone"],
                "timezone": row["timezone"],
                "source_batch": row["source_batch"],
                "status": "scheduled",
                "attempt_count": 0,
                "first_decisive_outcome": None,
                "ringing_duration_seconds": None,
                "estimated_rings": None,
                "target_segment": None,
                "priority_score": 0,
                "sales_angle": "",
                "imported_at": _iso_utc(now_utc),
            }
        )
        prospects_imported += 1
        for attempt_number, day_offset in enumerate(ATTEMPT_DAY_OFFSETS, start=1):
            local_dt, utc_dt = _unique_scheduled_time(
                now_utc=now_utc,
                prospect_timezone=row["timezone"],
                day_offset=day_offset,
                rng=rng,
                used_utc_values=used_utc_values,
            )
            attempt_id = f"ringout-{canonical_tenant_id}-{row['source_batch']}-{row['prospect_id']}-{attempt_number}"
            attempt = upsert_ring_out_attempt(
                {
                    "attempt_id": attempt_id,
                    "tenant_id": canonical_tenant_id,
                    "tenant_slug": tenant_slug,
                    "prospect_id": row["prospect_id"],
                    "prospect_record_id": prospect["id"],
                    "business_name": row["business_name"],
                    "phone": row["phone"],
                    "timezone": row["timezone"],
                    "source_batch": row["source_batch"],
                    "attempt_number": attempt_number,
                    "status": "pending",
                    "scheduled_for": _iso_utc(utc_dt),
                    "scheduled_for_local": local_dt.isoformat(),
                }
            )
            backlog = upsert_scheduler_backlog_entry(
                {
                    "tenant_id": canonical_tenant_id,
                    "job_type": JOB_TYPE,
                    "scheduled_for": attempt["scheduled_for"],
                    "status": "pending",
                    "scheduled_timezone": row["timezone"],
                    "scheduled_hour": local_dt.hour,
                    "scheduled_minute": local_dt.minute,
                    "payload": {
                        "attempt_id": attempt_id,
                        "prospect_id": row["prospect_id"],
                        "source_batch": row["source_batch"],
                        "phone": row["phone"],
                        "scheduled_for_local": attempt["scheduled_for_local"],
                        "import_row_index": row_index,
                    },
                }
            )
            upsert_ring_out_attempt({**attempt, "scheduler_backlog_id": backlog["id"]})
            attempts_scheduled += 1

    return {
        "prospects_imported": prospects_imported,
        "attempts_scheduled": attempts_scheduled,
        "source_batches": sorted({row["source_batch"] for row in rows}),
    }


def _prospect_has_decisive_outcome(prospect_id: str, *, tenant_id: str | None = None) -> bool:
    prospects = list_ring_out_prospects(tenant_id=tenant_id, prospect_id=prospect_id)
    return any(prospect.get("first_decisive_outcome") in DECISIVE_OUTCOMES for prospect in prospects)


def _has_inflight_attempt(prospect_id: str, *, tenant_id: str) -> bool:
    return any(
        attempt.get("status") == "dialing"
        for attempt in list_ring_out_attempts(prospect_id, tenant_id=tenant_id)
    )


def _find_attempt_for_backlog(entry: dict[str, Any]) -> dict[str, Any] | None:
    attempt_id = (entry.get("payload") or {}).get("attempt_id")
    if not attempt_id:
        return None
    try:
        return get_ring_out_attempt(attempt_id)
    except KeyError:
        return None


def _provider_name(provider: RingOutProvider) -> str:
    return provider.__class__.__name__.replace("RingOutProvider", "").replace("Provider", "").lower() or "unknown"


def claim_due_audit_attempts(
    *,
    utc_iso: str | None = None,
    max_attempts: int = 25,
    claimer_id: str = "ring-out-worker",
    provider: RingOutProvider | None = None,
) -> dict[str, Any]:
    kill_switch = evaluate_kill_switches(worker_id=WORKER_ID)
    if kill_switch:
        return {
            "blocked": True,
            "reason": kill_switch.get("reason", "Ring-out audit worker paused"),
            "dialed": [],
        }

    now_utc = _parse_utc(utc_iso)
    provider = provider or provider_from_env()
    due_entries = [
        entry
        for entry in list_scheduler_backlog(job_type=JOB_TYPE, status="pending")
        if _parse_utc(entry["scheduled_for"]) <= now_utc
    ]
    due_entries.sort(key=lambda entry: entry["scheduled_for"])

    dialed: list[dict[str, Any]] = []
    seen_prospects: set[tuple[str, str]] = set()
    for entry in due_entries:
        if len(dialed) >= max_attempts:
            break
        attempt = _find_attempt_for_backlog(entry)
        if not attempt or attempt.get("status") != "pending":
            update_scheduler_backlog_entry(entry["id"], {"status": "completed", "completed_at": _iso_utc(now_utc)})
            continue
        prospect_key = (attempt["tenant_id"], attempt["prospect_id"])
        if prospect_key in seen_prospects:
            continue
        seen_prospects.add(prospect_key)
        tenant_switch = evaluate_kill_switches(tenant_id=attempt["tenant_id"], worker_id=WORKER_ID)
        if tenant_switch:
            continue
        if _prospect_has_decisive_outcome(attempt["prospect_id"], tenant_id=attempt["tenant_id"]):
            update_ring_out_attempt(attempt["attempt_id"], {"status": "skipped", "skipped_reason": "decisive_outcome"})
            update_scheduler_backlog_entry(entry["id"], {"status": "completed", "completed_at": _iso_utc(now_utc)})
            continue
        if _has_inflight_attempt(attempt["prospect_id"], tenant_id=attempt["tenant_id"]):
            continue

        update_ring_out_attempt(
            attempt["attempt_id"],
            {
                "status": "dialing",
                "claimed_by": claimer_id,
                "claimed_at": _iso_utc(now_utc),
                "provider": _provider_name(provider),
            },
        )
        update_scheduler_backlog_entry(
            entry["id"],
            {
                "status": "claimed",
                "claimed_by": claimer_id,
                "claimed_at": _iso_utc(now_utc),
                "claim_expires_at": _iso_utc(now_utc + timedelta(seconds=300)),
            },
        )
        call = provider.place_call({**attempt, "claimed_by": claimer_id})
        updated = update_ring_out_attempt(
            attempt["attempt_id"],
            {
                "status": "dialing",
                "call_sid": call["call_sid"],
                "provider_status": call.get("provider_status"),
                "placed_at": _iso_utc(now_utc),
            },
        )
        update_scheduler_backlog_entry(
            entry["id"],
            {
                "status": "completed",
                "completed_at": _iso_utc(now_utc),
                "payload": {**entry.get("payload", {}), "call_sid": call["call_sid"]},
            },
        )
        dialed.append({**call, "attempt_id": updated["attempt_id"]})

    return {"blocked": False, "dialed": dialed}


def classify_status_callback(payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("CallStatus") or payload.get("call_status") or "").strip().lower()
    answered_by = str(payload.get("AnsweredBy") or payload.get("AnsweredByResult") or "").strip().lower()
    error_code = str(payload.get("ErrorCode") or "").strip()
    duration = _duration_seconds(payload.get("CallDuration"), default=0)

    invalid_error_codes = {"21211", "13224"}
    blocked_statuses = {"busy", "rejected"}
    failed_statuses = {"failed", "canceled"}

    if answered_by.startswith("machine"):
        outcome = "after_hours_voicemail"
    elif answered_by in {"human", "human_start"}:
        outcome = "covered_after_hours"
    elif error_code in invalid_error_codes:
        outcome = "invalid_number"
    elif status in blocked_statuses:
        outcome = "blocked_or_rejected"
    elif status == "no-answer":
        duration = duration or CALL_TIMEOUT_SECONDS
        outcome = "ring_out_confirmed" if duration >= CALL_TIMEOUT_SECONDS - 2 else "ambiguous_failure"
    elif status == "completed":
        outcome = "answered_before_timeout" if duration < CALL_TIMEOUT_SECONDS else "covered_after_hours"
    elif status in failed_statuses:
        outcome = "carrier_failed"
    else:
        outcome = "ambiguous_failure"

    return {
        "outcome": outcome,
        "call_status": status,
        "answered_by": answered_by,
        "ringing_duration_seconds": duration,
        "estimated_rings": _estimated_rings(duration),
        "error_code": error_code,
    }


def _skip_remaining_attempts(prospect_id: str, *, tenant_id: str, now_iso: str, reason: str) -> None:
    for attempt in list_ring_out_attempts(prospect_id, tenant_id=tenant_id):
        if attempt.get("status") != "pending":
            continue
        update_ring_out_attempt(attempt["attempt_id"], {"status": "skipped", "skipped_reason": reason})
        backlog_id = attempt.get("scheduler_backlog_id")
        if backlog_id:
            update_scheduler_backlog_entry(backlog_id, {"status": "completed", "completed_at": now_iso})


def process_twilio_status_callback(payload: dict[str, Any], *, now_iso: str | None = None) -> dict[str, Any]:
    raw_payload = dict(payload)
    call_sid = str(raw_payload.get("CallSid") or raw_payload.get("call_sid") or "").strip()
    if not call_sid:
        raise ValueError("Twilio status callback missing CallSid")
    attempts = list_ring_out_attempts(call_sid=call_sid)
    if not attempts:
        raise KeyError(f"Unknown ring-out call SID: {call_sid}")
    attempt = attempts[0]
    if attempt.get("status") == "completed" and attempt.get("outcome") in DECISIVE_OUTCOMES:
        prospects = list_ring_out_prospects(tenant_id=attempt["tenant_id"], prospect_id=attempt["prospect_id"])
        prospect = prospects[0] if prospects else {}
        return {
            "call_sid": call_sid,
            "attempt_id": attempt["attempt_id"],
            "prospect_id": attempt["prospect_id"],
            "outcome": attempt["outcome"],
            "target_segment": prospect.get("target_segment"),
            "priority_score": prospect.get("priority_score"),
            "duplicate": True,
        }
    now = _iso_utc(_parse_utc(now_iso))
    classified = classify_status_callback(raw_payload)
    outcome = classified["outcome"]

    create_ring_out_outcome(
        {
            "tenant_id": attempt["tenant_id"],
            "prospect_id": attempt["prospect_id"],
            "attempt_id": attempt["attempt_id"],
            "call_sid": call_sid,
            "outcome": outcome,
            "call_status": classified["call_status"],
            "answered_by": classified["answered_by"],
            "ringing_duration_seconds": classified["ringing_duration_seconds"],
            "estimated_rings": classified["estimated_rings"],
            "error_code": classified["error_code"],
            "raw_payload": raw_payload,
            "created_at": now,
        }
    )
    update_ring_out_attempt(
        attempt["attempt_id"],
        {
            "status": "completed",
            "completed_at": now,
            "outcome": outcome,
            "call_status": classified["call_status"],
            "answered_by": classified["answered_by"],
            "ringing_duration_seconds": classified["ringing_duration_seconds"],
            "estimated_rings": classified["estimated_rings"],
        },
    )

    attempts_for_prospect = list_ring_out_attempts(attempt["prospect_id"], tenant_id=attempt["tenant_id"])
    attempt_count = len([record for record in attempts_for_prospect if record.get("status") == "completed"])
    prospect_updates = {
        "attempt_count": attempt_count,
        "last_outcome": outcome,
        "last_outcome_at": now,
        "ringing_duration_seconds": classified["ringing_duration_seconds"],
        "estimated_rings": classified["estimated_rings"],
    }
    if outcome in DECISIVE_OUTCOMES:
        prospect_updates.update(
            {
                "status": "decisive",
                "first_decisive_outcome": outcome,
                **_score_outcome(outcome),
            }
        )
        _skip_remaining_attempts(attempt["prospect_id"], tenant_id=attempt["tenant_id"], now_iso=now, reason=outcome)
    else:
        prospect_updates.update({"status": "retry_pending", **_score_outcome(outcome)})
    prospect = update_ring_out_prospect(attempt["prospect_id"], prospect_updates, tenant_id=attempt["tenant_id"])

    return {
        "call_sid": call_sid,
        "attempt_id": attempt["attempt_id"],
        "prospect_id": attempt["prospect_id"],
        "outcome": outcome,
        "target_segment": prospect.get("target_segment"),
        "priority_score": prospect.get("priority_score"),
    }


def export_scored_csv(*, source_batch: str | None = None, tenant_id: str | None = None) -> str:
    prospects = list_ring_out_prospects(tenant_id=tenant_id, source_batch=source_batch)
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(EXPORT_COLUMNS))
    writer.writeheader()
    for prospect in prospects:
        writer.writerow(
            {
                "prospect_id": prospect.get("prospect_id", ""),
                "business_name": prospect.get("business_name", ""),
                "phone": prospect.get("phone", ""),
                "timezone": prospect.get("timezone", ""),
                "attempt_count": prospect.get("attempt_count") or 0,
                "first_decisive_outcome": prospect.get("first_decisive_outcome") or "",
                "ringing_duration_seconds": prospect.get("ringing_duration_seconds") or "",
                "estimated_rings": prospect.get("estimated_rings") or "",
                "target_segment": prospect.get("target_segment") or "",
                "priority_score": prospect.get("priority_score") or 0,
                "sales_angle": prospect.get("sales_angle") or "",
            }
        )
    return buffer.getvalue()
