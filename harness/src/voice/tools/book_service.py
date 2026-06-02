"""Harness-owned Retell book_service tool.

The CallLock backend owns booking policy and calendar writes. Retell can request a
booking, but this tool validates service area and routes failures through the
deterministic fallback router before returning anything caller-facing.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from voice.fallback_router import FallbackContext, FallbackPolicy, route_call_fallback
from voice.models import CalcomConfig, VoiceConfig
from voice.services.calcom import CalcomError, create_booking, list_available_slots

logger = logging.getLogger(__name__)

CreateBookingFn = Callable[..., Awaitable[dict[str, Any]]]
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


async def book_service(
    *,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    service_address: str,
    preferred_time: str,
    issue_description: str,
    urgency_tier: str,
    voice_config: VoiceConfig | None,
    calcom_config: CalcomConfig | None,
    zip_code: str = "",
    fallback_policy: FallbackPolicy | None = None,
    create_booking_fn: CreateBookingFn | None = None,
    list_available_slots_fn: ListAvailableSlotsFn | None = None,
    now_fn: NowFn | None = None,
) -> dict[str, Any]:
    """Validate and create a service booking.

    Returns a Retell-safe response. It never throws to the caller path because
    dead air is worse than a deterministic fallback.
    """

    policy = fallback_policy or FallbackPolicy(callback_tasks_enabled=True)
    if voice_config is None or calcom_config is None:
        return _failed_booking("configuration_missing", urgency_tier, policy)

    if not _location_in_service_area(service_address, zip_code, voice_config.service_area_zips):
        return _failed_booking("service_area_blocked", urgency_tier, policy)

    if not _is_valid_email(customer_email):
        return _failed_booking("customer_email_missing", urgency_tier, policy)

    resolved_time = preferred_time.strip()
    if not _is_exact_datetime(resolved_time):
        slots_fn = list_available_slots_fn or list_available_slots
        try:
            resolution = await _resolve_preferred_slot(
                preferred_time=resolved_time,
                config=calcom_config,
                list_available_slots_fn=slots_fn,
                now_fn=now_fn,
            )
        except (CalcomError, Exception):
            logger.warning("book_service.slot_lookup_failed", exc_info=True)
            return _failed_booking("booking_failed", urgency_tier, policy)

        if resolution.selected_start is None:
            return _slot_unavailable("no_matching_slot", resolution.available_starts)
        resolved_time = resolution.selected_start

    booking_fn = create_booking_fn or create_booking
    try:
        booking = await booking_fn(
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            service_address=service_address,
            preferred_time=resolved_time,
            issue_description=issue_description,
            urgency_tier=urgency_tier,
            config=calcom_config,
        )
    except (CalcomError, Exception):
        logger.warning("book_service.booking_failed", exc_info=True)
        return _failed_booking("booking_failed", urgency_tier, policy)

    booking_id = _first_present(booking, "booking_id", "bookingId", "uid", "id")
    appointment_time = _first_present(booking, "appointment_time", "appointmentTime", "start", "startTime")
    return {
        "success": True,
        "booking_confirmed": True,
        "booked": True,
        "booking_id": booking_id,
        "appointment_time": appointment_time,
        "message": "Appointment booked successfully.",
    }


async def _resolve_preferred_slot(
    *,
    preferred_time: str,
    config: CalcomConfig,
    list_available_slots_fn: ListAvailableSlotsFn,
    now_fn: NowFn | None,
) -> SlotResolution:
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


def _slot_unavailable(reason: str, available_slots: list[str]) -> dict[str, Any]:
    if available_slots:
        message = "That requested window is not open. I found other available slots."
    else:
        message = "I am not seeing any openings right now."
    return {
        "success": False,
        "booking_confirmed": False,
        "booked": False,
        "reason": reason,
        "available_slots": available_slots,
        "message": message,
    }


def _failed_booking(
    reason: str,
    urgency_tier: str,
    policy: FallbackPolicy,
) -> dict[str, Any]:
    decision = route_call_fallback(
        FallbackContext(
            urgency_tier=urgency_tier,
            route="legitimate",
            business_open=False,
            caller_requested_human=False,
            booking_failed=True,
            confidence=1.0,
        ),
        policy,
    )
    return {
        "success": False,
        "booking_confirmed": False,
        "booked": False,
        "reason": reason,
        "fallback_action": decision.action,
        "fallback_reason": decision.reason,
        "fallback_target": decision.target_number,
        "message": _message_for_fallback(decision.action),
    }


def _message_for_fallback(action: str) -> str:
    if action == "callback_task":
        return "I could not finalize that appointment. I will have the team call back to finish scheduling."
    if action == "voicemail":
        return "I could not finalize that appointment. I can route you to voicemail."
    if action == "transfer":
        return "I could not finalize that appointment. I can transfer you to the team."
    return "I could not finalize that appointment."


def _location_in_service_area(address: str, zip_code: str, allowed_zips: list[str]) -> bool:
    explicit_zip = _extract_zip(zip_code)
    address_zip = _extract_zip(address)
    candidate_zip = explicit_zip or address_zip
    return bool(candidate_zip and candidate_zip in set(allowed_zips))


def _extract_zip(value: str) -> str | None:
    match = re.search(r"\b(\d{5})\b", value or "")
    if not match:
        return None
    return match.group(1)


def _is_valid_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip()))


def _is_exact_datetime(value: str) -> bool:
    if not re.match(r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}", value.strip()):
        return False
    return _parse_datetime(value) is not None


def _timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        logger.warning("book_service.invalid_timezone", extra={"timezone": value})
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


def _first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value:
            return value
    return None


__all__ = ["book_service"]
