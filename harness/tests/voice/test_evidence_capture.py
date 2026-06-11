"""Tests for Retell production evidence capture."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from db.local_repository import _state
from voice.production.evidence import hash_payload, record_event, record_tool_call


def _sign_body(body: bytes, secret: str = "test-api-key") -> str:
    timestamp_ms = int(time.time() * 1000)
    message = body + str(timestamp_ms).encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"v={timestamp_ms},d={digest}"


def test_hash_payload_is_stable_for_dict_order() -> None:
    assert hash_payload({"b": 2, "a": {"d": 4, "c": 3}}) == hash_payload(
        {"a": {"c": 3, "d": 4}, "b": 2}
    )


def test_record_event_persists_normalized_event() -> None:
    event = record_event(
        tenant_id="tenant-ace-001",
        call_id="call-001",
        retell_call_id="ret-001",
        event_type="call_ended",
        payload={"call_id": "ret-001"},
    )

    assert event["payload_hash"] == hash_payload({"call_id": "ret-001"})
    rows = _state()["voice_call_events"]
    assert len(rows) == 1
    assert rows[0]["event_type"] == "call_ended"


def test_record_tool_call_persists_normalized_tool_record() -> None:
    record = record_tool_call(
        tenant_id="tenant-ace-001",
        call_id="call-001",
        retell_call_id="ret-001",
        tool_name="lookup_caller",
        request_payload={"args": {"phone_number": "+15125550101"}},
        response_payload={"found": False},
        status="success",
        latency_ms=9,
    )

    assert record["tool_name"] == "lookup_caller"
    assert _state()["voice_tool_calls"][0]["latency_ms"] == 9


def test_inbound_webhook_records_event(monkeypatch) -> None:
    monkeypatch.setenv("RETELL_API_KEY", "test-api-key")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    from harness.server import app

    client = TestClient(app)
    body = json.dumps({"agent_id": "agent-1", "to_number": "+13126463816"}).encode()

    response = client.post(
        "/webhook/retell/inbound",
        content=body,
        headers={"x-retell-signature": _sign_body(body), "content-type": "application/json"},
    )

    assert response.status_code == 200
    rows = _state()["voice_call_events"]
    assert len(rows) == 1
    assert rows[0]["event_type"] == "inbound"


def test_tool_endpoint_records_tool_call_and_events(monkeypatch) -> None:
    monkeypatch.setenv("RETELL_API_KEY", "test-api-key")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    from harness.server import app

    client = TestClient(app)
    body = json.dumps(
        {
            "name": "lookup_caller",
            "args": {"phone_number": "+15125550101"},
            "call": {"call_id": "ret-tool-001", "metadata": {"tenant_id": "tenant-ace-001"}},
        }
    ).encode()

    with patch("voice.router.lookup_caller", return_value={"found": False, "jobs": [], "calls": [], "bookings": []}):
        response = client.post(
            "/webhook/retell/lookup_caller",
            content=body,
            headers={"x-retell-signature": _sign_body(body), "content-type": "application/json"},
        )

    assert response.status_code == 200
    assert _state()["voice_tool_calls"][0]["tool_name"] == "lookup_caller"
    event_types = [row["event_type"] for row in _state()["voice_call_events"]]
    assert event_types == ["tool_call", "tool_result"]


def test_create_callback_endpoint_records_tool_call_and_events(monkeypatch) -> None:
    monkeypatch.setenv("RETELL_API_KEY", "test-api-key")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    from harness.server import app

    client = TestClient(app)
    body = json.dumps(
        {
            "name": "create_callback_request",
            "args": {
                "caller_phone": "+15125550101",
                "reason": "AC not cooling",
                "callback_minutes": 30,
            },
            "call": {"call_id": "ret-callback-001", "metadata": {"tenant_id": "tenant-ace-001"}},
        }
    ).encode()

    response = client.post(
        "/webhook/retell/create_callback",
        content=body,
        headers={"x-retell-signature": _sign_body(body), "content-type": "application/json"},
    )

    assert response.status_code == 200
    assert _state()["voice_tool_calls"][0]["tool_name"] == "create_callback"
    event_types = [row["event_type"] for row in _state()["voice_call_events"]]
    assert event_types == ["tool_call", "tool_result"]


def test_sales_lead_endpoint_records_tool_call_and_events(monkeypatch) -> None:
    monkeypatch.setenv("RETELL_API_KEY", "test-api-key")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    from harness.server import app

    client = TestClient(app)
    body = json.dumps(
        {
            "name": "send_sales_lead_alert",
            "args": {
                "equipment": "Central AC",
                "customer_name": "John Smith",
                "customer_phone": "+15125550101",
                "address": "123 Oak St",
            },
            "call": {"call_id": "ret-sales-001", "metadata": {"tenant_id": "tenant-ace-001"}},
        }
    ).encode()

    response = client.post(
        "/webhook/retell/send_sales_lead_alert",
        content=body,
        headers={"x-retell-signature": _sign_body(body), "content-type": "application/json"},
    )

    assert response.status_code == 200
    assert _state()["voice_tool_calls"][0]["tool_name"] == "send_sales_lead_alert"
    event_types = [row["event_type"] for row in _state()["voice_call_events"]]
    assert event_types == ["tool_call", "tool_result"]
