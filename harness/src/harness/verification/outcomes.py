from __future__ import annotations

from typing import Any


SEVERITY_ORDER = ("block", "escalate", "retry")


def resolve_verification_outcome(
    findings: list[dict[str, Any]],
    *,
    retry_count: int = 0,
    max_retries: int = 1,
) -> dict[str, Any]:
    reasons = [finding["reason"] for finding in findings]
    verdict = "pass"
    severities = {finding["severity"] for finding in findings}
    if "block" in severities:
        verdict = "block"
    elif "escalate" in severities:
        verdict = "escalate"
    elif "retry" in severities:
        verdict = "retry" if retry_count < max_retries else "escalate"
    return {"passed": verdict == "pass", "verdict": verdict, "reasons": reasons, "findings": findings}
