from __future__ import annotations

import re
from typing import Any


PII_PATTERNS = [
    re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b"),
]
FORBIDDEN_PHRASES = ["guaranteed savings", "always safe", "ignore the alarm"]


def verify_output(
    output: dict[str, Any],
    *,
    tenant_config: dict[str, Any],
    required_fields: list[str],
) -> dict[str, Any]:
    reasons: list[str] = []
    for field in required_fields:
        if not output.get(field):
            reasons.append(f"Missing required field: {field}")

    text = " ".join(str(value) for value in output.values())
    for phrase in FORBIDDEN_PHRASES + tenant_config.get("forbidden_claims", []):
        if phrase.lower() in text.lower():
            reasons.append(f"Forbidden claim detected: {phrase}")
    for pattern in PII_PATTERNS:
        if pattern.search(text):
            reasons.append("PII leakage detected in output")
            break
    return {"passed": not reasons, "reasons": reasons}


def verification_node(state: dict[str, Any]) -> dict[str, Any]:
    task = state["task"]
    result = verify_output(
        state.get("worker_output", {}),
        tenant_config=task.get("tenant_config", {}),
        required_fields=["summary", "lead_route", "sentiment"],
    )
    if not result["passed"]:
        from harness.metrics import MetricsEmitter

        MetricsEmitter().emit(
            category="verification",
            event_name="block",
            tenant_id=state.get("tenant_id"),
            run_id=state.get("run_id"),
            dimensions={"reasons": result["reasons"]},
        )
    return {"verification": result}
