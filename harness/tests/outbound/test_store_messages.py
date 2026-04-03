from __future__ import annotations

from outbound import store
from outbound.constants import OUTBOUND_TENANT_ID


def _setup_prospect() -> str:
    result = store.upsert_outbound_prospects(
        [
            {
                "tenant_id": OUTBOUND_TENANT_ID,
                "business_name": "Test HVAC Co",
                "trade": "hvac",
                "metro": "Phoenix",
                "phone": "+16025559999",
                "phone_normalized": "+16025559999",
                "source": "test",
                "timezone": "America/Phoenix",
                "stage": "call_ready",
                "score_tier": "a_lead",
                "total_score": 80,
                "raw_source": {},
            }
        ]
    )
    return result["records"][0]["id"]


def test_insert_and_list_prospect_message() -> None:
    prospect_id = _setup_prospect()

    msg = store.insert_prospect_message(
        {
            "tenant_id": OUTBOUND_TENANT_ID,
            "prospect_id": prospect_id,
            "direction": "outbound",
            "content": "Hey, just tried calling you! - Rashid",
            "outcome_trigger": "no_answer",
            "status": "sent",
            "phone_normalized": "+16025559999",
        }
    )

    assert msg["id"]
    assert msg["direction"] == "outbound"
    assert msg["status"] == "sent"

    messages = store.list_prospect_messages(prospect_id=prospect_id)
    assert len(messages) >= 1
    assert any(m["id"] == msg["id"] for m in messages)


def test_list_prospect_messages_by_direction() -> None:
    prospect_id = _setup_prospect()

    store.insert_prospect_message(
        {
            "tenant_id": OUTBOUND_TENANT_ID,
            "prospect_id": prospect_id,
            "direction": "outbound",
            "content": "outbound text",
            "status": "sent",
            "phone_normalized": "+16025559999",
        }
    )
    store.insert_prospect_message(
        {
            "tenant_id": OUTBOUND_TENANT_ID,
            "prospect_id": prospect_id,
            "direction": "inbound",
            "content": "inbound reply",
            "status": "received",
            "phone_normalized": "+16025559999",
        }
    )

    outbound = store.list_prospect_messages(prospect_id=prospect_id, direction="outbound")
    inbound = store.list_prospect_messages(prospect_id=prospect_id, direction="inbound")
    assert all(m["direction"] == "outbound" for m in outbound)
    assert all(m["direction"] == "inbound" for m in inbound)


def test_update_prospect_message() -> None:
    prospect_id = _setup_prospect()

    msg = store.insert_prospect_message(
        {
            "tenant_id": OUTBOUND_TENANT_ID,
            "prospect_id": prospect_id,
            "direction": "outbound",
            "content": "test",
            "status": "draft",
            "phone_normalized": "+16025559999",
        }
    )

    updated = store.update_prospect_message(msg["id"], {"status": "sent"})
    assert updated is not None
    assert updated["status"] == "sent"
