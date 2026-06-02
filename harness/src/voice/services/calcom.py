"""Cal.com API client for booking create, lookup, cancel, and reschedule.

Credentials come from CalcomConfig (per-tenant, resolved via config.py).
On timeout/error: raises CalcomError (propagates as 503 to booking API caller).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from voice.models import CalcomConfig

logger = logging.getLogger(__name__)

_CAL_API_BASE = "https://api.cal.com/v2"
_TIMEOUT = 10.0


class CalcomError(Exception):
    """Cal.com API call failed."""


def _headers(config: CalcomConfig) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.calcom_api_key}",
        "cal-api-version": "2024-08-13",
        "Content-Type": "application/json",
    }


async def lookup_by_phone(phone: str, config: CalcomConfig) -> list[dict[str, Any]]:
    """Look up upcoming bookings by phone number."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(
                f"{_CAL_API_BASE}/bookings",
                params={"status": "upcoming"},
                headers=_headers(config),
            )

        if response.status_code >= 400:
            raise CalcomError(f"Cal.com lookup failed: HTTP {response.status_code}")

        data = response.json()
        bookings = data.get("data", [])

        normalized = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        matched = []
        for booking in bookings:
            attendees = booking.get("attendees", [])
            for attendee in attendees:
                attendee_phone = (attendee.get("phoneNumber") or "").replace(" ", "").replace("-", "")
                if attendee_phone and attendee_phone == normalized:
                    matched.append(booking)
                    break

        return matched

    except CalcomError:
        raise
    except httpx.TimeoutException as exc:
        raise CalcomError(f"Cal.com lookup timed out: {exc}") from exc
    except Exception as exc:
        raise CalcomError(f"Cal.com lookup failed: {exc}") from exc


async def create_booking(
    *,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    service_address: str,
    preferred_time: str,
    issue_description: str,
    urgency_tier: str,
    config: CalcomConfig,
) -> dict[str, Any]:
    """Create a Cal.com booking for a Retell call."""
    payload = {
        "eventTypeId": config.calcom_event_type_id,
        "start": preferred_time,
        "attendee": {
            "name": customer_name,
            "email": customer_email,
            "phoneNumber": customer_phone,
            "timeZone": config.calcom_timezone,
        },
        "metadata": {
            "service_address": service_address,
            "issue_description": issue_description,
            "urgency_tier": urgency_tier,
            "source": "calllock_voice",
        },
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{_CAL_API_BASE}/bookings",
                json=payload,
                headers=_headers(config),
            )

        if response.status_code >= 400:
            raise CalcomError(f"Cal.com booking failed: HTTP {response.status_code}")

        data = response.json()
        if isinstance(data.get("data"), dict):
            return data["data"]
        return data

    except CalcomError:
        raise
    except httpx.TimeoutException as exc:
        raise CalcomError(f"Cal.com booking timed out: {exc}") from exc
    except Exception as exc:
        raise CalcomError(f"Cal.com booking failed: {exc}") from exc


async def cancel_booking(booking_uid: str, reason: str, config: CalcomConfig) -> bool:
    """Cancel a booking by UID."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{_CAL_API_BASE}/bookings/{booking_uid}/cancel",
                json={"cancellationReason": reason},
                headers=_headers(config),
            )

        if response.status_code >= 400:
            raise CalcomError(f"Cal.com cancel failed: HTTP {response.status_code}")

        return True

    except CalcomError:
        raise
    except httpx.TimeoutException as exc:
        raise CalcomError(f"Cal.com cancel timed out: {exc}") from exc
    except Exception as exc:
        raise CalcomError(f"Cal.com cancel failed: {exc}") from exc


async def reschedule_booking(
    booking_uid: str,
    new_time: str,
    config: CalcomConfig,
) -> bool:
    """Reschedule a booking to a new time (ISO 8601)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{_CAL_API_BASE}/bookings/{booking_uid}/reschedule",
                json={"start": new_time},
                headers=_headers(config),
            )

        if response.status_code >= 400:
            raise CalcomError(f"Cal.com reschedule failed: HTTP {response.status_code}")

        return True

    except CalcomError:
        raise
    except httpx.TimeoutException as exc:
        raise CalcomError(f"Cal.com reschedule timed out: {exc}") from exc
    except Exception as exc:
        raise CalcomError(f"Cal.com reschedule failed: {exc}") from exc


__all__ = [
    "CalcomError",
    "cancel_booking",
    "create_booking",
    "lookup_by_phone",
    "reschedule_booking",
]
