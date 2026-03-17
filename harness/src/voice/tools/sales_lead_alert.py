"""send_sales_lead_alert tool handler — sends sales lead SMS to owner.

Rules (from spec):
- Returns success to Retell even on Twilio failure (caller hears normal ending)
- Logs Twilio failures for Inngest retry post-call
- VoiceConfig missing -> returns graceful error message to Retell
- NEVER hangs or throws — Retell has 8s timeout
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from voice.models import VoiceConfig
from voice.services.twilio_sms import SendResult, mask_phone, send_sales_lead_sms

logger = logging.getLogger(__name__)

_GRACEFUL_ERROR = "We're experiencing technical difficulties. Please call back or leave a message."


def send_sales_lead_alert(
    *,
    equipment: str,
    customer_name: str,
    customer_phone: str,
    address: str,
    voice_config: VoiceConfig | None,
    send_sms_fn: Callable[..., SendResult | None] | None = None,
) -> dict[str, Any]:
    """Handle send_sales_lead_alert tool call from Retell.

    Args:
        equipment: Equipment type (e.g., "Central AC").
        customer_name: Customer's name.
        customer_phone: Customer's phone (E.164).
        address: Customer's service address.
        voice_config: Tenant's voice config (None if resolution failed).
        send_sms_fn: Override SMS sender for testing.

    Returns:
        Dict with success and message keys. Always returns a response to Retell.
    """
    if voice_config is None:
        logger.error("sales_lead_alert.no_config", extra={"phone": mask_phone(customer_phone)})
        return {"success": False, "message": _GRACEFUL_ERROR}

    sms_fn = send_sms_fn or send_sales_lead_sms

    try:
        result = sms_fn(
            config=voice_config,
            equipment=equipment,
            customer_name=customer_name,
            customer_phone=customer_phone,
            address=address,
        )

        if result and result.success:
            logger.info(
                "sales_lead_alert.sms_sent",
                extra={"phone": mask_phone(customer_phone), "sid": result.message_sid},
            )
        else:
            logger.warning(
                "sales_lead_alert.sms_failed",
                extra={"phone": mask_phone(customer_phone)},
            )
    except Exception:
        logger.error(
            "sales_lead_alert.sms_error",
            extra={"phone": mask_phone(customer_phone)},
            exc_info=True,
        )

    return {
        "success": True,
        "message": "Sales lead alert sent to the team.",
    }


__all__ = ["send_sales_lead_alert"]
