"""Reply watcher: detects inbound iMessages from prospects via imsg watch.

Runs as a background daemon thread (same pattern as Discord bot in assistant.py).
Matches inbound phone numbers to prospect records, logs to prospect_messages,
detects opt-out keywords, and posts Discord alerts via webhook.

Singleton: only one watcher thread runs per process.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from typing import Any

from . import store
from .constants import OUTBOUND_TENANT_ID
from .imsg_client import watch_replies

logger = logging.getLogger(__name__)

_watcher_lock = threading.Lock()
_watcher_running = False

OPT_OUT_PATTERNS = [
    re.compile(r"\bstop\b", re.IGNORECASE),
    re.compile(r"\bunsubscribe\b", re.IGNORECASE),
    re.compile(r"\bdon'?t text\b", re.IGNORECASE),
    re.compile(r"\bremove me\b", re.IGNORECASE),
    re.compile(r"\bopt out\b", re.IGNORECASE),
]


def _is_opt_out(text: str) -> bool:
    return any(pattern.search(text) for pattern in OPT_OUT_PATTERNS)


def _normalize_phone(raw: str) -> str:
    """Strip non-digit characters and ensure +1 prefix for US numbers."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        digits = "1" + digits
    if not digits.startswith("+"):
        digits = "+" + digits
    return digits


def _find_prospect_by_phone(phone: str) -> dict[str, Any] | None:
    """Look up a prospect by normalized phone number."""
    normalized = _normalize_phone(phone)
    prospects = store.list_outbound_prospects(tenant_id=OUTBOUND_TENANT_ID)
    for prospect in prospects:
        p_phone = prospect.get("phone_normalized") or prospect.get("phone", "")
        if _normalize_phone(p_phone) == normalized:
            return prospect
    return None


def _post_discord_alert(message: str) -> None:
    """Post an alert to the outbound Discord channel via webhook."""
    webhook_url = os.getenv("DISCORD_OUTBOUND_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("reply_watcher.no_webhook_url")
        return

    try:
        import httpx
        httpx.post(
            webhook_url,
            json={"content": message},
            timeout=10.0,
        )
    except Exception:
        logger.exception("reply_watcher.discord_alert_failed")


def _on_inbound_message(msg: dict[str, Any]) -> None:
    """Handle a single inbound iMessage from imsg watch."""
    sender = msg.get("sender", "")
    text = msg.get("text", "")

    if not sender or not text:
        return

    prospect = _find_prospect_by_phone(sender)

    if prospect is None:
        logger.debug("reply_watcher.unknown_phone", extra={"sender": sender})
        return

    prospect_id = str(prospect.get("id") or prospect.get("prospect_id") or "")
    business_name = prospect.get("business_name", "Unknown")
    phone = prospect.get("phone_normalized") or prospect.get("phone", sender)

    # Log inbound message
    store.insert_prospect_message({
        "tenant_id": OUTBOUND_TENANT_ID,
        "prospect_id": prospect_id,
        "direction": "inbound",
        "content": text,
        "status": "received",
        "phone_normalized": _normalize_phone(phone),
    })

    # Check for opt-out
    if _is_opt_out(text):
        store.update_outbound_prospect(prospect_id, {"do_not_message": True})
        _post_discord_alert(
            f"**Opt-out received** from {business_name}\n"
            f"> {text}\n"
            f"`do_not_message` set to true. No more texts will be sent."
        )
        logger.info(
            "reply_watcher.opt_out",
            extra={"prospect_id": prospect_id, "business_name": business_name},
        )
        return

    # Post Discord alert for non-opt-out replies
    stage = prospect.get("stage", "unknown")
    metro = prospect.get("metro", "")
    _post_discord_alert(
        f"**Reply from {business_name}** ({metro}, {stage})\n"
        f"> {text}"
    )
    logger.info(
        "reply_watcher.reply_received",
        extra={"prospect_id": prospect_id, "business_name": business_name},
    )


def start_watcher() -> bool:
    """Start the reply watcher background thread. Returns True if started, False if already running."""
    global _watcher_running

    with _watcher_lock:
        if _watcher_running:
            logger.info("reply_watcher.already_running")
            return False
        _watcher_running = True

    def _run() -> None:
        global _watcher_running
        try:
            watch_replies(_on_inbound_message)
        except Exception:
            logger.exception("reply_watcher.thread_crashed")
        finally:
            with _watcher_lock:
                _watcher_running = False

    thread = threading.Thread(target=_run, name="reply-watcher", daemon=True)
    thread.start()
    logger.info("reply_watcher.started")
    return True
