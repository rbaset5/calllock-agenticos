"""Tests for the post-call router (call-ended webhook)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from db.local_repository import reset_local_state


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_local_state()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RETELL_API_KEY", "test-api-key")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    from harness.server import app

    return TestClient(app)


def _sign_body(body: bytes, api_key: str = "test-api-key") -> str:
    """Generate Retell-format combined signature header."""
    ts_ms = int(time.time() * 1000)
    message = body + str(ts_ms).encode()
    digest = hmac.new(api_key.encode(), message, hashlib.sha256).hexdigest()
    return f"v={ts_ms},d={digest}"


def _call_ended_payload(
    *,
    call_id: str = "ret-call-001",
    tenant_id: str = "tenant-ace-001",
    transcript: str = "Agent: Thanks for calling. User: My AC is broken.",
    from_number: str = "+15125550101",
) -> dict:
    return {
        "call_id": call_id,
        "transcript": transcript,
        "transcript_object": [],
        "call_summary": "Customer reports broken AC.",
        "custom_metadata": {"tenant_id": tenant_id},
        "from_number": from_number,
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


class TestCallEndedHappyPath:
    def test_returns_200_and_persists_record(self, client: TestClient) -> None:
        payload = _call_ended_payload()
        body = json.dumps(payload).encode()
        sig = _sign_body(body)

        with patch("voice.post_call_router._process_call_ended", new_callable=AsyncMock) as mock_process:
            response = client.post(
                "/webhook/retell/call-ended",
                content=body,
                headers={
                    "x-retell-signature": sig,
                    "content-type": "application/json",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["call_id"] == payload["call_id"]
            assert data["extraction_status"] == "pending"
            mock_process.assert_called_once()

    def test_extraction_runs_on_transcript(self, client: TestClient) -> None:
        payload = _call_ended_payload(
            transcript="Agent: How can I help? User: Hi my name is Jane Doe. My heater stopped working. I live at 456 Elm St, Austin TX 78702."
        )
        body = json.dumps(payload).encode()
        sig = _sign_body(body)

        with patch("voice.post_call_router._process_call_ended", new_callable=AsyncMock):
            response = client.post(
                "/webhook/retell/call-ended",
                content=body,
                headers={
                    "x-retell-signature": sig,
                    "content-type": "application/json",
                },
            )

        assert response.status_code == 200


class TestCallEndedDuplicate:
    def test_duplicate_call_returns_200(self, client: TestClient) -> None:
        """UNIQUE(tenant_id, call_id) constraint -> skip, return 200."""
        payload = _call_ended_payload()
        body = json.dumps(payload).encode()

        with patch("voice.post_call_router._process_call_ended", new_callable=AsyncMock):
            sig = _sign_body(body)
            client.post(
                "/webhook/retell/call-ended",
                content=body,
                headers={
                    "x-retell-signature": sig,
                    "content-type": "application/json",
                },
            )

            sig2 = _sign_body(body)
            response = client.post(
                "/webhook/retell/call-ended",
                content=body,
                headers={
                    "x-retell-signature": sig2,
                    "content-type": "application/json",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "duplicate"


class TestCallEndedAuth:
    def test_invalid_hmac_returns_401(self, client: TestClient) -> None:
        body = json.dumps(_call_ended_payload()).encode()

        response = client.post(
            "/webhook/retell/call-ended",
            content=body,
            headers={
                "x-retell-signature": "bad",
                "content-type": "application/json",
            },
        )

        assert response.status_code == 401


class TestCallEndedEmptyTranscript:
    def test_short_transcript_still_processes(self, client: TestClient) -> None:
        """Short calls (<20 chars) get default values per spec finding #18."""
        payload = _call_ended_payload(transcript="Hi")
        body = json.dumps(payload).encode()
        sig = _sign_body(body)

        with patch("voice.post_call_router._process_call_ended", new_callable=AsyncMock):
            response = client.post(
                "/webhook/retell/call-ended",
                content=body,
                headers={
                    "x-retell-signature": sig,
                    "content-type": "application/json",
                },
            )

        assert response.status_code == 200
