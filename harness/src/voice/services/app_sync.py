"""CallLock App webhook sync service.

Transforms extraction results into the DashboardJobPayload format
expected by the CallLock App, signs the payload with HMAC, and POSTs
it to the app webhook URL.

The field mapping is byte-compatible with V2's dashboard.ts
transformToDashboardPayload function.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from voice.models import VoiceConfig

logger = logging.getLogger(__name__)

_REVENUE_MIDPOINTS: dict[str, int] = {
    "replacement": 10000,
    "major_repair": 1900,
    "standard_repair": 500,
    "minor": 150,
    "diagnostic": 99,
}


def transform_to_app_payload(
    *,
    extraction: dict[str, Any],
    raw_payload: dict[str, Any],
    call_id: str,
    user_email: str,
    booking_id: str | None = None,
) -> dict[str, Any]:
    """Transform extraction results into a DashboardJobPayload dict.

    This mapping mirrors V2 dashboard.ts transformToDashboardPayload
    so the CallLock App receives an identical payload format.
    """
    revenue_estimate = extraction.get("revenue_estimate") or {}
    revenue_tier = extraction.get("revenue_tier", "diagnostic")

    end_call_reason = extraction.get("end_call_reason", "agent_hangup")
    callback_scheduled = end_call_reason == "callback_scheduled"

    # Booking status tri-state (V11)
    if booking_id:
        booking_status = "confirmed"
    elif callback_scheduled:
        booking_status = "attempted_failed"
    else:
        booking_status = "not_requested"

    # Phone fallback: extraction > raw_payload from_number
    phone = extraction.get("customer_phone") or raw_payload.get("from_number") or "Unknown"

    # Extracted fields from pipeline (problem_duration etc.)
    extracted_fields = extraction.get("extracted_fields") or {}
    problem_duration_info = extracted_fields.get("problem_duration") or {}

    return {
        "customer_name": extraction.get("customer_name") or "Unknown Caller",
        "customer_phone": phone,
        "customer_address": extraction.get("service_address") or "",
        "service_type": "hvac",
        "urgency": extraction.get("dashboard_urgency", "medium"),
        "ai_summary": raw_payload.get("call_summary"),
        "scheduled_at": None,
        "call_transcript": raw_payload.get("transcript"),
        "user_email": user_email,
        "revenue_tier": revenue_tier,
        "revenue_tier_label": revenue_estimate.get("tierLabel"),
        "revenue_tier_description": revenue_estimate.get("tierDescription"),
        "revenue_tier_range": revenue_estimate.get("estimatedRange"),
        "revenue_tier_signals": revenue_estimate.get("signals"),
        "revenue_confidence": revenue_estimate.get("confidence"),
        "potential_replacement": revenue_estimate.get("potentialReplacement", False),
        "estimated_value": _REVENUE_MIDPOINTS.get(revenue_tier, 300),
        "end_call_reason": end_call_reason,
        "issue_description": extraction.get("problem_description"),
        "equipment_type": extraction.get("equipment_type"),
        "equipment_age": extraction.get("equipment_age"),
        "sales_lead_notes": extraction.get("sales_lead_notes"),
        "problem_duration": problem_duration_info.get("duration") if isinstance(problem_duration_info, dict) else None,
        "problem_duration_category": problem_duration_info.get("category") if isinstance(problem_duration_info, dict) else None,
        "problem_onset": problem_duration_info.get("onset") if isinstance(problem_duration_info, dict) else None,
        "problem_pattern": problem_duration_info.get("pattern") if isinstance(problem_duration_info, dict) else None,
        "customer_attempted_fixes": problem_duration_info.get("attempted_fixes") if isinstance(problem_duration_info, dict) else None,
        "call_id": call_id,
        "priority_color": extraction.get("priority_color"),
        "priority_reason": extraction.get("priority_reason"),
        "property_type": extraction.get("property_type"),
        "system_status": extraction.get("system_status"),
        "equipment_age_bracket": extraction.get("equipment_age_bracket"),
        "is_decision_maker": extraction.get("is_decision_maker"),
        "decision_maker_contact": extraction.get("decision_maker_contact"),
        "tags": extraction.get("tag_categories") or {},
        "site_contact_name": extraction.get("site_contact_name"),
        "site_contact_phone": extraction.get("site_contact_phone"),
        "is_third_party": extraction.get("is_third_party"),
        "third_party_type": extraction.get("third_party_type"),
        "call_type": extraction.get("call_type"),
        "call_subtype": extraction.get("call_subtype"),
        "call_type_confidence": extraction.get("call_type_confidence"),
        "is_commercial": extraction.get("is_commercial"),
        "sentiment_score": extraction.get("sentiment_score"),
        "work_type": extraction.get("work_type"),
        "caller_type": extraction.get("caller_type", "unknown"),
        "primary_intent": extraction.get("primary_intent", "unknown"),
        "card_headline": extraction.get("card_headline"),
        "card_summary": extraction.get("card_summary"),
        "booking_status": booking_status,
        "slot_changed": extraction.get("slot_changed"),
        "urgency_mismatch": extraction.get("urgency_mismatch"),
        "booking_requested_time": extraction.get("booking_requested_time"),
        "booking_booked_slot": extraction.get("booking_booked_slot"),
        "booking_urgency_transition": extraction.get("booking_urgency_transition"),
    }


def sign_webhook_payload(payload: dict[str, Any], secret: str) -> str:
    """Sign a webhook payload with HMAC-SHA256.

    Uses compact JSON serialization (no spaces, sorted keys) for deterministic signing.
    """
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def send_to_app(
    *,
    payload: dict[str, Any],
    config: VoiceConfig,
) -> bool:
    """POST the dashboard payload to the CallLock App webhook.

    Returns True on success (2xx). Raises on 5xx for Inngest retry.
    """
    signature = sign_webhook_payload(payload, config.app_webhook_secret)

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            config.app_webhook_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": config.app_webhook_secret,
                "X-Webhook-Signature": signature,
            },
        )

    if response.status_code >= 500:
        logger.error(
            "app_sync.5xx",
            extra={"status": response.status_code, "url": config.app_webhook_url},
        )
        response.raise_for_status()

    if response.status_code >= 400:
        logger.warning(
            "app_sync.4xx",
            extra={"status": response.status_code, "url": config.app_webhook_url},
        )
        return False

    logger.info("app_sync.success", extra={"url": config.app_webhook_url})
    return True


__all__ = [
    "send_to_app",
    "sign_webhook_payload",
    "transform_to_app_payload",
]
