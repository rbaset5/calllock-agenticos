from __future__ import annotations

import pytest

from outbound import outcomes, store
from outbound.constants import OUTBOUND_TENANT_ID


def _insert_call_ready_prospect(phone: str) -> str:
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
                "timezone": "America/Phoenix",
                "stage": "call_ready",
                "score_tier": "a_lead",
                "total_score": 80,
                "raw_source": {},
            }
        ]
    )
    return result["records"][0]["id"]


@pytest.mark.parametrize(
    ("outcome", "expected_stage"),
    [
        ("answered_interested", "interested"),
        ("answered_not_interested", "called"),
        ("answered_callback", "callback"),
        ("voicemail_left", "called"),
        ("no_answer", "called"),
        ("gatekeeper_blocked", "called"),
    ],
)
def test_each_outcome_drives_expected_stage(monkeypatch: pytest.MonkeyPatch, outcome: str, expected_stage: str) -> None:
    prospect_id = _insert_call_ready_prospect(phone=f"+1602555{len(store.list_outbound_prospects()) + 1:04d}")
    emitted: list[str] = []
    monkeypatch.setattr(outcomes, "emit_call_outcome", lambda record: emitted.append(record["twilio_call_sid"]) or {"touchpoint_created": True, "lifecycle_created": False})

    result = outcomes.log_call_outcome(prospect_id=prospect_id, twilio_call_sid=f"CA-{outcome}", outcome=outcome)

    assert result["inserted"] is True
    assert store.get_outbound_prospect(prospect_id)["stage"] == expected_stage
    assert emitted == [f"CA-{outcome}"]


def test_callback_outcome_stores_callback_date(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_call_ready_prospect(phone="+16025550111")
    monkeypatch.setattr(outcomes, "emit_call_outcome", lambda _record: {"touchpoint_created": True, "lifecycle_created": True})

    outcomes.log_call_outcome(
        prospect_id=prospect_id,
        twilio_call_sid="CA-callback",
        outcome="answered_callback",
        callback_date="2026-03-24",
    )

    call = store.list_outbound_calls(prospect_id=prospect_id)[0]
    assert call["callback_date"] == "2026-03-24"


def test_wrong_number_disqualifies_with_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_call_ready_prospect(phone="+16025550112")
    monkeypatch.setattr(outcomes, "emit_call_outcome", lambda _record: {"touchpoint_created": True, "lifecycle_created": False})

    outcomes.log_call_outcome(prospect_id=prospect_id, twilio_call_sid="CA-wrong", outcome="wrong_number")

    prospect = store.get_outbound_prospect(prospect_id)
    assert prospect["stage"] == "disqualified"
    assert prospect["disqualification_reason"] == "wrong_number"


def test_duplicate_twilio_call_sid_skips_growth(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_call_ready_prospect(phone="+16025550113")
    calls = {"count": 0}
    monkeypatch.setattr(outcomes, "emit_call_outcome", lambda _record: calls.__setitem__("count", calls["count"] + 1) or {"touchpoint_created": True, "lifecycle_created": False})

    first = outcomes.log_call_outcome(prospect_id=prospect_id, twilio_call_sid="CA-dup", outcome="no_answer")
    second = outcomes.log_call_outcome(prospect_id=prospect_id, twilio_call_sid="CA-dup", outcome="no_answer")

    assert first["inserted"] is True
    assert second["inserted"] is False
    assert calls["count"] == 1
