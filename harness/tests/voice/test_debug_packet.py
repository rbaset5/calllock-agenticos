"""Tests for Retell call debug packet generation."""

from __future__ import annotations

from db import repository
from voice.production.debug_packet import build_debug_packet


def _call_record() -> dict[str, object]:
    return {
        "tenant_id": "tenant-ace-001",
        "call_id": "call-001",
        "retell_call_id": "ret-001",
        "phone_number": "313-555-1212",
        "transcript": "User: My AC is out at 123 Oak St, Austin TX 78701. Call me at 313-555-1212.",
        "raw_retell_payload": {
            "recording_url": "https://retell.ai/recordings/ret-001.mp3",
            "transcript_object": [
                {"role": "user", "content": "My AC is out at 123 Oak St, Austin TX 78701."}
            ],
            "call_summary": "Caller at 123 Oak St needs AC service.",
            "disconnection_reason": "agent_hangup",
        },
        "extracted_fields": {
            "customer_name": "John Smith",
            "service_address": "123 Oak St, Austin TX 78701",
            "quality_score": 98,
            "scorecard_warnings": [],
            "route": "legitimate",
            "urgency_tier": "urgent",
            "tags": ["REPAIR_AC"],
        },
        "extraction_status": "complete",
        "quality_score": 98,
        "tags": ["REPAIR_AC"],
        "route": "legitimate",
        "urgency_tier": "urgent",
        "booking_id": None,
        "callback_scheduled": False,
        "call_duration_seconds": 120,
        "end_call_reason": "agent_hangup",
        "call_recording_url": "https://retell.ai/recordings/ret-001.mp3",
        "created_at": "2026-06-11T12:00:00+00:00",
    }


def _config_snapshot() -> dict[str, object]:
    return {
        "retell_agent_id": "agent-001",
        "retell_llm_id": "llm-001",
        "config_hash": "hash-001",
        "config_source_path": "knowledge/industry-packs/hvac/voice/retell-agent-v10.yaml",
    }


def test_debug_packet_includes_required_sections_and_redacts_pii() -> None:
    packet = build_debug_packet(
        call_record=_call_record(),
        events=[
            {
                "event_type": "supervisor_completed",
                "payload": {"guardian_gate": {"gate_passed": True, "quarantine": False, "gate_failures": []}},
            }
        ],
        tool_calls=[],
        config_snapshot=_config_snapshot(),
        safety_findings=[],
    )

    assert set(packet) >= {
        "identity",
        "retell",
        "config",
        "state_and_tools",
        "booking",
        "callback",
        "extraction",
        "supervisor",
        "safety_findings",
        "failure_bucket",
    }
    assert packet["identity"]["call_id"] == "call-001"
    assert "[REDACTED_PHONE]" in packet["retell"]["transcript"]
    assert "[REDACTED_ADDRESS]" in packet["retell"]["transcript"]
    assert "313-555-1212" not in packet["retell"]["transcript"]
    assert "123 Oak St" not in packet["extraction"]["extracted_fields"]["service_address"]


def test_failure_bucket_prioritizes_fake_booking_findings() -> None:
    packet = build_debug_packet(
        call_record=_call_record(),
        events=[],
        tool_calls=[],
        config_snapshot=_config_snapshot(),
        safety_findings=[
            {
                "finding_type": "fake_booking_claim",
                "severity": "high",
                "evidence": {"transcript": "Agent: you are booked for tomorrow"},
            }
        ],
    )

    assert packet["failure_bucket"] == "fake_booking"


def test_failure_bucket_is_clean_without_findings_when_extraction_complete() -> None:
    packet = build_debug_packet(
        call_record=_call_record(),
        events=[],
        tool_calls=[],
        config_snapshot=_config_snapshot(),
        safety_findings=[],
    )

    assert packet["failure_bucket"] == "clean"


def test_debug_packet_upsert_is_idempotent() -> None:
    packet = build_debug_packet(
        call_record=_call_record(),
        events=[],
        tool_calls=[],
        config_snapshot=_config_snapshot(),
        safety_findings=[],
    )

    first = repository.upsert_voice_call_debug_packet(
        {
            "tenant_id": "tenant-ace-001",
            "call_id": "call-001",
            "packet": packet,
            "failure_bucket": packet["failure_bucket"],
        }
    )
    second = repository.upsert_voice_call_debug_packet(
        {
            "tenant_id": "tenant-ace-001",
            "call_id": "call-001",
            "packet": {**packet, "failure_bucket": "unknown"},
            "failure_bucket": "unknown",
        }
    )

    assert second["id"] == first["id"]
    stored = repository.get_voice_call_debug_packet("tenant-ace-001", "call-001")
    assert stored is not None
    assert stored["failure_bucket"] == "unknown"

