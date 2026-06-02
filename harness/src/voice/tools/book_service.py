"""Harness-owned Retell book_service tool.

The CallLock backend owns booking policy and calendar writes. Retell can request a
booking, but this tool validates service area and routes failures through the
deterministic fallback router before returning anything caller-facing.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from voice.fallback_router import FallbackContext, FallbackPolicy, route_call_fallback
from voice.models import CalcomConfig, VoiceConfig
from voice.services.calcom import CalcomError, create_booking

logger = logging.getLogger(__name__)

CreateBookingFn = Callable[..., Awaitable[dict[str, Any]]]


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

    booking_fn = create_booking_fn or create_booking
    try:
        booking = await booking_fn(
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            service_address=service_address,
            preferred_time=preferred_time,
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


def _first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value:
            return value
    return None


__all__ = ["book_service"]
