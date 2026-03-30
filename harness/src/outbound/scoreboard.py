from __future__ import annotations

import concurrent.futures
import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

try:
    from litellm import completion
except Exception:  # pragma: no cover
    completion = None  # type: ignore[assignment]

from . import store
from .constants import OUTBOUND_TENANT_ID
from .daily_plan import current_week_number, get_daily_sprint_count, is_calling_day, load_schedule

logger = logging.getLogger(__name__)


def _week_config(schedule: dict[str, Any], week_num: int) -> dict[str, Any]:
    weeks = schedule.get("weeks", {})
    return weeks.get(week_num) or weeks.get(str(week_num)) or {}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _daily_target_for_date(schedule: dict[str, Any], day: date) -> int:
    week_num = current_week_number(schedule, day)
    if week_num <= 0 or not is_calling_day(schedule, week_num, day):
        return 0
    week_cfg = _week_config(schedule, week_num)
    dials_per_sprint = int(week_cfg.get("dials_per_sprint", schedule.get("dials_per_sprint", 10)) or 10)
    return get_daily_sprint_count(schedule, week_num, day) * dials_per_sprint


def _scheduled_days_between(schedule: dict[str, Any], start: date, end: date) -> list[date]:
    days: list[date] = []
    cur = start
    while cur <= end:
        week_num = current_week_number(schedule, cur)
        if week_num > 0 and is_calling_day(schedule, week_num, cur):
            days.append(cur)
        cur += timedelta(days=1)
    return days


def _completed_call(row: dict[str, Any]) -> bool:
    outcome = str(row.get("outcome") or "")
    outcome_type = str(row.get("call_outcome_type") or "")
    return outcome != "dial_started" and outcome_type != "dial_started"


def _extract_dates(date_range: Any, today: date) -> tuple[date, date]:
    if isinstance(date_range, tuple) and len(date_range) == 2:
        return date_range[0], date_range[1]
    if isinstance(date_range, dict):
        start = date.fromisoformat(str(date_range.get("start")))
        end = date.fromisoformat(str(date_range.get("end")))
        return start, end
    if isinstance(date_range, int):
        return today - timedelta(days=max(0, date_range - 1)), today
    return today - timedelta(days=6), today


def format_progress_bar(current: int, target: int, width: int = 20) -> str:
    if target <= 0:
        return f"[{'-' * width}] 0% ({current}/{target})"
    ratio = min(max(float(current) / float(target), 0.0), 1.0)
    filled = int(round(width * ratio))
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {int(ratio * 100)}% ({current}/{target})"


def sprint_scoreboard(tenant_id: str = OUTBOUND_TENANT_ID, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    schedule = load_schedule()
    if not schedule:
        return {
            "daily_dials": 0,
            "daily_target": 0,
            "weekly_dials": 0,
            "weekly_target": 0,
            "total_dials": 0,
            "connect_rate": 0.0,
            "day_number": 0,
            "error": "schedule_missing",
        }

    start_date = date.fromisoformat(str(schedule.get("start_date", today.isoformat())))
    week_num = current_week_number(schedule, today)
    week_cfg = _week_config(schedule, week_num) if week_num > 0 else {}

    daily_target = _daily_target_for_date(schedule, today)

    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    weekly_target = sum(_daily_target_for_date(schedule, day) for day in _scheduled_days_between(schedule, week_start, week_end))

    scheduled_to_today = _scheduled_days_between(schedule, start_date, today)
    cumulative_target = sum(_daily_target_for_date(schedule, day) for day in scheduled_to_today)

    max_week = max((int(k) for k in schedule.get("weeks", {}).keys()), default=0)
    end_by_week = start_date + timedelta(days=max(0, max_week * 7 - 1))
    deadline_raw = schedule.get("deadline")
    deadline = date.fromisoformat(deadline_raw) if deadline_raw else end_by_week
    deadline = max(deadline, start_date)
    all_scheduled_days = _scheduled_days_between(schedule, start_date, deadline)

    try:
        raw = store.sprint_scoreboard(
            tenant_id=tenant_id,
            start_date=start_date.isoformat(),
            today=today.isoformat(),
        )
    except Exception as exc:
        logger.exception("Failed sprint_scoreboard RPC")
        raw = {"error": str(exc)}

    daily_dials = int(raw.get("daily_dials", 0) or 0)
    daily_connects = int(raw.get("daily_connects", 0) or 0)
    daily_demos = int(raw.get("daily_demos", 0) or 0)
    daily_close_attempts = int(raw.get("daily_close_attempts", raw.get("daily_close_attempts", 0)) or 0)

    streak = streak_counter(tenant_id, today, schedule)
    used_working_days = len(scheduled_to_today)
    remaining_working_days = max(len(all_scheduled_days) - used_working_days, 0)
    recent_heat_map = heat_map(tenant_id, {"start": (today - timedelta(days=6)).isoformat(), "end": today.isoformat()})
    recent_objections = objection_summary(tenant_id, {"start": (today - timedelta(days=6)).isoformat(), "end": today.isoformat()})

    return {
        "week": week_num,
        "day_number": max((today - start_date).days + 1, 0) if today >= start_date else 0,
        "daily_dials": daily_dials,
        "daily_target": daily_target,
        "live_conversations": daily_connects,
        "connect_rate": round((daily_connects / daily_dials) * 100, 1) if daily_dials > 0 else 0.0,
        "demos_booked_today": daily_demos,
        "close_attempts_today": daily_close_attempts,
        "callbacks_completed": int(raw.get("callbacks_completed", 0) or 0),
        "weekly_dials": int(raw.get("weekly_dials", 0) or 0),
        "weekly_target": weekly_target,
        "weekly_convos": int(raw.get("weekly_connects", raw.get("weekly_convos", 0)) or 0),
        "weekly_demos": int(raw.get("weekly_demos", 0) or 0),
        "total_dials": int(raw.get("total_dials", 0) or 0),
        "total_convos": int(raw.get("total_connects", raw.get("total_convos", 0)) or 0),
        "total_demos": int(raw.get("total_demos", 0) or 0),
        "total_closes": int(raw.get("total_closes", 0) or 0),
        "customers_signed": int(raw.get("customers_signed", 0) or 0),
        "days_to_deadline": max((deadline - today).days, 0),
        "working_days_used": used_working_days,
        "working_days_remaining": remaining_working_days,
        "total_target": cumulative_target,
        "dials_per_sprint": int(week_cfg.get("dials_per_sprint", schedule.get("dials_per_sprint", 10)) or 10),
        "streak": streak,
        "heat_map": recent_heat_map,
        "objection_summary": recent_objections,
        **({"error": str(raw.get("error"))} if raw.get("error") else {}),
    }


def streak_counter(
    tenant_id: str = OUTBOUND_TENANT_ID,
    today: date | None = None,
    schedule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    schedule = schedule or load_schedule()
    if not schedule:
        return {"current_streak": 0, "best_streak": 0, "streak_start_date": None}

    start_date = date.fromisoformat(str(schedule.get("start_date", today.isoformat())))
    if today < start_date:
        return {"current_streak": 0, "best_streak": 0, "streak_start_date": None}

    # Only fetch calls in the relevant date range (start_date..today), not all calls
    try:
        calls = store.list_outbound_calls(
            tenant_id=tenant_id,
            start_date=start_date.isoformat(),
            end_date=today.isoformat(),
        )
    except TypeError:
        # Fallback if store doesn't support date filters yet
        calls = store.list_outbound_calls(tenant_id=tenant_id)
    counts: dict[date, int] = defaultdict(int)
    for row in calls:
        if not _completed_call(row):
            continue
        called_at = _parse_datetime(row.get("called_at"))
        if called_at is None:
            continue
        counts[called_at.date()] += 1

    scheduled_days = _scheduled_days_between(schedule, start_date, today)
    status: list[tuple[date, bool]] = []
    for day in scheduled_days:
        target = _daily_target_for_date(schedule, day)
        status.append((day, target > 0 and counts.get(day, 0) >= target))

    best_streak = 0
    running = 0
    for _, success in status:
        if success:
            running += 1
            best_streak = max(best_streak, running)
        else:
            running = 0

    current_streak = 0
    current_start: date | None = None
    for day, success in reversed(status):
        if success:
            current_streak += 1
            current_start = day
        else:
            break

    return {
        "current_streak": current_streak,
        "best_streak": best_streak,
        "streak_start_date": current_start.isoformat() if current_start else None,
    }


def heat_map(tenant_id: str = OUTBOUND_TENANT_ID, date_range: Any = None) -> dict[str, dict[str, dict[str, float | int]]]:
    today = date.today()
    start, end = _extract_dates(date_range, today)
    try:
        rows = store.list_outbound_calls(tenant_id=tenant_id, start_date=start.isoformat(), end_date=end.isoformat())
    except TypeError:
        rows = store.list_outbound_calls(tenant_id=tenant_id)
    prospect_map = {
        row.get("id"): row
        for row in store.list_outbound_prospects(tenant_id=tenant_id)
    }

    result: dict[str, dict[str, dict[str, float | int]]] = {}

    for row in rows:
        called_at = _parse_datetime(row.get("called_at"))
        if called_at is None:
            continue
        call_day = called_at.date()
        if call_day < start or call_day > end:
            continue

        prospect = prospect_map.get(row.get("prospect_id"))
        metro = str(row.get("metro") or (prospect or {}).get("metro") or "unknown").strip() or "unknown"
        slot_start = called_at.hour
        slot_end = (slot_start + 1) % 24
        slot = f"{slot_start:02d}:00-{slot_end:02d}:00"

        metro_bucket = result.setdefault(metro, {})
        slot_bucket = metro_bucket.setdefault(slot, {"dials": 0, "connects": 0, "rate": 0.0})

        outcome = str(row.get("outcome") or "")
        # Count every completed call as a dial (not dial_started events)
        if _completed_call(row):
            slot_bucket["dials"] = int(slot_bucket["dials"]) + 1
        if outcome.startswith("answered_"):
            slot_bucket["connects"] = int(slot_bucket["connects"]) + 1

    for metro_slots in result.values():
        for slot_bucket in metro_slots.values():
            dials = int(slot_bucket["dials"])
            connects = int(slot_bucket["connects"])
            slot_bucket["rate"] = round((connects / dials), 4) if dials > 0 else 0.0

    return result


def objection_summary(tenant_id: str = OUTBOUND_TENANT_ID, date_range: Any = None) -> list[dict[str, Any]]:
    today = date.today()
    start, end = _extract_dates(date_range, today)
    try:
        rows = store.list_outbound_calls(tenant_id=tenant_id, start_date=start.isoformat(), end_date=end.isoformat())
    except TypeError:
        rows = store.list_outbound_calls(tenant_id=tenant_id)

    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        called_at = _parse_datetime(row.get("called_at"))
        if called_at is None or not (start <= called_at.date() <= end):
            continue

        transcript = str(row.get("transcript") or "")
        if len(transcript.strip()) < 50:
            continue

        extraction = row.get("extraction") or {}
        if not isinstance(extraction, dict):
            continue
        objection = str(extraction.get("objection_type") or "").strip().lower()
        if not objection or objection == "none":
            continue

        bucket = groups.setdefault(
            objection,
            {
                "objection": objection,
                "count": 0,
                "example": str(extraction.get("objection_verbatim") or transcript[:120]).strip(),
            },
        )
        bucket["count"] += 1

    return sorted(groups.values(), key=lambda item: int(item.get("count", 0)), reverse=True)[:3]


def _call_llm_json(messages: list[dict[str, str]], timeout_seconds: int = 15) -> Any:
    if completion is None:
        raise RuntimeError("litellm is not installed")

    def _run() -> str:
        response = completion(
            model="claude-sonnet-4-6",
            messages=messages,
            temperature=0,
        )
        return str(response.choices[0].message.content)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        try:
            raw = future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError(f"LLM call timed out after {timeout_seconds}s")

    # Strip markdown code fences that LLMs frequently add
    stripped = raw.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        # Remove first line (```json or ```) and last line (```)
        if len(lines) >= 2:
            stripped = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return json.loads(stripped)


def tactical_recommendations(tenant_id: str = OUTBOUND_TENANT_ID, today: date | None = None) -> list[dict[str, str]]:
    today = today or date.today()
    start = today - timedelta(days=2)
    try:
        rows = store.list_outbound_calls(tenant_id=tenant_id, start_date=start.isoformat(), end_date=today.isoformat())
    except TypeError:
        rows = store.list_outbound_calls(tenant_id=tenant_id)

    window = []
    for row in rows:
        called_at = _parse_datetime(row.get("called_at"))
        if called_at is None:
            continue
        if start <= called_at.date() <= today and _completed_call(row):
            window.append(row)

    if not window:
        return []

    dials = len(window)
    connects = sum(1 for row in window if str(row.get("outcome") or "").startswith("answered_"))
    connect_rate = round((connects / dials) * 100, 1) if dials else 0.0
    top_objections = objection_summary(tenant_id, {"start": start.isoformat(), "end": today.isoformat()})

    try:
        parsed = _call_llm_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Return strict JSON: a list of objects with keys recommendation and data_point. "
                        "Keep each recommendation concise and tactical for outbound calling."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "window_days": 3,
                            "dials": dials,
                            "connects": connects,
                            "connect_rate": connect_rate,
                            "top_objections": top_objections,
                        }
                    ),
                },
            ],
            timeout_seconds=15,
        )
    except Exception:
        logger.exception("tactical_recommendations failed")
        return []

    if not isinstance(parsed, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        recommendation = str(item.get("recommendation") or "").strip()
        data_point = str(item.get("data_point") or "").strip()
        if not recommendation or not data_point:
            continue
        normalized.append({"recommendation": recommendation, "data_point": data_point})

    return normalized[:3]


def auto_adjust_analysis(tenant_id: str = OUTBOUND_TENANT_ID, schedule: dict[str, Any] | None = None) -> dict[str, Any] | None:
    schedule = schedule or load_schedule()
    if not schedule:
        return None

    try:
        all_rows = store.list_outbound_calls(tenant_id=tenant_id, start_date=None, end_date=None)
    except TypeError:
        all_rows = store.list_outbound_calls(tenant_id=tenant_id)
    rows = [row for row in all_rows if _completed_call(row)]
    if not rows:
        return None

    call_days: list[date] = []
    for row in rows:
        dt = _parse_datetime(row.get("called_at"))
        if dt is not None:
            call_days.append(dt.date())
    call_days = sorted(set(call_days))
    scheduled_data_days = [
        day
        for day in call_days
        if current_week_number(schedule, day) > 0 and is_calling_day(schedule, current_week_number(schedule, day), day)
    ]
    if len(scheduled_data_days) < 5:
        return None

    end_day = max(call_days)
    start_day = end_day - timedelta(days=13)
    heat = heat_map(tenant_id, {"start": start_day.isoformat(), "end": end_day.isoformat()})

    metro_keys = {str(key) for key in (schedule.get("metro_timezones") or {}).keys()}
    if not metro_keys:
        for row in rows:
            metro = str(row.get("metro") or "").strip()
            if metro:
                metro_keys.add(metro)

    try:
        parsed = _call_llm_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Return strict JSON object with keys advisory (string) and suggestions (array). "
                        "Each suggestion must include metro, slot, and recommended_sprints integer."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"heat_map": heat, "metro_keys": sorted(metro_keys)}),
                },
            ],
            timeout_seconds=15,
        )
    except Exception:
        logger.exception("auto_adjust_analysis failed")
        return None

    if not isinstance(parsed, dict):
        return None

    suggestions = parsed.get("suggestions")
    if not isinstance(suggestions, list):
        return None

    validated: list[dict[str, Any]] = []
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        metro = str(item.get("metro") or "").strip()
        slot = str(item.get("slot") or "").strip()
        sprints = item.get("recommended_sprints")
        if metro not in metro_keys:
            continue
        if not isinstance(sprints, int) or sprints < 1 or sprints > 12:
            continue
        if not slot:
            continue
        validated.append({"metro": metro, "slot": slot, "recommended_sprints": sprints})

    if not validated:
        return None

    advisory = str(parsed.get("advisory") or "Rebalance sprint allocation using the strongest time-slot signals.")
    return {
        "advisory": advisory,
        "suggestions": validated,
    }
