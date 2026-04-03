from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from outbound import store
from outbound.constants import OUTBOUND_TENANT_ID
from outbound.followup import emit_followup_text


def _insert_prospect(phone: str = "+16025551234", **overrides) -> str:
    defaults = {
        "tenant_id": OUTBOUND_TENANT_ID,
        "business_name": f"Test HVAC {phone[-4:]}",
        "trade": "hvac",
        "metro": "Phoenix",
        "phone": phone,
        "phone_normalized": phone,
        "source": "test",
        "timezone": "America/Phoenix",
        "stage": "call_ready",
        "score_tier": "a_lead",
        "total_score": 80,
        "raw_source": {},
    }
    defaults.update(overrides)
    result = store.upsert_outbound_prospects([defaults])
    return result["records"][0]["id"]


def _mock_llm_and_imsg(monkeypatch: pytest.MonkeyPatch, imsg_success: bool = True) -> list:
    """Mock both LLM and imsg. Returns a list that captures sent messages."""
    sent: list = []

    monkeypatch.setattr(
        "outbound.followup.llm_completion",
        lambda **kwargs: {"text": "Hey, just tried calling. - Rashid", "status": "complete"},
    )

    def mock_send(phone, text):
        sent.append({"phone": phone, "text": text})
        if imsg_success:
            return {"success": True, "error": None}
        return {"success": False, "error": "AppleScript error"}

    monkeypatch.setattr("outbound.followup.send_imessage", mock_send)
    return sent


def test_followup_no_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_prospect(phone="+16025550001")
    sent = _mock_llm_and_imsg(monkeypatch)

    result = emit_followup_text(prospect_id=prospect_id, outcome="no_answer")
    assert result["sent"] is True
    assert len(sent) == 1
    assert sent[0]["phone"] == "+16025550001"


def test_followup_voicemail(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_prospect(phone="+16025550002")
    sent = _mock_llm_and_imsg(monkeypatch)

    result = emit_followup_text(prospect_id=prospect_id, outcome="voicemail_left")
    assert result["sent"] is True
    assert len(sent) == 1


def test_followup_interested(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_prospect(phone="+16025550003", stage="interested")
    sent = _mock_llm_and_imsg(monkeypatch)

    result = emit_followup_text(
        prospect_id=prospect_id,
        outcome="answered_interested",
        extraction_data={"buying_temperature": "warm", "objection_type": "price"},
    )
    assert result["sent"] is True
    assert len(sent) == 1


def test_followup_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_prospect(phone="+16025550004", stage="callback")
    sent = _mock_llm_and_imsg(monkeypatch)

    result = emit_followup_text(prospect_id=prospect_id, outcome="answered_callback")
    assert result["sent"] is True


def test_followup_skip_wrong_number(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_prospect(phone="+16025550005")
    sent = _mock_llm_and_imsg(monkeypatch)

    result = emit_followup_text(prospect_id=prospect_id, outcome="wrong_number")
    assert result["skipped"] is True
    assert result["reason"] == "outcome_wrong_number"
    assert len(sent) == 0


def test_followup_skip_disqualified(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_prospect(phone="+16025550006", stage="disqualified")
    sent = _mock_llm_and_imsg(monkeypatch)

    result = emit_followup_text(prospect_id=prospect_id, outcome="no_answer")
    assert result["skipped"] is True
    assert result["reason"] == "disqualified"
    assert len(sent) == 0


def test_followup_skip_do_not_message(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_prospect(phone="+16025550007")
    store.update_outbound_prospect(prospect_id, {"do_not_message": True})
    sent = _mock_llm_and_imsg(monkeypatch)

    result = emit_followup_text(prospect_id=prospect_id, outcome="no_answer")
    assert result["skipped"] is True
    assert result["reason"] == "do_not_message"
    assert len(sent) == 0


def test_followup_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_prospect(phone="+16025550008")
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    store.update_outbound_prospect(prospect_id, {"last_messaged_at": recent})
    sent = _mock_llm_and_imsg(monkeypatch)

    result = emit_followup_text(prospect_id=prospect_id, outcome="no_answer")
    assert result["skipped"] is True
    assert result["reason"] == "cooldown_72h"
    assert len(sent) == 0


def test_followup_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_prospect(phone="+16025550009")
    monkeypatch.setattr(
        "outbound.followup.llm_completion",
        lambda **kwargs: {"text": None, "status": "failed"},
    )

    result = emit_followup_text(prospect_id=prospect_id, outcome="no_answer")
    assert result["sent"] is False
    assert result["reason"] == "llm_failed"


def test_followup_imsg_failure_reverts_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_prospect(phone="+16025550010")
    _mock_llm_and_imsg(monkeypatch, imsg_success=False)

    result = emit_followup_text(prospect_id=prospect_id, outcome="no_answer")
    assert result["sent"] is False
    assert "imsg_failed" in result["reason"]

    # Verify last_messaged_at was reverted so the prospect can be retried
    prospect = store.get_outbound_prospect(prospect_id)
    assert prospect.get("last_messaged_at") is None
