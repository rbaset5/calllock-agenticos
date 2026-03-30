"""Generate a timezone-aware daily call plan from sprint schedule + live data.

Reads the 7-week sprint schedule YAML, queries due callbacks and ranked
fresh leads from Supabase, and produces a structured plan with sprint blocks
ordered by timezone (FL -> TX -> IL -> AZ).
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from . import store
from .constants import OUTBOUND_TENANT_ID

logger = logging.getLogger(__name__)

SCHEDULE_PATH = Path(__file__).resolve().parents[3] / "knowledge" / "outbound" / "sprint-schedule.yaml"

# Metro name to Supabase metro column value mapping.
METRO_FILTERS: dict[str, list[str]] = {
    "FL": ["Miami", "Tampa", "Orlando", "Jacksonville", "Fort Lauderdale"],
    "TX": ["Houston", "Dallas", "San Antonio", "Austin", "Fort Worth"],
    "IL": ["Chicago"],
    "AZ": ["Phoenix", "Mesa", "Tucson", "Scottsdale", "Chandler", "Gilbert", "Tempe", "Glendale", "Peoria"],
    "TX_IL": ["Houston", "Dallas", "San Antonio", "Austin", "Fort Worth", "Chicago"],
}


def load_schedule(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the sprint schedule YAML."""
    p = Path(path) if path else SCHEDULE_PATH
    if not p.exists():
        logger.warning("Sprint schedule not found at %s, using empty schedule", p)
        return {}
    with open(p) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "weeks" not in data:
        logger.error("Invalid sprint schedule format at %s", p)
        return {}
    return data


def current_week_number(schedule: dict[str, Any], today: date | None = None) -> int:
    """Compute the current week number (1-indexed) from schedule start_date."""
    today = today or date.today()
    start_str = schedule.get("start_date", "")
    if not start_str:
        return 1
    start = date.fromisoformat(start_str)
    if today < start:
        return 0  # before sprint starts
    delta_days = (today - start).days
    week = (delta_days // 7) + 1
    weeks = schedule.get("weeks", {})
    max_week = max(int(k) for k in weeks.keys()) if weeks else 7
    return min(week, max_week)


def _get_week_config(schedule: dict[str, Any], week_num: int) -> dict[str, Any] | None:
    """Get week config handling YAML int-key vs str-key ambiguity."""
    weeks = schedule.get("weeks", {})
    return weeks.get(week_num) or weeks.get(str(week_num))


def is_calling_day(schedule: dict[str, Any], week_num: int, today: date | None = None) -> bool:
    """Check if today is a calling day for the given week."""
    today = today or date.today()
    week_config = _get_week_config(schedule, week_num)
    if not week_config:
        return today.weekday() < 5  # default: weekdays only
    days = week_config.get("days", "weekdays")
    if days == "weekdays":
        return today.weekday() < 5
    if days == "weekdays_saturday":
        return today.weekday() < 6
    return today.weekday() < 5


def _metro_list_for_sprint(metro_key: str) -> list[str] | None:
    """Convert a sprint metro key to a list of metro names, or None for special types."""
    if metro_key in ("callbacks", "hot_leads", "warm_callbacks", "fresh"):
        return None  # special sprint types, not metro-filtered
    return METRO_FILTERS.get(metro_key, [metro_key])


def build_daily_plan(
    *,
    today: date | None = None,
    tenant_id: str = OUTBOUND_TENANT_ID,
    schedule_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build today's call plan: callbacks first, then fresh leads in sprint blocks.

    Returns a structured dict suitable for Discord posting and dialer UI display.
    """
    today = today or date.today()
    schedule = load_schedule(schedule_path)

    if not schedule:
        # Fallback: flat ranked list, no sprint structure
        fresh = store.list_ranked_call_ready_prospects(tenant_id=tenant_id, limit=50)
        return {
            "date": today.isoformat(),
            "week": 0,
            "fallback": True,
            "callbacks": [],
            "blocks": [],
            "fresh_leads": fresh,
            "total_callbacks": 0,
            "total_fresh": len(fresh),
        }

    week_num = current_week_number(schedule, today)

    if week_num == 0:
        return {
            "date": today.isoformat(),
            "week": 0,
            "message": f"Sprint starts {schedule.get('start_date', 'TBD')}. No calls today.",
            "callbacks": [],
            "blocks": [],
            "fresh_leads": [],
            "total_callbacks": 0,
            "total_fresh": 0,
        }

    if not is_calling_day(schedule, week_num, today):
        return {
            "date": today.isoformat(),
            "week": week_num,
            "message": "Rest day. No calls scheduled.",
            "callbacks": [],
            "blocks": [],
            "fresh_leads": [],
            "total_callbacks": 0,
            "total_fresh": 0,
        }

    # Fetch callbacks due today
    callbacks = store.list_due_callbacks(tenant_id=tenant_id, today=today.isoformat())

    # Fetch fresh leads grouped by metro/timezone
    all_fresh = store.list_ranked_call_ready_prospects(tenant_id=tenant_id, limit=200)

    # Build sprint blocks from schedule
    week_config = schedule.get("weeks", {}).get(str(week_num)) or schedule.get("weeks", {}).get(week_num, {})
    blocks_config = week_config.get("blocks", {})
    dials_per_sprint = schedule.get("dials_per_sprint", 10)
    sprint_min = schedule.get("sprint_duration_min", 20)
    recovery_min = schedule.get("recovery_min", 5)

    blocks = []
    fresh_assigned = set()  # track which prospect IDs have been assigned to sprints

    for block_name in ["AM", "MID", "EOD"]:
        block_cfg = blocks_config.get(block_name)
        if not block_cfg:
            continue

        start_et = block_cfg.get("start_et", "07:00")
        sprints = block_cfg.get("sprints", [])
        block_sprints = []

        for i, sprint_cfg in enumerate(sprints):
            metro_key = sprint_cfg.get("metro", "")
            note = sprint_cfg.get("note", "")

            # Calculate sprint start time
            offset_min = i * (sprint_min + recovery_min)
            h, m = map(int, start_et.split(":"))
            sprint_start = f"{h + (m + offset_min) // 60:02d}:{(m + offset_min) % 60:02d}"

            # Determine leads for this sprint
            sprint_leads: list[dict[str, Any]] = []
            metro_filter = _metro_list_for_sprint(metro_key)

            if metro_key in ("callbacks", "hot_leads", "warm_callbacks"):
                sprint_leads = [
                    cb for cb in callbacks
                    if cb.get("prospect_id") not in fresh_assigned
                ][:dials_per_sprint]
            elif metro_key == "fresh":
                sprint_leads = [
                    p for p in all_fresh
                    if p.get("id") not in fresh_assigned
                ][:dials_per_sprint]
            elif metro_filter:
                metro_lower = {m.lower() for m in metro_filter}
                sprint_leads = [
                    p for p in all_fresh
                    if (p.get("metro") or "").lower() in metro_lower and p.get("id") not in fresh_assigned
                ][:dials_per_sprint]

            for lead in sprint_leads:
                fresh_assigned.add(lead.get("id") or lead.get("prospect_id"))

            block_sprints.append({
                "sprint_number": len(blocks) * 10 + i + 1,
                "start_et": sprint_start,
                "duration_min": sprint_min,
                "metro": metro_key,
                "note": note,
                "lead_count": len(sprint_leads),
                "leads": sprint_leads[:dials_per_sprint],
            })

        blocks.append({
            "block": block_name,
            "start_et": start_et,
            "sprints": block_sprints,
        })

    return {
        "date": today.isoformat(),
        "week": week_num,
        "day_of_week": today.strftime("%A"),
        "callbacks": callbacks,
        "blocks": blocks,
        "total_callbacks": len(callbacks),
        "total_fresh": len(all_fresh),
        "total_sprints": sum(len(b["sprints"]) for b in blocks),
        "dials_per_sprint": dials_per_sprint,
        "sprint_duration_min": sprint_min,
        "recovery_min": recovery_min,
    }
