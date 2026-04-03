"""Post-call iMessage follow-up for outbound sales calls.

After each call, generates a personalized text using extraction data
(objection type, buying temperature, pain signals) and sends it via
the imsg CLI. Triggered by Inngest OUTBOUND_EXTRACTION_COMPLETE event.

Guards: 72h cooldown, do_not_message flag, outcome-based skip.
On failure: logs to prospect_messages with status=failed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from . import store
from .constants import OUTBOUND_TENANT_ID
from .imsg_client import send_imessage
from .llm import llm_completion

logger = logging.getLogger(__name__)

COOLDOWN_HOURS = 72

FOLLOWUP_SYSTEM_PROMPT = (
    "You are writing a short iMessage text from Rashid, a sales rep for "
    "CallLock (AI receptionist for HVAC companies). Write ONE text message "
    "under 160 characters. Be casual, friendly, specific to their business. "
    "No emojis. Sign off with '- Rashid'."
)

# Outcomes that should NOT trigger a follow-up text
SKIP_OUTCOMES = {"wrong_number", "gatekeeper_blocked"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _within_cooldown(prospect: dict[str, Any]) -> bool:
    """Check if prospect was messaged within the cooldown window."""
    last = prospect.get("last_messaged_at")
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - last_dt).total_seconds() < COOLDOWN_HOURS * 3600
    except (ValueError, TypeError):
        return False


def _build_user_prompt(
    prospect: dict[str, Any],
    outcome: str,
    extraction: dict[str, Any] | None,
) -> str:
    """Build the LLM user prompt from prospect context and extraction data."""
    name = prospect.get("business_name", "")
    metro = prospect.get("metro", "")

    lines = [f"Outcome: {outcome}", f"Business: {name}", f"Metro: {metro}"]

    if extraction:
        pain = extraction.get("missed_call_pain")
        if pain and pain != "none":
            lines.append(f"Pain level on missed calls: {pain}")
        objection = extraction.get("objection_type")
        if objection and objection != "none":
            lines.append(f"Objection: {objection}")
        temp = extraction.get("buying_temperature")
        if temp:
            lines.append(f"Buying temperature: {temp}")
        status_quo = extraction.get("status_quo_details")
        if status_quo:
            lines.append(f"How they handle calls today: {status_quo}")
        follow_up = extraction.get("follow_up_action")
        if follow_up and follow_up != "none":
            lines.append(f"Agreed next step: {follow_up}")

    return "\n".join(lines)


def emit_followup_text(
    *,
    prospect_id: str,
    outcome: str,
    extraction_data: dict[str, Any] | None = None,
    tenant_id: str = OUTBOUND_TENANT_ID,
) -> dict[str, Any]:
    """Generate and send a follow-up iMessage after a call.

    Returns dict with keys: sent, skipped, reason, message_id.
    """
    # Skip outcomes that shouldn't get texts
    if outcome in SKIP_OUTCOMES:
        logger.info("followup.skip_outcome", extra={"prospect_id": prospect_id, "outcome": outcome})
        return {"sent": False, "skipped": True, "reason": f"outcome_{outcome}"}

    # Fetch prospect
    prospect = store.get_outbound_prospect(prospect_id, tenant_id=tenant_id)
    if not prospect:
        logger.warning("followup.prospect_not_found", extra={"prospect_id": prospect_id})
        return {"sent": False, "skipped": True, "reason": "prospect_not_found"}

    # Check do_not_message
    if prospect.get("do_not_message"):
        logger.info("followup.do_not_message", extra={"prospect_id": prospect_id})
        return {"sent": False, "skipped": True, "reason": "do_not_message"}

    # Check disqualified
    if prospect.get("stage") == "disqualified":
        logger.info("followup.disqualified", extra={"prospect_id": prospect_id})
        return {"sent": False, "skipped": True, "reason": "disqualified"}

    # Check cooldown
    if _within_cooldown(prospect):
        logger.info("followup.cooldown", extra={"prospect_id": prospect_id})
        return {"sent": False, "skipped": True, "reason": "cooldown_72h"}

    phone = prospect.get("phone_normalized") or prospect.get("phone")
    if not phone:
        logger.warning("followup.no_phone", extra={"prospect_id": prospect_id})
        return {"sent": False, "skipped": True, "reason": "no_phone"}

    # Generate text via LLM
    user_prompt = _build_user_prompt(prospect, outcome, extraction_data)
    llm_result = llm_completion(
        system_prompt=FOLLOWUP_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.7,
    )

    if llm_result["status"] != "complete" or not llm_result["text"]:
        logger.error("followup.llm_failed", extra={"prospect_id": prospect_id, "status": llm_result["status"]})
        store.insert_prospect_message({
            "tenant_id": tenant_id,
            "prospect_id": prospect_id,
            "direction": "outbound",
            "content": f"[LLM_FAILED] {user_prompt[:200]}",
            "outcome_trigger": outcome,
            "status": "failed",
            "phone_normalized": phone,
        })
        return {"sent": False, "skipped": False, "reason": "llm_failed"}

    text = llm_result["text"]

    # Update last_messaged_at BEFORE send to prevent duplicates
    store.update_outbound_prospect(prospect_id, {"last_messaged_at": _now_iso()})

    # Send via imsg
    send_result = send_imessage(phone, text)

    if send_result["success"]:
        msg = store.insert_prospect_message({
            "tenant_id": tenant_id,
            "prospect_id": prospect_id,
            "direction": "outbound",
            "content": text,
            "outcome_trigger": outcome,
            "status": "sent",
            "imsg_result": send_result,
            "sent_at": _now_iso(),
            "phone_normalized": phone,
        })
        logger.info(
            "followup.sent",
            extra={"prospect_id": prospect_id, "outcome": outcome, "message_id": msg.get("id")},
        )
        return {"sent": True, "skipped": False, "reason": None, "message_id": msg.get("id")}

    # Send failed: revert last_messaged_at so the prospect can be retried
    store.update_outbound_prospect(prospect_id, {"last_messaged_at": None})

    msg = store.insert_prospect_message({
        "tenant_id": tenant_id,
        "prospect_id": prospect_id,
        "direction": "outbound",
        "content": text,
        "outcome_trigger": outcome,
        "status": "failed",
        "imsg_result": send_result,
        "phone_normalized": phone,
    })
    logger.error(
        "followup.send_failed",
        extra={
            "prospect_id": prospect_id,
            "outcome": outcome,
            "error": send_result.get("error"),
        },
    )
    return {"sent": False, "skipped": False, "reason": f"imsg_failed: {send_result.get('error')}"}
