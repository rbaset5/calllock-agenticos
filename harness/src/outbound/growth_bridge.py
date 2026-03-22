from __future__ import annotations

import uuid
from typing import Any

try:
    from growth.events.lifecycle_handler import handle_lifecycle_transition
    from growth.memory.models import GrowthDuplicateError
    from growth.memory.repository import insert_touchpoint
except ModuleNotFoundError:  # pragma: no cover - supports `from src.outbound...` smoke path
    from src.growth.events.lifecycle_handler import handle_lifecycle_transition
    from src.growth.memory.models import GrowthDuplicateError
    from src.growth.memory.repository import insert_touchpoint

from . import store
from .constants import OUTBOUND_SOURCE_VERSION, OUTBOUND_TENANT_ID, OUTBOUND_UUID_NAMESPACE


def _call_touchpoint_id(twilio_call_sid: str) -> uuid.UUID:
    return uuid.uuid5(OUTBOUND_UUID_NAMESPACE, f"call-{twilio_call_sid}")


def _lifecycle_touchpoint_id(twilio_call_sid: str) -> uuid.UUID:
    return uuid.uuid5(OUTBOUND_UUID_NAMESPACE, f"lifecycle-{twilio_call_sid}")


def emit_call_outcome(call_record: dict[str, Any]) -> dict[str, bool]:
    twilio_call_sid = str(call_record["twilio_call_sid"])
    call_tp_id = _call_touchpoint_id(twilio_call_sid)
    lifecycle_tp_id = _lifecycle_touchpoint_id(twilio_call_sid)

    touchpoint_created = False
    lifecycle_created = False

    try:
        insert_touchpoint(
            {
                "touchpoint_id": str(call_tp_id),
                "tenant_id": call_record.get("tenant_id", OUTBOUND_TENANT_ID),
                "prospect_id": call_record["prospect_id"],
                "touchpoint_type": "outbound_call",
                "channel": "outbound-cold-call",
                "metadata": {
                    "outcome": call_record["outcome"],
                    "twilio_call_sid": twilio_call_sid,
                    "notes": call_record.get("notes"),
                    "call_hook_used": call_record.get("call_hook_used"),
                    "recording_url": call_record.get("recording_url"),
                },
                "source_component": "outbound-scout",
                "source_version": OUTBOUND_SOURCE_VERSION,
                "created_at": call_record.get("called_at"),
            }
        )
        touchpoint_created = True
    except GrowthDuplicateError:
        touchpoint_created = False

    lifecycle_state = None
    if call_record["outcome"] == "answered_interested":
        lifecycle_state = "interested"
    elif call_record["outcome"] == "answered_callback":
        lifecycle_state = "callback"

    if lifecycle_state is not None:
        try:
            handle_lifecycle_transition(
                {
                    "touchpoint_id": str(lifecycle_tp_id),
                    "tenant_id": call_record.get("tenant_id", OUTBOUND_TENANT_ID),
                    "prospect_id": call_record["prospect_id"],
                    "trigger_id": str(call_tp_id),
                    "to_state": lifecycle_state,
                    "channel": "outbound-cold-call",
                    "source_component": "outbound-scout",
                    "source_version": OUTBOUND_SOURCE_VERSION,
                    "created_at": call_record.get("called_at"),
                }
            )
            lifecycle_created = True
        except GrowthDuplicateError:
            lifecycle_created = False

    store.update_outbound_call_by_sid(twilio_call_sid, {"growth_memory_id": str(call_tp_id)})
    return {"touchpoint_created": touchpoint_created, "lifecycle_created": lifecycle_created}
