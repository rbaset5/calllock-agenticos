from __future__ import annotations

import pytest

from outbound import lifecycle


def _patch_empty_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lifecycle.store, "list_overdue_callbacks", lambda **_kwargs: [])
    monkeypatch.setattr(lifecycle.store, "list_recent_no_answer_strikes", lambda **_kwargs: [])
    monkeypatch.setattr(lifecycle.store, "list_voicemail_requeue_candidates", lambda **_kwargs: [])
    monkeypatch.setattr(lifecycle.store, "list_cooling_leads", lambda **_kwargs: [])
    monkeypatch.setattr(lifecycle.store, "list_wrong_numbers", lambda **_kwargs: [])


def test_overdue_callback_requeue(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_empty_lists(monkeypatch)
    monkeypatch.setattr(
        lifecycle.store,
        "list_overdue_callbacks",
        lambda **_kwargs: [{"prospect_id": "p1", "business_name": "Overdue HVAC"}],
    )
    monkeypatch.setattr(lifecycle.store, "update_outbound_prospect", lambda *_args, **_kwargs: {"id": "p1"})

    result = lifecycle.run_lifecycle_sweep()

    assert result["overdue_requeued"] == 1


def test_three_strike_disqualification(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_empty_lists(monkeypatch)
    monkeypatch.setattr(
        lifecycle.store,
        "list_recent_no_answer_strikes",
        lambda **_kwargs: [{"prospect_id": "p2", "business_name": "No Answer Inc", "stage": "call_ready"}],
    )
    monkeypatch.setattr(lifecycle.store, "update_outbound_prospect", lambda *_args, **_kwargs: {"id": "p2"})

    result = lifecycle.run_lifecycle_sweep()

    assert result["strikes_disqualified"] == 1


def test_voicemail_requeue(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_empty_lists(monkeypatch)
    monkeypatch.setattr(
        lifecycle.store,
        "list_voicemail_requeue_candidates",
        lambda **_kwargs: [{"prospect_id": "p3", "business_name": "Voice Mail LLC"}],
    )
    monkeypatch.setattr(lifecycle.store, "update_outbound_prospect", lambda *_args, **_kwargs: {"id": "p3"})

    result = lifecycle.run_lifecycle_sweep()

    assert result["voicemail_requeued"] == 1


def test_cooling_lead_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_empty_lists(monkeypatch)
    monkeypatch.setattr(
        lifecycle.store,
        "list_cooling_leads",
        lambda **_kwargs: [
            {
                "prospect_id": "p4",
                "business_name": "Cooling Lead",
                "phone": "+15550004444",
                "metro": "Phoenix",
                "days_since_interested": 6,
            }
        ],
    )

    result = lifecycle.run_lifecycle_sweep()

    assert len(result["cooling_alerts"]) == 1
    assert result["cooling_alerts"][0]["prospect_id"] == "p4"


def test_wrong_number_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_empty_lists(monkeypatch)
    monkeypatch.setattr(
        lifecycle.store,
        "list_wrong_numbers",
        lambda **_kwargs: [{"prospect_id": "p5", "business_name": "Wrong Number Co", "stage": "called"}],
    )
    monkeypatch.setattr(lifecycle.store, "update_outbound_prospect", lambda *_args, **_kwargs: {"id": "p5"})

    result = lifecycle.run_lifecycle_sweep()

    assert result["wrong_number_disqualified"] == 1


def test_expected_stage_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_empty_lists(monkeypatch)
    monkeypatch.setattr(
        lifecycle.store,
        "list_recent_no_answer_strikes",
        lambda **_kwargs: [{"prospect_id": "p6", "business_name": "Race Condition", "stage": "called"}],
    )
    # Simulate expected_stage mismatch no-op
    monkeypatch.setattr(lifecycle.store, "update_outbound_prospect", lambda *_args, **_kwargs: None)

    result = lifecycle.run_lifecycle_sweep()

    assert result["strikes_disqualified"] == 0


def test_warm_lead_protected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_empty_lists(monkeypatch)
    monkeypatch.setattr(
        lifecycle.store,
        "list_recent_no_answer_strikes",
        lambda **_kwargs: [{"prospect_id": "p7", "business_name": "Warm Lead", "stage": "interested"}],
    )

    called = {"count": 0}

    def _update(*_args, **_kwargs):
        called["count"] += 1
        return {"id": "p7"}

    monkeypatch.setattr(lifecycle.store, "update_outbound_prospect", _update)

    result = lifecycle.run_lifecycle_sweep()

    assert result["strikes_disqualified"] == 0
    assert called["count"] == 0
