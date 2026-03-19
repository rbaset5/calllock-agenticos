from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from db.local_repository import _state, reset_local_state


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_local_state()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RETELL_WEBHOOK_SECRET", "test-secret")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    from harness.server import app

    return TestClient(app)


def _sign_body(body: bytes, secret: str = "test-secret") -> tuple[str, str]:
    timestamp = str(int(time.time()))
    message = timestamp.encode() + b"." + body
    signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return signature, timestamp


def _payload(
    *,
    call_id: str = "ret-call-001",
    tenant_id: str = "tenant-ace-001",
) -> dict[str, object]:
    return {
        "call_id": call_id,
        "transcript": "Agent: Thanks for calling. User: My AC is broken.",
        "transcript_object": [],
        "call_summary": "Customer reports broken AC.",
        "custom_metadata": {"tenant_id": tenant_id},
        "from_number": "+15125550101",
        "to_number": "+15125559999",
        "direction": "inbound",
        "duration_ms": 120000,
        "recording_url": "https://retell.ai/recordings/test.mp3",
        "disconnection_reason": "agent_hangup",
        "retell_llm_dynamic_variables": {
            "customer_name": "John Smith",
            "service_address": "123 Oak St, Austin TX 78701",
        },
        "tool_call_results": [],
    }


def _post(client: TestClient, payload: dict[str, object]) -> TestClient:
    body = json.dumps(payload).encode()
    signature, timestamp = _sign_body(body)
    return client.post(
        "/webhook/retell/call-ended",
        content=body,
        headers={
            "x-retell-signature": signature,
            "x-retell-timestamp": timestamp,
            "content-type": "application/json",
        },
    )


def test_handle_call_ended_returns_200_immediately(client: TestClient) -> None:
    body = json.dumps(_payload()).encode()
    signature, timestamp = _sign_body(body)

    with patch("voice.post_call_router.BackgroundTasks.add_task") as mock_add_task:
        response = client.post(
            "/webhook/retell/call-ended",
            content=body,
            headers={
                "x-retell-signature": signature,
                "x-retell-timestamp": timestamp,
                "content-type": "application/json",
            },
        )

    assert response.status_code == 200
    assert response.json()["extraction_status"] == "pending"
    assert len(_state()["call_records"]) == 1
    assert _state()["call_records"][0]["extraction_status"] == "pending"
    mock_add_task.assert_called_once()


def test_handle_call_ended_returns_401_on_invalid_hmac(client: TestClient) -> None:
    response = client.post(
        "/webhook/retell/call-ended",
        content=json.dumps(_payload()).encode(),
        headers={
            "x-retell-signature": "bad",
            "x-retell-timestamp": str(int(time.time())),
            "content-type": "application/json",
        },
    )

    assert response.status_code == 401


def test_handle_call_ended_returns_400_on_malformed_payload(client: TestClient) -> None:
    body = b'{"call_id":'
    signature, timestamp = _sign_body(body)

    response = client.post(
        "/webhook/retell/call-ended",
        content=body,
        headers={
            "x-retell-signature": signature,
            "x-retell-timestamp": timestamp,
            "content-type": "application/json",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "Invalid payload"


def test_handle_call_ended_returns_400_on_missing_tenant_id(client: TestClient) -> None:
    response = _post(client, _payload(tenant_id=""))

    assert response.status_code == 400
    assert response.json()["error"] == "Missing tenant_id in custom_metadata"


def test_handle_call_ended_returns_duplicate_when_insert_skips(client: TestClient) -> None:
    with patch("voice.post_call_router.BackgroundTasks.add_task"):
        first = _post(client, _payload(call_id="ret-dup-001"))
        second = _post(client, _payload(call_id="ret-dup-001"))

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
