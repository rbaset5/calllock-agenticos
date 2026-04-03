from __future__ import annotations

import pytest

from outbound import store
from outbound.constants import OUTBOUND_TENANT_ID
from outbound.reply_watcher import _on_inbound_message, _is_opt_out, _normalize_phone, start_watcher


def _insert_prospect(phone: str = "+16025551234") -> str:
    result = store.upsert_outbound_prospects(
        [
            {
                "tenant_id": OUTBOUND_TENANT_ID,
                "business_name": f"Test HVAC {phone[-4:]}",
                "trade": "hvac",
                "metro": "Phoenix",
                "phone": phone,
                "phone_normalized": phone,
                "source": "test",
                "timezone": "America/Phoenix",
                "stage": "interested",
                "score_tier": "a_lead",
                "total_score": 80,
                "raw_source": {},
            }
        ]
    )
    return result["records"][0]["id"]


def test_known_phone_logs_message_and_alerts(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_prospect(phone="+16025554001")
    alerts: list = []
    monkeypatch.setattr("outbound.reply_watcher._post_discord_alert", lambda msg: alerts.append(msg))

    _on_inbound_message({"sender": "+16025554001", "text": "Yes I'm interested, tell me more"})

    messages = store.list_prospect_messages(prospect_id=prospect_id, direction="inbound")
    assert len(messages) >= 1
    assert messages[0]["content"] == "Yes I'm interested, tell me more"
    assert len(alerts) == 1
    assert "Test HVAC 4001" in alerts[0]


def test_unknown_phone_no_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    alerts: list = []
    monkeypatch.setattr("outbound.reply_watcher._post_discord_alert", lambda msg: alerts.append(msg))

    _on_inbound_message({"sender": "+19999999999", "text": "Who is this?"})

    assert len(alerts) == 0


def test_opt_out_sets_do_not_message(monkeypatch: pytest.MonkeyPatch) -> None:
    prospect_id = _insert_prospect(phone="+16025554002")
    alerts: list = []
    monkeypatch.setattr("outbound.reply_watcher._post_discord_alert", lambda msg: alerts.append(msg))

    _on_inbound_message({"sender": "+16025554002", "text": "Please stop texting me"})

    prospect = store.get_outbound_prospect(prospect_id)
    assert prospect["do_not_message"] is True
    assert len(alerts) == 1
    assert "Opt-out" in alerts[0]


def test_opt_out_keyword_variants() -> None:
    assert _is_opt_out("STOP") is True
    assert _is_opt_out("stop") is True
    assert _is_opt_out("unsubscribe") is True
    assert _is_opt_out("don't text me") is True
    assert _is_opt_out("dont text me") is True
    assert _is_opt_out("remove me from this list") is True
    assert _is_opt_out("opt out please") is True
    assert _is_opt_out("Yes I'm interested") is False
    assert _is_opt_out("Sure, let's talk") is False


def test_singleton_protection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Second call to start_watcher returns False if already running."""
    import outbound.reply_watcher as rw

    # Simulate already running
    monkeypatch.setattr(rw, "_watcher_running", True)
    assert start_watcher() is False
