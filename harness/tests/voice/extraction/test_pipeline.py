"""Tests for the extraction pipeline runner."""

from __future__ import annotations

import voice.extraction.pipeline as extraction_pipeline


def test_run_extraction_returns_complete_result_for_happy_path() -> None:
    payload = {
        "call_id": "ret-call-001",
        "from_number": "+15125550101",
        "call_summary": "Customer reports AC not cooling.",
        "disconnection_reason": "agent_hangup",
        "start_timestamp": 1710600000000,
        "retell_llm_dynamic_variables": {
            "service_address": "123 Oak Street, Austin, TX 78701",
            "problem_description": "AC not cooling",
            "urgency_tier": "urgent",
            "booking_confirmed": "false",
        },
    }
    transcript = (
        "Agent: Thank you for calling.\n"
        "User: My name is John Smith.\n"
        "User: My AC is not cooling.\n"
        "User: It stopped working this morning."
    )

    result = extraction_pipeline.run_extraction(transcript, payload)

    assert result["extraction_status"] == "complete"
    assert result["customer_name"] == "John Smith"
    assert result["service_address"] == "123 Oak Street, Austin, TX 78701"
    assert result["urgency_level"] == "Urgent"
    assert result["urgency_tier"] == "urgent"
    assert result["hvac_issue_type"] == "No Cool"
    assert result["quality_score"] > 0
    assert result["caller_type"] == "residential"
    assert result["primary_intent"] == "service"
    assert result["route"] == "legitimate"
    assert result["extracted_fields"]["problem_duration"] == {
        "raw": "this morning",
        "category": "acute",
    }


def test_run_extraction_marks_partial_when_one_step_fails(monkeypatch) -> None:
    payload = {
        "call_id": "ret-call-002",
        "from_number": "+15125550102",
        "retell_llm_dynamic_variables": {"problem_description": "furnace not working"},
    }

    def explode(_: str | None) -> str | None:
        raise RuntimeError("boom")

    monkeypatch.setattr(extraction_pipeline, "extract_customer_name", explode)
    result = extraction_pipeline.run_extraction("User: My furnace is broken.", payload)

    assert result["extraction_status"] == "partial"
    assert "customer_name" in result["failed_steps"]
    assert result["urgency_level"] == "Routine"
    assert result["route"] == "legitimate"


def test_run_extraction_handles_empty_transcript_with_safe_defaults() -> None:
    result = extraction_pipeline.run_extraction("", {"call_id": "ret-call-003"})

    assert result["extraction_status"] == "complete"
    assert result["urgency_level"] == "Routine"
    assert result["urgency_tier"] == "routine"
    assert result["route"] == "legitimate"
    assert result["tags"] == []
    assert result["quality_score"] == 0
    assert "zero-tags" in result["scorecard_warnings"]
    assert "callback-gap" in result["scorecard_warnings"]
