from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


def require_touchpoint_id(touchpoint_id: str) -> str:
    if not touchpoint_id:
        raise ValueError("touchpoint_id is required")
    return touchpoint_id


def monday_snapshot_week(now: datetime | None = None) -> date:
    current = now or datetime.now(timezone.utc)
    current = current.astimezone(timezone.utc)
    return (current - timedelta(days=current.weekday())).date()
