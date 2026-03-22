from __future__ import annotations

from datetime import datetime, timezone

import pytest

from outbound import probe, store
from outbound.constants import OUTBOUND_TENANT_ID


def _insert_scored_prospect(*, phone: str, timezone_name: str) -> str:
    result = store.upsert_outbound_prospects(
        [
            {
                "tenant_id": OUTBOUND_TENANT_ID,
                "business_name": phone,
                "trade": "hvac",
                "metro": "Phoenix",
                "phone": phone,
                "phone_normalized": phone,
                "source": "leads_db",
                "timezone": timezone_name,
                "score_tier": "a_lead",
                "total_score": 80,
                "stage": "scored",
                "raw_source": {},
            }
        ]
    )
    return result["records"][0]["id"]


def test_timezone_filter_only_includes_7pm_local(monkeypatch: pytest.MonkeyPatch) -> None:
    included = _insert_scored_prospect(phone="+16025550100", timezone_name="America/Phoenix")
    excluded = _insert_scored_prospect(phone="+13125550100", timezone_name="America/Chicago")

    monkeypatch.setattr(
        probe,
        "place_probe_call",
        lambda _prospect: {"twilio_call_sid": "CA123", "amd_status": "machine_start", "status": "completed", "ring_duration_ms": 4000, "result": "voicemail"},
    )

    result = probe.run_probe_batch(now=datetime(2026, 3, 23, 2, 15, tzinfo=timezone.utc))

    assert result["tested"] == 1
    assert store.get_outbound_prospect(included)["stage"] == "call_ready"
    assert store.get_outbound_prospect(excluded)["stage"] == "scored"


def test_map_amd_result_covers_status_values() -> None:
    assert probe.map_amd_result("human", "completed") == "answered_human"
    assert probe.map_amd_result("machine_end_beep", "completed") == "voicemail"
    assert probe.map_amd_result(None, "busy") == "busy"
    assert probe.map_amd_result(None, "no-answer") == "no_answer"
    assert probe.map_amd_result(None, "failed") == "failed"
    assert probe.map_amd_result(None, "completed") == "uncertain"


def test_twilio_error_marks_failed_and_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    _insert_scored_prospect(phone="+16025550101", timezone_name="America/Phoenix")
    _insert_scored_prospect(phone="+16025550102", timezone_name="America/Phoenix")

    calls = {"count": 0}

    def _fake_place(_prospect):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("twilio down")
        return {"twilio_call_sid": "CA124", "amd_status": "human", "status": "completed", "ring_duration_ms": 3000, "result": "answered_human"}

    monkeypatch.setattr(probe, "place_probe_call", _fake_place)

    result = probe.run_probe_batch(now=datetime(2026, 3, 23, 2, 15, tzinfo=timezone.utc))

    assert result["tested"] == 2
    assert result["failed"] == 1
    assert result["answered"] == 1


def test_uncertain_result_does_not_change_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_scored_prospect(phone="+16025550103", timezone_name="America/Phoenix")
    monkeypatch.setattr(
        probe,
        "place_probe_call",
        lambda _prospect: {"twilio_call_sid": "CA125", "amd_status": None, "status": "completed", "ring_duration_ms": 2000, "result": "uncertain"},
    )

    probe.run_probe_batch(now=datetime(2026, 3, 23, 2, 15, tzinfo=timezone.utc))

    assert store.get_outbound_prospect(prospect_id)["stage"] == "scored"
