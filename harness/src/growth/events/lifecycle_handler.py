from __future__ import annotations

from typing import Any

from growth.events.touchpoint_handler import handle_touchpoint


def handle_lifecycle_transition(payload: dict[str, Any]) -> dict[str, Any]:
    touchpoint_payload: dict[str, Any] = {
        "touchpoint_id": payload["touchpoint_id"],
        "tenant_id": payload["tenant_id"],
        "prospect_id": payload["prospect_id"],
        "touchpoint_type": "lifecycle_transitioned",
        "channel": payload.get("channel", "cold_email"),
        "experiment_id": payload.get("experiment_id"),
        "arm_id": payload.get("arm_id"),
        "signal_quality_score": payload.get("signal_quality_score"),
        "cost": payload.get("cost", 0),
        "metadata": {
            "to_state": payload["to_state"],
            "trigger_id": payload["trigger_id"],
            **payload.get("metadata", {}),
        },
        "source_component": payload.get("source_component", "growth.lifecycle"),
        "source_version": payload["source_version"],
        "seasonal_context": payload.get("seasonal_context", {}),
        "created_at": payload.get("created_at"),
    }
    return handle_touchpoint(touchpoint_payload)
