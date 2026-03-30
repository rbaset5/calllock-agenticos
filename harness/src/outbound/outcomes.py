from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import store
from .constants import OUTBOUND_TENANT_ID
from .growth_bridge import emit_call_outcome


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stage_update_for_outcome(
    outcome: str,
    *,
    demo_scheduled: bool = False,
    callback_date: str | None = None,
) -> dict[str, Any]:
    if outcome == "answered_interested":
        if demo_scheduled:
            return {
                "stage": "converted",
                "next_action_date": None,
                "next_action_type": None,
            }
        return {
            "stage": "interested",
            "next_action_type": "close_attempt",
        }
    if outcome == "answered_callback":
        return {
            "stage": "callback",
            "next_action_date": callback_date,
            "next_action_type": "callback",
        }
    if outcome == "wrong_number":
        return {
            "stage": "disqualified",
            "disqualification_reason": "wrong_number",
            "next_action_date": None,
            "next_action_type": None,
        }
    return {
        "stage": "called",
        "next_action_date": None,
        "next_action_type": None,
    }


def log_call_outcome(
    *,
    prospect_id: str,
    twilio_call_sid: str,
    outcome: str,
    notes: str | None = None,
    call_hook_used: str | None = None,
    demo_scheduled: bool = False,
    callback_date: str | None = None,
    recording_url: str | None = None,
    transcript: str | None = None,
) -> dict[str, Any]:
    insert_result = store.insert_outbound_call(
        {
            "tenant_id": OUTBOUND_TENANT_ID,
            "prospect_id": prospect_id,
            "twilio_call_sid": twilio_call_sid,
            "called_at": _now_iso(),
            "outcome": outcome,
            "notes": notes,
            "call_hook_used": call_hook_used,
            "demo_scheduled": demo_scheduled,
            "callback_date": callback_date,
            "recording_url": recording_url,
            "transcript": transcript,
        }
    )
    if not insert_result["inserted"]:
        return {"inserted": False, "growth": None, "record": None}

    record = insert_result["record"]
    store.update_outbound_prospect(
        prospect_id,
        stage_update_for_outcome(
            outcome,
            demo_scheduled=demo_scheduled,
            callback_date=callback_date,
        ),
    )
    growth = emit_call_outcome(record)
    return {"inserted": True, "growth": growth, "record": record}
