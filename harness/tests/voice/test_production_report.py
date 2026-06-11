"""Tests for weekly Retell production reporting."""

from __future__ import annotations

from db import repository
from voice.services.production_report import build_voice_production_report


TENANT_ID = "tenant-ace-001"


def _insert_call(
    call_id: str,
    *,
    booking_id: str | None = None,
    callback_scheduled: bool = False,
    quality_score: int = 96,
    extraction_status: str = "complete",
) -> None:
    repository.insert_call_record(
        TENANT_ID,
        call_id,
        f"ret-{call_id}",
        {
            "call_id": f"ret-{call_id}",
            "from_number": "+15125550101",
            "transcript": "User: My AC is not cooling.",
        },
    )
    repository.update_call_record_extraction(
        TENANT_ID,
        call_id,
        {
            "extraction_status": extraction_status,
            "quality_score": quality_score,
            "tags": ["REPAIR_AC"],
            "route": "legitimate",
            "urgency_tier": "urgent",
        },
        booking_id=booking_id,
        callback_scheduled=callback_scheduled,
    )


def _record_snapshot(call_id: str) -> None:
    repository.record_voice_config_snapshot(
        {
            "tenant_id": TENANT_ID,
            "call_id": call_id,
            "retell_agent_id": "agent-001",
            "retell_llm_id": "llm-001",
            "config_source_path": "knowledge/industry-packs/hvac/voice/retell-agent-v10.yaml",
            "config_hash": "hash-001",
            "config_snapshot": {"model": "gpt-4o-mini"},
        }
    )


def test_empty_production_report_returns_zero_counts() -> None:
    report = build_voice_production_report(days=7)

    assert report["total_calls"] == 0
    assert report["booked_calls"] == 0
    assert report["callback_calls"] == 0
    assert report["safety_findings"]["total"] == 0
    assert report["tool_failures"]["total"] == 0
    assert report["top_recommended_fix"]["code"] == "no_issue_detected"
    assert report["migration_gate"] == {
        "retell_replacement_recommended": False,
        "reasons": [],
        "evidence_threshold_met": False,
    }


def test_production_report_summarizes_calls_tools_findings_and_top_fix() -> None:
    _insert_call("call-001", booking_id="book-001")
    _insert_call("call-002", callback_scheduled=True)
    _insert_call("call-003", quality_score=62)
    _insert_call("call-004")
    _record_snapshot("call-001")
    _record_snapshot("call-002")
    _record_snapshot("call-004")

    repository.record_voice_tool_call(
        {
            "tenant_id": TENANT_ID,
            "call_id": "call-001",
            "retell_call_id": "ret-call-001",
            "tool_name": "lookup_caller",
            "request_payload": {},
            "response_payload": {},
            "status": "success",
            "latency_ms": 100,
        }
    )
    repository.record_voice_tool_call(
        {
            "tenant_id": TENANT_ID,
            "call_id": "call-002",
            "retell_call_id": "ret-call-002",
            "tool_name": "lookup_caller",
            "request_payload": {},
            "response_payload": {},
            "status": "exception",
            "latency_ms": 250,
            "error_message": "timeout",
        }
    )
    repository.record_voice_tool_call(
        {
            "tenant_id": TENANT_ID,
            "call_id": "call-003",
            "retell_call_id": "ret-call-003",
            "tool_name": "book_service",
            "request_payload": {},
            "response_payload": {},
            "status": "validation_failed",
            "latency_ms": 400,
        }
    )
    repository.record_voice_safety_findings(
        [
            {
                "tenant_id": TENANT_ID,
                "call_id": "call-003",
                "finding_type": "emergency_mishandled",
                "severity": "critical",
                "status": "open",
                "evidence": {},
            },
            {
                "tenant_id": TENANT_ID,
                "call_id": "call-004",
                "finding_type": "fake_booking_claim",
                "severity": "high",
                "status": "resolved",
                "evidence": {},
            },
        ]
    )

    report = build_voice_production_report(tenant_id=TENANT_ID, days=7)

    assert report["tenant_id"] == TENANT_ID
    assert report["total_calls"] == 4
    assert report["booked_calls"] == 1
    assert report["callback_calls"] == 1
    assert report["safety_findings"]["by_type"] == {
        "emergency_mishandled": 1,
        "fake_booking_claim": 1,
    }
    assert report["safety_findings"]["by_severity"] == {"critical": 1, "high": 1}
    assert report["unresolved_findings"] == 1
    assert report["tool_failures"]["by_tool"] == {"book_service": 1, "lookup_caller": 1}
    assert report["tool_latency_p95_ms"] == {"book_service": 400, "lookup_caller": 250}
    assert report["config_snapshots"]["missing"] == 1
    assert report["extraction_drift"]["low_quality_calls"] == 1
    assert report["top_recommended_fix"]["code"] == "critical_emergency_findings"
    assert report["migration_gate"]["retell_replacement_recommended"] is False
    assert report["migration_gate"]["evidence_threshold_met"] is False


def test_migration_gate_requires_repeated_severe_failures_at_volume() -> None:
    for index in range(30):
        call_id = f"call-{index:03d}"
        _insert_call(call_id)
        _record_snapshot(call_id)
    repository.record_voice_safety_findings(
        [
            {
                "tenant_id": TENANT_ID,
                "call_id": f"call-{index:03d}",
                "finding_type": "emergency_mishandled",
                "severity": "critical",
                "status": "open",
                "evidence": {},
            }
            for index in range(4)
        ]
    )

    report = build_voice_production_report(tenant_id=TENANT_ID, days=7)

    assert report["migration_gate"]["evidence_threshold_met"] is True
    assert report["migration_gate"]["retell_replacement_recommended"] is True
    assert "repeated_critical_safety_findings" in report["migration_gate"]["reasons"]
