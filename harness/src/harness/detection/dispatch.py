from __future__ import annotations

from typing import Any

from harness.dispatch import RunTaskRequest


def build_detection_dispatches(alert: dict[str, Any]) -> list[RunTaskRequest]:
    detection = (alert.get("metrics") or {}).get("detection", {})
    if not isinstance(detection, dict):
        return []

    outcome = str(detection.get("triage_outcome") or "")
    if outcome not in {"investigate", "escalate"}:
        return []

    alert_type = str(alert.get("alert_type") or "")
    worker_id = "eng-product-qa" if outcome == "escalate" else "voice-builder" if alert_type.startswith("voice_") else "eng-product-qa"
    priority = "high" if outcome == "escalate" else "medium"
    dedupe_key = str(detection.get("dedupe_key") or f"{alert.get('tenant_id') or 'global'}:{alert_type}")

    return [
        RunTaskRequest(
            worker_id=worker_id,
            task_type="detection-investigate",
            task_context={
                "task_type": "detection-investigate",
                "detection_issue": {
                    "alert_type": alert_type,
                    "triage_outcome": outcome,
                    "incident_key": dedupe_key,
                },
            },
            idempotency_key=f"detection:{dedupe_key}",
            priority=priority,
            requires_approval=outcome == "escalate",
        )
    ]
