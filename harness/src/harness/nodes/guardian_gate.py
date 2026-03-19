"""Pre-persist guardian gate.

Inspired by the Antspace pre-stop hook pattern: a multi-condition checkpoint
that prevents bad data from reaching the persistence layer. Records that fail
the gate are quarantined — they persist for audit/debugging but are invisible
to app-facing queries via RLS.

Gate conditions:
1. Verification must have passed (verdict == "pass") or be an expected block.
2. Required output fields must be present (no null where contract says required).
3. Tenant ID must be set (prevents orphan records).
"""

from __future__ import annotations

from typing import Any

# Required fields that must be non-null for voice pipeline records.
# Derived from the seam contract's required_chain fields.
# Only enforced for workers whose output feeds the App (voice pipeline).
VOICE_PIPELINE_REQUIRED_FIELDS = frozenset([
    "customer_name",
    "customer_phone",
    "urgency_tier",
    "caller_type",
    "problem_description",
])

# Workers whose output feeds the voice → app pipeline.
# Other workers (customer-analyst, product-manager, etc.) bypass field checks.
VOICE_PIPELINE_WORKERS = frozenset([
    "eng-ai-voice",
    "eng-app",
    "eng-product-qa",
])


def _check_verification_passed(state: dict[str, Any]) -> str | None:
    verification = state.get("verification", {})
    verdict = verification.get("verdict")
    if verdict == "pass":
        return None
    if verdict == "block" and state.get("policy_decision", {}).get("verdict") != "allow":
        return None  # policy block is an expected path, not a gate failure
    return f"verification_verdict={verdict}"


def _check_required_fields(state: dict[str, Any]) -> str | None:
    # Only enforce for voice pipeline workers whose output reaches the App.
    worker_id = state.get("worker_id", "")
    if worker_id not in VOICE_PIPELINE_WORKERS:
        return None
    output = state.get("worker_output", {})
    if not output or output.get("status") == "blocked":
        return None  # blocked runs don't have output fields
    missing = [f for f in VOICE_PIPELINE_REQUIRED_FIELDS if not output.get(f)]
    if missing:
        return f"missing_required_fields={','.join(sorted(missing))}"
    return None


def _check_tenant_id(state: dict[str, Any]) -> str | None:
    if not state.get("tenant_id"):
        return "missing_tenant_id"
    return None


GATE_CHECKS = [
    _check_verification_passed,
    _check_required_fields,
    _check_tenant_id,
]


def evaluate_guardian_gate(state: dict[str, Any]) -> dict[str, Any]:
    """Run all gate conditions.  Return gate result dict."""
    failures = []
    for check in GATE_CHECKS:
        reason = check(state)
        if reason is not None:
            failures.append(reason)

    passed = len(failures) == 0
    return {
        "gate_passed": passed,
        "quarantine": not passed,
        "gate_failures": failures,
    }


def guardian_gate_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: evaluate the guardian gate and set quarantine flag."""
    return {"guardian_gate": evaluate_guardian_gate(state)}
