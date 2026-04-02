from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from . import store
from .constants import OUTBOUND_TENANT_ID
from .daily_plan import current_week_number, get_daily_sprint_count, get_week_config, is_calling_day, load_schedule


ET = ZoneInfo("America/Detroit")


def _coerce_et(value: datetime | None) -> datetime:
    now = value or datetime.now(ET)
    if now.tzinfo is None:
        return now.replace(tzinfo=ET)
    return now.astimezone(ET)


def _block_start(day: date, start_et: str) -> datetime:
    hour, minute = [int(part) for part in start_et.split(":", 1)]
    return datetime.combine(day, time(hour, minute), ET)


def _schedule_blocks(schedule: dict[str, Any], week_num: int, day: date) -> list[dict[str, Any]]:
    week_config = get_week_config(schedule, week_num) or {}
    blocks_config = week_config.get("blocks", {})
    sprint_duration = int(schedule.get("sprint_duration_min", 20) or 20)
    recovery = int(schedule.get("recovery_min", 5) or 5)

    blocks: list[dict[str, Any]] = []
    global_index = 0
    for block_name in ("AM", "MID", "EOD"):
        block_cfg = blocks_config.get(block_name)
        if not isinstance(block_cfg, dict):
            continue

        start_et = str(block_cfg.get("start_et", "07:20"))
        sprints_config = block_cfg.get("sprints", [])
        block_start_at = _block_start(day, start_et)
        segments: list[str] = []
        sprints: list[dict[str, Any]] = []

        for offset, sprint_cfg in enumerate(sprints_config):
            metro = str((sprint_cfg or {}).get("metro", ""))
            note = str((sprint_cfg or {}).get("note", ""))
            sprint_start = block_start_at + timedelta(minutes=offset * (sprint_duration + recovery))
            sprint_end = sprint_start + timedelta(minutes=sprint_duration)
            window_end = sprint_end + timedelta(minutes=recovery)
            global_index += 1
            segments.append(metro)
            sprints.append(
                {
                    "block": block_name,
                    "sprint_index": global_index,
                    "block_sprint_index": offset + 1,
                    "metro": metro,
                    "note": note,
                    "start_at": sprint_start,
                    "end_at": sprint_end,
                    "window_end": window_end,
                }
            )

        blocks.append(
            {
                "block": block_name,
                "start_et": start_et,
                "segments": segments,
                "sprints": sprints,
            }
        )

    return blocks


def _inactive_state(schedule: dict[str, Any], day: date, week_num: int, message: str) -> dict[str, Any]:
    week_config = get_week_config(schedule, week_num) or {}
    dials_per_sprint = int(week_config.get("dials_per_sprint", schedule.get("dials_per_sprint", 10)) or 10)
    sprints_target = get_daily_sprint_count(schedule, week_num, day) if week_num > 0 else 0
    return {
        "date": day.isoformat(),
        "week": week_num,
        "phase": week_config.get("phase"),
        "block_active": False,
        "message": message,
        "sprints_target_today": sprints_target,
        "dials_target_today": sprints_target * dials_per_sprint,
        "all_blocks": [],
    }


def get_current_state(at: datetime | None = None) -> dict[str, Any]:
    now = _coerce_et(at)
    today = now.date()
    schedule = load_schedule()
    if not schedule:
        return {"date": today.isoformat(), "week": 0, "block_active": False, "message": "Sprint schedule unavailable", "all_blocks": []}

    start_date = date.fromisoformat(str(schedule.get("start_date", today.isoformat())))
    deadline = date.fromisoformat(str(schedule.get("deadline", today.isoformat())))
    if today < start_date:
        return _inactive_state(schedule, today, 0, f"Sprint starts {start_date.strftime('%b %d')}")
    if today > deadline:
        return _inactive_state(schedule, today, current_week_number(schedule, today), "Sprint complete")

    week_num = current_week_number(schedule, today)
    if not is_calling_day(schedule, week_num, today):
        return _inactive_state(schedule, today, week_num, "Rest day")

    week_config = get_week_config(schedule, week_num) or {}
    dials_per_sprint = int(week_config.get("dials_per_sprint", schedule.get("dials_per_sprint", 10)) or 10)
    sprints_target = get_daily_sprint_count(schedule, week_num, today)
    try:
        raw_scoreboard = store.sprint_scoreboard(
            tenant_id=OUTBOUND_TENANT_ID,
            start_date=start_date.isoformat(),
            today=today.isoformat(),
        )
    except Exception:
        raw_scoreboard = {}
    blocks = _schedule_blocks(schedule, week_num, today)
    all_blocks = [{"block": block["block"], "start_et": block["start_et"], "sprints": len(block["sprints"]), "segments": block["segments"]} for block in blocks]
    all_sprints = [sprint for block in blocks for sprint in block["sprints"]]

    base_state = {
        "date": today.isoformat(),
        "week": week_num,
        "phase": week_config.get("phase"),
        "instruction": week_config.get("coaching_note", ""),
        "schedule_start": str(schedule.get("start_date", "")),
        "sprints_target_today": sprints_target,
        "dials_completed_today": int(raw_scoreboard.get("daily_dials", 0) or 0),
        "dials_target_today": sprints_target * dials_per_sprint,
        "all_blocks": all_blocks,
    }

    for block in blocks:
        sprints = block["sprints"]
        if not sprints:
            continue
        block_start_at = sprints[0]["start_at"]
        block_end_at = sprints[-1]["window_end"]
        if block_start_at <= now < block_end_at:
            current_sprint = next((sprint for sprint in sprints if sprint["start_at"] <= now < sprint["window_end"]), sprints[-1])
            completed = sum(1 for sprint in all_sprints if sprint["end_at"] <= now)
            next_sprint = next((sprint for sprint in all_sprints if sprint["start_at"] > now), None)
            minutes_until_next = None
            if next_sprint is not None:
                minutes_until_next = max(int((next_sprint["start_at"] - now).total_seconds() // 60), 0)
            return {
                **base_state,
                "block_active": True,
                "current_block": block["block"],
                "active_segment": current_sprint["metro"],
                "sprint_index": current_sprint["sprint_index"],
                "sprints_completed_today": completed,
                "next_segment_at": next_sprint["start_at"].isoformat() if next_sprint else None,
                "next_segment_name": next_sprint["metro"] if next_sprint else None,
                "minutes_until_next": minutes_until_next,
            }

    next_block = next((block for block in blocks if block["sprints"] and block["sprints"][0]["start_at"] > now), None)
    if next_block is not None:
        return {
            **base_state,
            "block_active": False,
            "next_block": next_block["block"],
            "next_block_at": next_block["sprints"][0]["start_at"].isoformat(),
        }

    return {
        **base_state,
        "block_active": False,
        "message": "Sprint complete",
    }
