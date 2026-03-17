"""Caller classification and traffic routing helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _get_value(state: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in state:
            return state[key]
    return None


def derive_caller_type(state: Mapping[str, Any], tags: Mapping[str, list[str]] | None) -> str:
    property_type = (_get_value(state, "property_type", "propertyType") or "").lower()
    if property_type == "commercial":
        return "commercial"

    if tags:
        if "COMMERCIAL_ACCT" in tags.get("CUSTOMER", []):
            return "commercial"
        if "JOB_APPLICANT" in tags.get("NON_CUSTOMER", []):
            return "job_applicant"
        if "SPAM_TELEMARKETING" in tags.get("NON_CUSTOMER", []):
            return "spam"
        if "VENDOR_SALES" in tags.get("NON_CUSTOMER", []):
            return "vendor"
        if tags.get("CUSTOMER") or tags.get("SERVICE_TYPE"):
            return "residential"

    if _get_value(state, "problem_description", "problemDescription"):
        return "residential"
    return "unknown"


def derive_primary_intent(state: Mapping[str, Any], tags: Mapping[str, list[str]] | None) -> str:
    if _get_value(state, "appointment_booked", "appointmentBooked"):
        return "booking_request"
    if tags and tags.get("RECOVERY"):
        return "active_job_issue"
    if tags and tags.get("NON_CUSTOMER"):
        return "solicitation"

    callback_type = (_get_value(state, "callback_type", "callbackType") or "").lower()
    if callback_type in {"billing", "warranty"}:
        return "admin_billing"

    end_call_reason = (_get_value(state, "end_call_reason", "endCallReason") or "").lower()
    if end_call_reason == "sales_lead":
        return "new_lead"
    if _get_value(state, "problem_description", "problemDescription"):
        return "service"
    return "unknown"


def route_call(caller_type: str | None, primary_intent: str | None) -> str:
    caller_type = (caller_type or "unknown").lower()
    primary_intent = (primary_intent or "unknown").lower()

    if caller_type == "spam":
        return "spam"
    if caller_type in {"vendor", "job_applicant"} or primary_intent == "solicitation":
        return "vendor"
    return "legitimate"


__all__ = ["derive_caller_type", "derive_primary_intent", "route_call"]
