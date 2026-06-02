"""Calendar slot selection for harness-owned voice bookings."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from voice.models import CalcomConfig

logger = logging.getLogger(__name__)

ListAvailableSlotsFn = Callable[..., Awaitable[list[dict[str, Any]]]]
NowFn = Callable[[], datetime]

_DEFAULT_OPEN_HOUR = 9
_DEFAULT_CLOSE_HOUR = 17
_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


@dataclass(frozen=True)
class SlotResolution:
    selected_start: str | None
    available_starts: list[str]


async def resolve_preferred_slot(
    *,
    preferred_time: str,
    config: CalcomConfig,
    list_available_slots_fn: ListAvailableSlotsFn,
    now_fn: NowFn | None,
) -> SlotResolution:
    """Resolve a caller's natural time preference to a concrete Cal.com slot."""
    zone = _timezone(config.calcom_timezone)
    now = _localized_now(zone, now_fn)
    window_start, window_end = _query_window(preferred_time, now)
    slots = await list_available_slots_fn(
        config=config,
        start=window_start.isoformat(),
        end=window_end.isoformat(),
        time_zone=config.calcom_timezone,
    )
    available = _available_business_slots(slots, zone, now)
    matching = [slot for slot in available if _matches_preference(slot[0], preferred_time)]
    if matching:
        return SlotResolution(selected_start=matching[0][1], available_starts=[slot[1] for slot in available[:3]])
    return SlotResolution(selected_start=None, available_starts=[slot[1] for slot in available[:3]])


def is_exact_datetime(value: str) -> bool:
    """Return true for ISO-like values Cal.com can receive as exact starts."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}", value.strip()):
        return False
    return _parse_datetime(value) is not None


def _timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        logger.warning("slot_selection.invalid_timezone", extra={"timezone": value})
        return ZoneInfo("UTC")


def _localized_now(zone: ZoneInfo, now_fn: NowFn | None) -> datetime:
    now = now_fn() if now_fn else datetime.now(zone)
    if now.tzinfo is None:
        return now.replace(tzinfo=zone)
    return now.astimezone(zone)


def _query_window(preferred_time: str, now: datetime) -> tuple[datetime, datetime]:
    text = preferred_time.lower()
    target_date = _target_date(text, now)
    if target_date is not None:
        start = datetime.combine(target_date, datetime.min.time(), tzinfo=now.tzinfo)
        if target_date == now.date():
            start = max(start, now)
        end = datetime.combine(target_date + timedelta(days=1), datetime.min.time(), tzinfo=now.tzinfo)
        return start, end

    return now, now + timedelta(days=7)


def _target_date(text: str, now: datetime) -> date | None:
    if "today" in text:
        return now.date()
    if "tomorrow" in text:
        return (now + timedelta(days=1)).date()

    for name, weekday in _WEEKDAYS.items():
        if name in text:
            days_ahead = (weekday - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (now + timedelta(days=days_ahead)).date()

    return None


def _available_business_slots(
    slots: list[dict[str, Any]],
    zone: ZoneInfo,
    now: datetime,
) -> list[tuple[datetime, str]]:
    parsed: list[tuple[datetime, str]] = []
    for slot in slots:
        start = slot.get("start")
        if not isinstance(start, str):
            continue

        parsed_start = _parse_datetime(start)
        if parsed_start is None:
            continue

        local_start = parsed_start.astimezone(zone) if parsed_start.tzinfo else parsed_start.replace(tzinfo=zone)
        if local_start < now:
            continue
        if not (_DEFAULT_OPEN_HOUR <= local_start.hour < _DEFAULT_CLOSE_HOUR):
            continue
        parsed.append((local_start, start))

    return sorted(parsed, key=lambda item: item[0])


def _matches_preference(slot_start: datetime, preferred_time: str) -> bool:
    text = preferred_time.lower().strip()
    requested_time = _requested_clock_time(text)
    if requested_time is not None:
        hour, minute = requested_time
        return slot_start.hour == hour and slot_start.minute == minute

    if "morning" in text:
        return _DEFAULT_OPEN_HOUR <= slot_start.hour < 12
    if "afternoon" in text:
        return 12 <= slot_start.hour < _DEFAULT_CLOSE_HOUR
    if any(term in text for term in ("evening", "night", "after 5", "after five")):
        return False
    return True


def _requested_clock_time(text: str) -> tuple[int, int] | None:
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text)
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    meridiem = match.group(3)
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return hour, minute


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


__all__ = [
    "ListAvailableSlotsFn",
    "NowFn",
    "is_exact_datetime",
    "resolve_preferred_slot",
]
