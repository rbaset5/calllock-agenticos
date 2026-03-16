from __future__ import annotations

from typing import Any, Callable


class HealthGateUnavailableError(RuntimeError):
    pass


class HealthGateTimeoutError(TimeoutError):
    pass


def _evaluate_message(message: dict[str, Any]) -> dict[str, Any]:
    if message.get("suppress_list_hit"):
        return {"status": "blocked", "reason": "suppress_list"}
    if message.get("duplicate_send"):
        return {"status": "blocked", "reason": "duplicate_send"}
    if message.get("volume_cap_exceeded"):
        return {"status": "blocked", "reason": "volume_cap"}
    if not message.get("required_compliance_fields_present", True):
        return {"status": "blocked", "reason": "missing_compliance_fields"}
    if message.get("domain_reputation") == "bad":
        return {"status": "blocked", "reason": "domain_reputation"}
    if float(message.get("bounce_rate", 0)) > 5:
        return {"status": "blocked", "reason": "bounce_rate"}
    if float(message.get("complaint_rate", 0)) > 0.3:
        return {"status": "blocked", "reason": "complaint_rate"}
    if not message.get("lifecycle_eligible", True):
        return {"status": "blocked", "reason": "lifecycle_ineligible"}
    return {"status": "approved", "reason": "approved"}


def check_health_gate(
    messages: list[dict[str, Any]],
    *,
    evaluator: Callable[[dict[str, Any]], dict[str, Any]] = _evaluate_message,
) -> dict[str, Any]:
    outcomes: list[dict[str, Any]] = []
    sent = queued = blocked = 0

    for index, message in enumerate(messages):
        try:
            decision = evaluator(message)
        except (HealthGateUnavailableError, HealthGateTimeoutError, TimeoutError, RuntimeError) as exc:
            reason = "gate_timeout" if isinstance(exc, (HealthGateTimeoutError, TimeoutError)) else "gate_unavailable"
            for queued_message in messages[index:]:
                outcomes.append(
                    {
                        "message_id": queued_message["message_id"],
                        "status": "queued",
                        "reason": reason,
                    }
                )
                queued += 1
            break

        if decision["status"] == "approved":
            outcomes.append({"message_id": message["message_id"], "status": "sent", "reason": decision["reason"]})
            sent += 1
            continue

        outcomes.append({"message_id": message["message_id"], "status": "blocked", "reason": decision["reason"]})
        blocked += 1

    return {
        "status": "pass" if queued == 0 and blocked == 0 else "mixed",
        "sent_count": sent,
        "queued_count": queued,
        "blocked_count": blocked,
        "outcomes": outcomes,
    }
