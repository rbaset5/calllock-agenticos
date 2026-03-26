from __future__ import annotations

from harness.nodes.guardian_gate import evaluate_guardian_gate


def _state(
    *,
    worker_id: str = "eng-ai-voice",
    verification_verdict: str = "pass",
    verification_passed: bool = True,
    tenant_id: str = "tenant-1",
    worker_output: dict[str, object] | None = None,
    policy_verdict: str = "allow",
) -> dict[str, object]:
    return {
        "worker_id": worker_id,
        "tenant_id": tenant_id,
        "policy_decision": {"verdict": policy_verdict},
        "verification": {
            "verdict": verification_verdict,
            "passed": verification_passed,
        },
        "worker_output": worker_output
        or {
            "customer_name": "Jane Doe",
            "customer_phone": "+15551234567",
            "urgency_tier": "urgent",
            "caller_type": "customer",
            "problem_description": "AC not cooling",
        },
    }


def test_guardian_gate_passes_when_all_checks_pass() -> None:
    result = evaluate_guardian_gate(_state())

    assert result == {
        "gate_passed": True,
        "quarantine": False,
        "gate_failures": [],
    }


def test_guardian_gate_quarantines_missing_customer_name() -> None:
    result = evaluate_guardian_gate(
        _state(
            worker_output={
                "customer_name": "",
                "customer_phone": "+15551234567",
                "urgency_tier": "urgent",
                "caller_type": "customer",
                "problem_description": "AC not cooling",
            }
        )
    )

    assert result["quarantine"] is True
    assert result["gate_failures"] == ["missing_required_fields=customer_name"]


def test_guardian_gate_quarantines_missing_tenant_id() -> None:
    result = evaluate_guardian_gate(_state(tenant_id=""))

    assert result["quarantine"] is True
    assert "missing_tenant_id" in result["gate_failures"]


def test_guardian_gate_skips_required_field_checks_for_non_voice_workers() -> None:
    result = evaluate_guardian_gate(
        _state(
            worker_id="customer-analyst",
            worker_output={"summary": "Customer called about no heat."},
        )
    )

    assert result["gate_passed"] is True
    assert result["gate_failures"] == []


def test_guardian_gate_reports_combined_failures() -> None:
    result = evaluate_guardian_gate(
        _state(
            verification_verdict="retry",
            verification_passed=False,
            tenant_id="",
            worker_output={
                "customer_name": "",
                "customer_phone": "",
                "urgency_tier": "",
                "caller_type": "",
                "problem_description": "",
            },
        )
    )

    assert result["quarantine"] is True
    assert result["gate_failures"] == [
        "verification_verdict=retry",
        "missing_required_fields=caller_type,customer_name,customer_phone,problem_description,urgency_tier",
        "missing_tenant_id",
    ]
