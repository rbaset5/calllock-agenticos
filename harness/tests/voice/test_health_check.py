from __future__ import annotations

from datetime import date
import subprocess

import pytest

from voice.extraction.pipeline import run_extraction
from voice.services import health_check


def make_call_row(
    *,
    call_id: str,
    transcript: str,
    dynamic_variables: dict[str, object] | None = None,
) -> dict[str, object]:
    raw_payload = {
        "call_id": call_id,
        "transcript": transcript,
        "from_number": "+15125550101",
        "call_summary": "Customer needs HVAC service.",
        "disconnection_reason": "booking_confirmed",
        "retell_llm_dynamic_variables": {
            "service_address": "123 Oak Street, Austin, TX 78701",
            "problem_description": "AC not cooling",
            "urgency_tier": "urgent",
            "booking_confirmed": "true",
            **(dynamic_variables or {}),
        },
    }
    extracted = run_extraction(transcript, raw_payload)
    return {
        "call_id": call_id,
        "transcript": transcript,
        "raw_retell_payload": raw_payload,
        "extracted_fields": extracted,
        "tags": extracted["tags"],
        "quality_score": extracted["quality_score"],
        "urgency_tier": extracted["urgency_tier"],
        "caller_type": extracted["caller_type"],
        "primary_intent": extracted["primary_intent"],
        "route": extracted["route"],
        "revenue_tier": extracted["revenue_tier"],
        "end_call_reason": extracted["end_call_reason"],
        "phone_number": extracted["customer_phone"],
        "created_at": "2026-03-17T10:00:00Z",
    }


def test_run_daily_health_check_returns_green_report(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        make_call_row(
            call_id="call-1",
            transcript=(
                "Agent: Thank you for calling. "
                "User: My name is John Smith. My AC is not cooling and the house is hot. "
                "User: I live at 123 Oak Street in Austin. "
                "User: Please book the first available appointment."
            ),
        ),
        make_call_row(
            call_id="call-2",
            transcript=(
                "Agent: How can I help? "
                "User: This is Maria Garcia. Our furnace stopped working this morning. "
                "User: The home is at 456 Pine Avenue, Austin. "
                "User: Go ahead and schedule the repair visit."
            ),
            dynamic_variables={"problem_description": "Furnace not working"},
        ),
    ]

    monkeypatch.setattr(health_check, "list_recent_call_records", lambda **kwargs: rows)
    monkeypatch.setattr(health_check, "_run_config_drift_check", lambda: (False, False))

    report = health_check.run_daily_health_check(today=date(2026, 3, 17))

    assert report == {
        "agent": "eng-ai-voice",
        "report_type": "voice-health-check",
        "date": "2026-03-17",
        "status": "green",
        "calls_sampled": 2,
        "extraction_accuracy": 1.0,
        "classification_accuracy": 1.0,
        "zero_tag_rate": 0.0,
        "config_drift": False,
        "scorecard_warnings": 0,
        "issues_created": 0,
        "prs_created": 0,
    }


def test_run_daily_health_check_degrades_when_fields_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    healthy = make_call_row(
        call_id="call-1",
        transcript=(
            "Agent: Thank you for calling. "
            "User: My name is John Smith. My AC is not cooling at 123 Oak Street. "
            "User: Please schedule a visit today."
        ),
    )
    drifted = make_call_row(
        call_id="call-2",
        transcript=(
            "Agent: How can I help? "
            "User: I am Maria Garcia and my furnace quit yesterday at 456 Pine Avenue. "
            "User: Please book the appointment."
        ),
        dynamic_variables={"problem_description": "Furnace quit yesterday"},
    )
    assert isinstance(drifted["extracted_fields"], dict)
    drifted["extracted_fields"] = dict(drifted["extracted_fields"])
    drifted["extracted_fields"]["customer_name"] = "Wrong Name"
    drifted["extracted_fields"]["tags"] = ["NOT_IN_TAXONOMY"]

    monkeypatch.setattr(health_check, "list_recent_call_records", lambda **kwargs: [healthy, drifted])
    monkeypatch.setattr(health_check, "_run_config_drift_check", lambda: (True, False))

    report = health_check.run_daily_health_check(today=date(2026, 3, 17))

    assert report["status"] == "yellow"
    assert report["config_drift"] is True
    assert report["calls_sampled"] == 2
    assert report["extraction_accuracy"] < 1.0
    assert report["classification_accuracy"] < 1.0


def test_run_daily_health_check_marks_red_when_zero_tag_rate_is_critical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    zero_tag_row = make_call_row(
        call_id="call-3",
        transcript="User: Hello.",
        dynamic_variables={"problem_description": ""},
    )

    monkeypatch.setattr(health_check, "list_recent_call_records", lambda **kwargs: [zero_tag_row])
    monkeypatch.setattr(health_check, "_run_config_drift_check", lambda: (False, False))

    report = health_check.run_daily_health_check(today=date(2026, 3, 17))

    assert report["status"] == "red"
    assert report["zero_tag_rate"] == 1.0
    assert report["scorecard_warnings"] >= 1


def test_run_config_drift_check_interprets_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETELL_LLM_ID", "llm_test")
    monkeypatch.setenv("RETELL_API_KEY", "retell_test")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="2 field(s) differ", stderr="")

    monkeypatch.setattr(health_check.subprocess, "run", fake_run)

    drift, failed = health_check._run_config_drift_check()

    assert drift is True
    assert failed is False
