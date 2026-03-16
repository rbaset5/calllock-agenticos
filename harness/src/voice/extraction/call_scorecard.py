"""Call quality scorecard utilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

WEIGHTS = {
    "customer_name": 15,
    "customer_phone": 15,
    "service_address": 15,
    "problem_description": 15,
    "urgency": 10,
    "booking_or_callback": 20,
    "tags": 10,
}


def _get_value(state: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in state:
            return state[key]
    return None


def _is_callback_created(state: Mapping[str, Any]) -> bool:
    end_call_reason = (_get_value(state, "end_call_reason", "endCallReason") or "").lower()
    callback_type = _get_value(state, "callback_type", "callbackType")
    return end_call_reason == "callback_later" and bool(callback_type)


def build_call_scorecard(
    state: Mapping[str, Any], tags: Mapping[str, list[str]]
) -> dict[str, Any]:
    tag_count = sum(len(values) for values in tags.values())

    fields = {
        "has_customer_name": bool(_get_value(state, "customer_name", "customerName")),
        "has_customer_phone": bool(_get_value(state, "customer_phone", "customerPhone")),
        "has_service_address": bool(_get_value(state, "service_address", "serviceAddress")),
        "has_problem_description": bool(_get_value(state, "problem_description", "problemDescription")),
        "has_urgency": bool(_get_value(state, "urgency", "urgency_tier", "urgencyTier")),
        "has_booking_or_callback": bool(_get_value(state, "appointment_booked", "appointmentBooked"))
        or _is_callback_created(state),
        "tag_count": tag_count,
    }

    score = 0
    if fields["has_customer_name"]:
        score += WEIGHTS["customer_name"]
    if fields["has_customer_phone"]:
        score += WEIGHTS["customer_phone"]
    if fields["has_service_address"]:
        score += WEIGHTS["service_address"]
    if fields["has_problem_description"]:
        score += WEIGHTS["problem_description"]
    if fields["has_urgency"]:
        score += WEIGHTS["urgency"]
    if fields["has_booking_or_callback"]:
        score += WEIGHTS["booking_or_callback"]
    if tag_count > 0:
        score += WEIGHTS["tags"]

    warnings: list[str] = []
    if tag_count == 0:
        warnings.append("zero-tags")

    end_call_reason = (_get_value(state, "end_call_reason", "endCallReason") or "").lower()
    if (
        not _get_value(state, "appointment_booked", "appointmentBooked")
        and not _is_callback_created(state)
        and end_call_reason not in {"wrong_number", "out_of_area"}
    ):
        warnings.append("callback-gap")

    return {
        "call_id": _get_value(state, "call_id", "callId"),
        "score": score,
        "fields": fields,
        "warnings": warnings,
    }


__all__ = ["build_call_scorecard"]
