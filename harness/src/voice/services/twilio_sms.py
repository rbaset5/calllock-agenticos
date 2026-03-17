"""Twilio SMS service with template-based messages.

Three fixed SMS templates (spec finding #5 — no raw user input in body):
- CALLBACK: business callback request notification
- SALES_LEAD: high-ticket equipment lead alert
- EMERGENCY: urgent safety-related alert

On Twilio error: catch TwilioRestException, log, return None (never raise).
Phone numbers are masked in structured logs for PII protection.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient

from voice.models import VoiceConfig

logger = logging.getLogger(__name__)

_NON_PRINTABLE_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_MAX_REASON_LENGTH = 200


@dataclass(frozen=True)
class SendResult:
    success: bool
    message_sid: str


def mask_phone(phone: str | None) -> str:
    """Mask phone number for safe logging — show only last 4 digits."""
    if not phone:
        return "unknown"
    cleaned = re.sub(r"\D", "", phone)
    if len(cleaned) < 4:
        return "****"
    return f"***-***-{cleaned[-4:]}"


def sanitize_reason(reason: str | None) -> str:
    """Truncate to 200 chars and strip non-printable characters."""
    if not reason:
        return ""
    cleaned = _NON_PRINTABLE_RE.sub("", reason)
    return cleaned[:_MAX_REASON_LENGTH]


def _send_sms(
    config: VoiceConfig,
    to: str,
    body: str,
    twilio_client: Any | None = None,
) -> SendResult | None:
    """Send SMS via Twilio SDK. Returns None on error."""
    client = twilio_client or TwilioClient(config.twilio_account_sid, config.twilio_auth_token)

    try:
        message = client.messages.create(
            to=to,
            from_=config.twilio_from_number,
            body=body,
        )
        logger.info(
            "twilio_sms.sent",
            extra={"to": mask_phone(to), "message_sid": message.sid},
        )
        return SendResult(success=True, message_sid=message.sid)
    except TwilioRestException as exc:
        logger.error(
            "twilio_sms.error",
            extra={"to": mask_phone(to), "status": exc.status, "error_msg": exc.msg},
        )
        return None


def send_callback_sms(
    *,
    config: VoiceConfig,
    caller_phone: str,
    reason: str,
    callback_minutes: int,
    twilio_client: Any | None = None,
) -> SendResult | None:
    """Send callback request SMS to owner.

    Template:
      {business_name} callback request
      Caller: {phone}
      Reason: {reason}
      Callback within {minutes} min
    """
    safe_reason = sanitize_reason(reason)
    body = (
        f"{config.business_name} callback request\n"
        f"Caller: {caller_phone}\n"
        f"Reason: {safe_reason}\n"
        f"Callback within {callback_minutes} min"
    )

    logger.info(
        "twilio_sms.callback",
        extra={"caller": mask_phone(caller_phone), "minutes": callback_minutes},
    )
    return _send_sms(config, config.twilio_owner_phone, body, twilio_client)


def send_sales_lead_sms(
    *,
    config: VoiceConfig,
    equipment: str,
    customer_name: str,
    customer_phone: str,
    address: str,
    twilio_client: Any | None = None,
) -> SendResult | None:
    """Send sales lead SMS to owner.

    Template:
      SALES LEAD: {equipment}
      Customer: {name}
      Phone: {phone}
      Address: {address}
    """
    body = (
        f"SALES LEAD: {equipment}\n"
        f"Customer: {customer_name}\n"
        f"Phone: {customer_phone}\n"
        f"Address: {address}"
    )

    logger.info(
        "twilio_sms.sales_lead",
        extra={"phone": mask_phone(customer_phone), "equipment": equipment},
    )
    return _send_sms(config, config.twilio_owner_phone, body, twilio_client)


def send_emergency_sms(
    *,
    config: VoiceConfig,
    description: str,
    caller_phone: str,
    address: str,
    twilio_client: Any | None = None,
) -> SendResult | None:
    """Send emergency alert SMS to owner.

    Template:
      URGENT: {description}
      Caller: {phone}
      Address: {address}
    """
    body = (
        f"URGENT: {description}\n"
        f"Caller: {caller_phone}\n"
        f"Address: {address}"
    )

    logger.info(
        "twilio_sms.emergency",
        extra={"caller": mask_phone(caller_phone), "description": description},
    )
    return _send_sms(config, config.twilio_owner_phone, body, twilio_client)


__all__ = [
    "SendResult",
    "mask_phone",
    "sanitize_reason",
    "send_callback_sms",
    "send_emergency_sms",
    "send_sales_lead_sms",
]
