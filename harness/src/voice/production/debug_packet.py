"""Build operator-readable debug packets for Retell calls."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from observability.pii_redactor import redact_pii_recursive

_FINDING_BUCKETS = {
    "tenant_missing": "tenant_missing",
    "emergency_mishandled": "emergency_failure",
    "fake_booking_claim": "fake_booking",
    "callback_claim_without_callback": "callback_failure",
    "tool_error_or_timeout": "tool_failure",
    "low_quality_extraction": "low_quality_extraction",
}
_BUCKET_PRIORITY = [
    "tenant_missing",
    "emergency_failure",
    "fake_booking",
    "callback_failure",
    "tool_failure",
    "low_quality_extraction",
    "unknown",
    "clean",
]


def _latest_event_payload(events: Sequence[Mapping[str, Any]], event_type: str) -> dict[str, Any]:
    for event in reversed(events):
        if event.get("event_type") != event_type:
            continue
        payload = event.get("payload")
        return dict(payload) if isinstance(payload, Mapping) else {}
    return {}


def _failure_bucket(
    *,
    call_record: Mapping[str, Any],
    safety_findings: Sequence[Mapping[str, Any]],
) -> str:
    buckets = {
        _FINDING_BUCKETS.get(str(finding.get("finding_type")), "unknown")
        for finding in safety_findings
    }
    if not buckets:
        return "clean" if call_record.get("extraction_status") == "complete" else "low_quality_extraction"
    return min(buckets, key=_BUCKET_PRIORITY.index)


def _tool_success(tool_calls: Sequence[Mapping[str, Any]], names: set[str]) -> bool:
    return any(
        str(call.get("tool_name")) in names and call.get("status") == "success"
        for call in tool_calls
    )


def build_debug_packet(
    *,
    call_record: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    tool_calls: Sequence[Mapping[str, Any]],
    config_snapshot: Mapping[str, Any] | None,
    safety_findings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build an idempotent debug packet from persisted call evidence."""
    raw_payload = call_record.get("raw_retell_payload")
    raw = raw_payload if isinstance(raw_payload, Mapping) else {}
    extracted = call_record.get("extracted_fields")
    extracted_fields = extracted if isinstance(extracted, Mapping) else {}
    config = config_snapshot or {}
    supervisor_payload = _latest_event_payload(events, "supervisor_completed")
    guardian_gate = supervisor_payload.get("guardian_gate", {})
    bucket = _failure_bucket(call_record=call_record, safety_findings=safety_findings)

    packet = {
        "identity": {
            "tenant_id": call_record.get("tenant_id"),
            "call_id": call_record.get("call_id"),
            "retell_call_id": call_record.get("retell_call_id"),
            "phone_number": redact_pii_recursive(call_record.get("phone_number")),
            "created_at": call_record.get("created_at"),
            "duration_seconds": call_record.get("call_duration_seconds"),
        },
        "retell": {
            "recording_url": call_record.get("call_recording_url") or raw.get("recording_url"),
            "transcript": redact_pii_recursive(call_record.get("transcript") or raw.get("transcript") or ""),
            "transcript_object": redact_pii_recursive(raw.get("transcript_object", [])),
            "call_summary": redact_pii_recursive(raw.get("call_summary")),
            "disconnection_reason": raw.get("disconnection_reason") or call_record.get("end_call_reason"),
        },
        "config": {
            "retell_agent_id": config.get("retell_agent_id"),
            "retell_llm_id": config.get("retell_llm_id"),
            "config_hash": config.get("config_hash"),
            "config_source_path": config.get("config_source_path"),
        },
        "state_and_tools": {
            "state_path": raw.get("state_path", []),
            "state_path_unknown": not bool(raw.get("state_path")),
            "tool_calls": redact_pii_recursive(list(tool_calls)),
        },
        "booking": {
            "booking_id": call_record.get("booking_id"),
            "booking_claim_detected": any(
                finding.get("finding_type") == "fake_booking_claim"
                for finding in safety_findings
            ),
            "booking_tool_success": _tool_success(tool_calls, {"book_service"}),
        },
        "callback": {
            "callback_scheduled": bool(call_record.get("callback_scheduled")),
            "callback_claim_detected": any(
                finding.get("finding_type") == "callback_claim_without_callback"
                for finding in safety_findings
            ),
            "callback_tool_success": _tool_success(tool_calls, {"create_callback", "create_callback_request"}),
        },
        "extraction": {
            "extraction_status": call_record.get("extraction_status"),
            "quality_score": call_record.get("quality_score") or extracted_fields.get("quality_score"),
            "route": call_record.get("route") or extracted_fields.get("route"),
            "urgency_tier": call_record.get("urgency_tier") or extracted_fields.get("urgency_tier"),
            "tags": call_record.get("tags") or extracted_fields.get("tags", []),
            "scorecard_warnings": extracted_fields.get("scorecard_warnings", []),
            "extracted_fields": redact_pii_recursive(dict(extracted_fields)),
        },
        "supervisor": {
            "guardian_gate": guardian_gate,
            "quarantine": bool(isinstance(guardian_gate, Mapping) and guardian_gate.get("quarantine")),
            "gate_failures": guardian_gate.get("gate_failures", []) if isinstance(guardian_gate, Mapping) else [],
        },
        "safety_findings": redact_pii_recursive(list(safety_findings)),
        "failure_bucket": bucket,
    }
    return packet


__all__ = ["build_debug_packet"]

