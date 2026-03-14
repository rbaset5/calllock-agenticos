from __future__ import annotations

from growth.memory import repository as growth_repository


def test_duplicate_touchpoint_is_deduped_once(client, auth_headers) -> None:
    payload = {
        "touchpoint_id": "00000000-0000-0000-0000-00000000a101",
        "tenant_id": "tenant-alpha",
        "prospect_id": "00000000-0000-0000-0000-00000000b101",
        "touchpoint_type": "email_sent",
        "channel": "cold_email",
        "source_component": "growth.tests",
        "source_version": "test",
    }

    first = client.post("/growth/handle-touchpoint", headers=auth_headers, json=payload)
    second = client.post("/growth/handle-touchpoint", headers=auth_headers, json=payload)

    assert first.status_code == 200
    assert first.json()["status"] == "inserted"
    assert second.status_code == 200
    assert second.json()["status"] == "deduped"
    assert len(growth_repository.list_touchpoints(tenant_id="tenant-alpha")) == 1


def test_duplicate_belief_event_is_deduped_once(client, auth_headers) -> None:
    payload = {
        "tenant_id": "tenant-alpha",
        "source_touchpoint_id": "00000000-0000-0000-0000-00000000a111",
        "prospect_id": "00000000-0000-0000-0000-00000000b111",
        "touchpoint_type": "email_replied",
        "belief_shift": "up",
        "confidence": 0.7,
        "signal_map_version": "v1",
        "source_version": "test",
    }

    first = client.post("/growth/handle-belief", headers=auth_headers, json=payload)
    second = client.post("/growth/handle-belief", headers=auth_headers, json=payload)

    assert first.status_code == 200
    assert first.json()["status"] == "inserted"
    assert second.status_code == 200
    assert second.json()["status"] == "deduped"
    assert len(growth_repository.list_belief_events(tenant_id="tenant-alpha")) == 1
