from __future__ import annotations

import uuid

import pytest

from growth.memory.models import GrowthDuplicateError
from outbound import growth_bridge, store
from outbound.constants import OUTBOUND_TENANT_ID, OUTBOUND_UUID_NAMESPACE


def _insert_call_record() -> dict[str, str]:
    prospect = store.upsert_outbound_prospects(
        [
            {
                "tenant_id": OUTBOUND_TENANT_ID,
                "business_name": "Growth Prospect",
                "trade": "hvac",
                "metro": "Phoenix",
                "phone": "+16025550120",
                "phone_normalized": "+16025550120",
                "source": "leads_db",
                "timezone": "America/Phoenix",
                "stage": "call_ready",
                "raw_source": {},
            }
        ]
    )["records"][0]
    return store.insert_outbound_call(
        {
            "tenant_id": OUTBOUND_TENANT_ID,
            "prospect_id": prospect["id"],
            "twilio_call_sid": "CA-growth",
            "outcome": "answered_interested",
            "called_at": "2026-03-22T22:00:00+00:00",
        }
    )["record"]


def test_generates_two_distinct_deterministic_uuids() -> None:
    expected_call = uuid.uuid5(OUTBOUND_UUID_NAMESPACE, "call-CA-growth")
    expected_lifecycle = uuid.uuid5(OUTBOUND_UUID_NAMESPACE, "lifecycle-CA-growth")

    assert expected_call != expected_lifecycle
    assert expected_call == uuid.uuid5(OUTBOUND_UUID_NAMESPACE, "call-CA-growth")
    assert expected_lifecycle != uuid.uuid5(OUTBOUND_UUID_NAMESPACE, "lifecycle-CA-other")


def test_duplicate_errors_are_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _insert_call_record()
    monkeypatch.setattr(growth_bridge, "insert_touchpoint", lambda _payload: (_ for _ in ()).throw(GrowthDuplicateError("call")))
    monkeypatch.setattr(growth_bridge, "handle_lifecycle_transition", lambda _payload: (_ for _ in ()).throw(GrowthDuplicateError("lifecycle")))

    result = growth_bridge.emit_call_outcome(record)

    assert result == {"touchpoint_created": False, "lifecycle_created": False}
    assert store.list_outbound_calls()[0]["growth_memory_id"] == str(uuid.uuid5(OUTBOUND_UUID_NAMESPACE, "call-CA-growth"))


def test_interested_emits_lifecycle_but_voicemail_does_not(monkeypatch: pytest.MonkeyPatch) -> None:
    interested_record = _insert_call_record()
    payloads: list[dict[str, object]] = []
    monkeypatch.setattr(growth_bridge, "insert_touchpoint", lambda payload: payloads.append(payload) or payload)
    monkeypatch.setattr(growth_bridge, "handle_lifecycle_transition", lambda payload: payloads.append(payload) or payload)

    interested = growth_bridge.emit_call_outcome(interested_record)

    voicemail = store.insert_outbound_call(
        {
            "tenant_id": OUTBOUND_TENANT_ID,
            "prospect_id": interested_record["prospect_id"],
            "twilio_call_sid": "CA-voicemail",
            "outcome": "voicemail_left",
            "called_at": "2026-03-22T22:10:00+00:00",
        }
    )["record"]
    voicemail_payloads: list[dict[str, object]] = []
    monkeypatch.setattr(growth_bridge, "insert_touchpoint", lambda payload: voicemail_payloads.append(payload) or payload)
    monkeypatch.setattr(growth_bridge, "handle_lifecycle_transition", lambda payload: voicemail_payloads.append(payload) or payload)

    voicemail_result = growth_bridge.emit_call_outcome(voicemail)

    assert interested == {"touchpoint_created": True, "lifecycle_created": True}
    assert len(payloads) == 2
    assert voicemail_result == {"touchpoint_created": True, "lifecycle_created": False}
    assert len(voicemail_payloads) == 1
