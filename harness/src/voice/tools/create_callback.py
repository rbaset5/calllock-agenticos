"""create_callback tool handler — sends callback SMS to owner via Twilio.

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
from voice.services.twilio_sms import SendResult, mask_phone, send_callback_sms

logger = logging.getLogger(__name__)

_GRACEFUL_ERROR = "We're experiencing technical difficulties. Please call back or leave a message."


def create_callback(
    *,
    caller_phone: str,
    reason: str,
    callback_minutes: int,
    voice_config: VoiceConfig | None,
    send_sms_fn: Callable[..., SendResult | None] | None = None,
) -> dict[str, Any]:
    """Handle create_callback_request tool call from Retell.

    Args:
        caller_phone: Caller's phone (E.164).
        reason: Caller's stated reason for needing a callback.
        callback_minutes: Promised callback time in minutes.
        voice_config: Tenant's voice config (None if resolution failed).
        send_sms_fn: Override SMS sender for testing.

    Returns:
        Dict with success and message keys. Always returns a response to Retell.
    """
    if voice_config is None:
        logger.error("create_callback.no_config", extra={"phone": mask_phone(caller_phone)})
        return {"success": False, "message": _GRACEFUL_ERROR}

    sms_fn = send_sms_fn or send_callback_sms

    try:
        result = sms_fn(
            config=voice_config,
            caller_phone=caller_phone,
            reason=reason,
            callback_minutes=callback_minutes,
        )

        if result and result.success:
            logger.info(
                "create_callback.sms_sent",
                extra={"phone": mask_phone(caller_phone), "sid": result.message_sid},
            )
        else:
            logger.warning(
                "create_callback.sms_failed",
                extra={"phone": mask_phone(caller_phone)},
            )
    except Exception:
        logger.error(
            "create_callback.sms_error",
            extra={"phone": mask_phone(caller_phone)},
            exc_info=True,
        )

    return {
        "success": True,
        "message": f"Callback request created. Someone will call back within {callback_minutes} minutes.",
    }


__all__ = ["create_callback"]
