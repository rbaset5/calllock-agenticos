"""Tests for deterministic Retell post-call safety monitoring."""

from __future__ import annotations

from voice.production.safety_monitor import evaluate_call_safety


def _call_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "tenant_id": "tenant-ace-001",
        "call_id": "call-001",
        "retell_call_id": "ret-001",
        "transcript": "Agent: Thanks for calling. User: My AC is not cooling.",
        "booking_id": None,
        "callback_scheduled": False,
        "end_call_reason": "agent_hangup",
        "extraction_status": "complete",
        "extracted_fields": {},
    }
    record.update(overrides)
    return record


def _finding_types(findings: list[dict[str, object]]) -> set[str]:
    return {str(finding["finding_type"]) for finding in findings}


def test_fake_booking_claim_without_booking_evidence() -> None:
    findings = evaluate_call_safety(
        call_record=_call_record(
            transcript="Agent: You are booked for tomorrow morning. User: Thanks."
        ),
        tool_calls=[],
    )

    assert _finding_types(findings) == {"fake_booking_claim"}
    assert findings[0]["severity"] == "high"


def test_clean_booking_call_with_booking_id() -> None:
    findings = evaluate_call_safety(
        call_record=_call_record(
            transcript="Agent: You are booked for tomorrow morning. User: Thanks.",
            booking_id="booking-001",
        ),
        tool_calls=[],
    )

    assert findings == []


def test_callback_claim_without_callback_success() -> None:
    findings = evaluate_call_safety(
        call_record=_call_record(
            transcript="Agent: We will call you back within 30 minutes. User: Thanks."
        ),
        tool_calls=[],
    )

    assert _finding_types(findings) == {"callback_claim_without_callback"}
    assert findings[0]["severity"] == "medium"


def test_callback_claim_with_successful_tool_is_clean() -> None:
    findings = evaluate_call_safety(
        call_record=_call_record(
            transcript="Agent: We will call you back within 30 minutes. User: Thanks."
        ),
        tool_calls=[{"tool_name": "create_callback", "status": "success"}],
    )

    assert findings == []


def test_emergency_mishandled_without_safe_handling() -> None:
    findings = evaluate_call_safety(
        call_record=_call_record(
            transcript="User: I smell gas near the furnace. Agent: We can schedule you tomorrow."
        ),
        tool_calls=[],
    )

    assert _finding_types(findings) == {"emergency_mishandled"}
    assert findings[0]["severity"] == "critical"


def test_emergency_with_evacuate_instruction_is_clean() -> None:
    findings = evaluate_call_safety(
        call_record=_call_record(
            transcript="User: I smell gas near the furnace. Agent: Leave the house and call the gas company."
        ),
        tool_calls=[],
    )

    assert findings == []


def test_missing_tenant_raises_tenant_missing() -> None:
    findings = evaluate_call_safety(
        call_record=_call_record(tenant_id=None),
        tool_calls=[],
    )

    assert _finding_types(findings) == {"tenant_missing"}
    assert findings[0]["severity"] == "high"


def test_tool_exception_raises_tool_error_or_timeout() -> None:
    findings = evaluate_call_safety(
        call_record=_call_record(),
        tool_calls=[
            {
                "tool_name": "lookup_caller",
                "status": "exception",
                "error_message": "database unavailable",
            }
        ],
    )

    assert _finding_types(findings) == {"tool_error_or_timeout"}
    assert findings[0]["severity"] == "medium"

