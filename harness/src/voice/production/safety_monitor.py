"""Deterministic post-call safety and consistency checks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_BOOKING_CLAIMS = (
    "appointment is booked",
    "you are booked",
    "confirmed for",
    "i have you scheduled",
)
_CALLBACK_CLAIMS = (
    "we will call you back",
    "someone will call you",
    "technician will call",
    "owner will call",
)
_EMERGENCY_TERMS = (
    "gas smell",
    "smell gas",
    "gas leak",
    "carbon monoxide",
    "smoke",
    "fire",
    "burning smell",
    "sparking",
)
_SAFE_HANDLING_PHRASES = (
    "leave the house",
    "stay outside",
    "call 911",
    "call the gas company",
    "call the utility",
    "do not go back inside",
)
_BAD_TOOL_STATUSES = {
    "exception",
    "validation_failed",
    "auth_failed",
    "timeout_unknown",
}


def _text(call_record: Mapping[str, Any]) -> str:
    raw = call_record.get("raw_retell_payload")
    raw_payload = raw if isinstance(raw, Mapping) else {}
    return str(call_record.get("transcript") or raw_payload.get("transcript") or "").lower()


def _contains_any(text: str, phrases: Sequence[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _successful_tool(tool_calls: Sequence[Mapping[str, Any]], names: set[str]) -> bool:
    return any(
        str(call.get("tool_name")) in names and call.get("status") == "success"
        for call in tool_calls
    )


def _finding(
    *,
    call_record: Mapping[str, Any],
    finding_type: str,
    severity: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "tenant_id": call_record.get("tenant_id"),
        "call_id": call_record.get("call_id"),
        "finding_type": finding_type,
        "severity": severity,
        "status": "open",
        "evidence": dict(evidence),
    }


def _has_booking_evidence(
    *,
    call_record: Mapping[str, Any],
    tool_calls: Sequence[Mapping[str, Any]],
) -> bool:
    return bool(call_record.get("booking_id")) or _successful_tool(tool_calls, {"book_service"})


def _has_callback_evidence(
    *,
    call_record: Mapping[str, Any],
    tool_calls: Sequence[Mapping[str, Any]],
) -> bool:
    return bool(call_record.get("callback_scheduled")) or _successful_tool(
        tool_calls,
        {"create_callback", "create_callback_request"},
    )


def _has_emergency_safe_handling(call_record: Mapping[str, Any], transcript: str) -> bool:
    extracted = call_record.get("extracted_fields")
    extracted_fields = extracted if isinstance(extracted, Mapping) else {}
    return (
        _contains_any(transcript, _SAFE_HANDLING_PHRASES)
        or bool(extracted_fields.get("safety_emergency"))
        or call_record.get("end_call_reason") in {"safety_exit", "safety_emergency"}
    )


def evaluate_call_safety(
    *,
    call_record: Mapping[str, Any],
    tool_calls: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Evaluate a stored call for deterministic production-safety findings."""
    del events
    findings: list[dict[str, Any]] = []
    transcript = _text(call_record)

    if not call_record.get("tenant_id"):
        findings.append(
            _finding(
                call_record=call_record,
                finding_type="tenant_missing",
                severity="high",
                evidence={"reason": "call record has no tenant_id"},
            )
        )

    if _contains_any(transcript, _BOOKING_CLAIMS) and not _has_booking_evidence(
        call_record=call_record,
        tool_calls=tool_calls,
    ):
        findings.append(
            _finding(
                call_record=call_record,
                finding_type="fake_booking_claim",
                severity="high",
                evidence={"matched_claim_group": "booking"},
            )
        )

    if _contains_any(transcript, _CALLBACK_CLAIMS) and not _has_callback_evidence(
        call_record=call_record,
        tool_calls=tool_calls,
    ):
        findings.append(
            _finding(
                call_record=call_record,
                finding_type="callback_claim_without_callback",
                severity="medium",
                evidence={"matched_claim_group": "callback"},
            )
        )

    if _contains_any(transcript, _EMERGENCY_TERMS) and not _has_emergency_safe_handling(
        call_record,
        transcript,
    ):
        findings.append(
            _finding(
                call_record=call_record,
                finding_type="emergency_mishandled",
                severity="critical",
                evidence={"matched_claim_group": "emergency"},
            )
        )

    bad_tools = [
        {
            "tool_name": call.get("tool_name"),
            "status": call.get("status"),
            "error_type": call.get("error_type"),
            "error_message": call.get("error_message"),
        }
        for call in tool_calls
        if call.get("status") in _BAD_TOOL_STATUSES
    ]
    if bad_tools:
        findings.append(
            _finding(
                call_record=call_record,
                finding_type="tool_error_or_timeout",
                severity="medium",
                evidence={"tool_calls": bad_tools},
            )
        )

    return findings


__all__ = ["evaluate_call_safety"]
