"""Pipeline integration tests for the post-call background flow."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from db.local_repository import reset_local_state, _state
from voice.models import CallEndedEvent


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


def _sign_body(body: bytes, secret: str = "test-api-key") -> str:
    timestamp_ms = int(time.time() * 1000)
    message = body + str(timestamp_ms).encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"v={timestamp_ms},d={digest}"


def _realistic_payload(
    *,
    call_id: str = "ret-integration-001",
    tenant_id: str = "tenant-ace-001",
) -> dict[str, Any]:
    """A realistic Retell call-ended payload with enough transcript
    content for the REAL extraction pipeline to produce meaningful results."""
    return {
        "event": "call_ended",
        "call": {
            "call_id": call_id,
            "transcript": (
                "Agent: Thank you for calling ACE Cooling and Heating. How can I help you today? "
                "User: Hi, my name is John Smith. My AC stopped blowing cold air this morning. "
                "It's 95 degrees outside and my house is getting up to 88 degrees inside. "
                "I live at 123 Oak Street, Austin, TX 78701. "
                "Agent: I'm sorry to hear that, John. Let me get some details. "
                "How old is your AC unit? "
                "User: It's about 12 years old, it's a Carrier unit. "
                "Agent: Thank you. I'll get a technician out to you. "
                "Is there anything else I can help with? "
                "User: No, that's all. Thank you."
            ),
            "transcript_object": [
                {"role": "agent", "content": "Thank you for calling ACE Cooling and Heating."},
                {"role": "user", "content": "Hi, my name is John Smith. My AC stopped blowing cold air."},
            ],
            "call_summary": "Customer John Smith reports AC not cooling. Unit is 12-year-old Carrier. Needs technician visit at 123 Oak Street, Austin.",
            "metadata": {"tenant_id": tenant_id},
            "from_number": "+15125550101",
            "to_number": "+15125559999",
            "direction": "inbound",
            "duration_ms": 180000,
            "recording_url": "https://retell.ai/recordings/ret-integration-001.mp3",
            "disconnection_reason": "agent_hangup",
            "retell_llm_dynamic_variables": {
                "customer_name": "John Smith",
                "service_address": "123 Oak Street, Austin, TX 78701",
                "urgency_level": "Routine",
                "urgency_tier": "routine",
            },
            "tool_call_results": [],
        },
    }


def _post_call_ended(client: TestClient, payload: dict[str, Any]) -> Any:
    body = json.dumps(payload).encode()
    sig = _sign_body(body)
    return client.post(
        "/webhook/retell/call-ended",
        content=body,
        headers={
            "x-retell-signature": sig,
            "content-type": "application/json",
        },
    )


class TestPipelineIntegrationHappyPath:
    """Full pipeline: real extraction, mocked supervisor, assert record + payload schema."""

    def test_full_pipeline(self, client: TestClient) -> None:
        captured_payloads: list[dict[str, Any]] = []

        def capture_supervisor(payload: dict[str, Any]) -> dict[str, Any]:
            captured_payloads.append(payload)
            return {"guardian_gate": {"gate_passed": True, "quarantine": False, "gate_failures": []}}

        payload = _realistic_payload()

        with patch("voice.post_call_router._run_voice_supervisor", side_effect=capture_supervisor):
            response = _post_call_ended(client, payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["extraction_status"] == "pending"

        records = _state()["call_records"]
        assert len(records) == 1
        record = records[0]
        assert record["tenant_id"] == "tenant-ace-001"
        assert record["call_id"] == "ret-integration-001"
        assert record["extraction_status"] == "complete"
        assert record["extracted_fields"] is not None
        assert record["extracted_fields"].get("customer_name") == "John Smith"

        assert len(captured_payloads) == 1
        event_payload = captured_payloads[0]
        assert event_payload["tenant_id"] == "tenant-ace-001"
        assert event_payload["call_id"] == "ret-integration-001"
        assert event_payload["call_source"] == "retell"
        assert event_payload["phone_number"] == "+15125550101"
        assert event_payload["extraction_status"] == "complete"
        assert event_payload["retell_call_id"] == "ret-integration-001"
        assert event_payload["call_duration_seconds"] == 180
        assert event_payload["end_call_reason"] == "agent_hangup"
        assert event_payload["call_recording_url"] == "https://retell.ai/recordings/ret-integration-001.mp3"

        event_obj = CallEndedEvent.model_validate(event_payload)
        assert event_obj.tenant_id == "tenant-ace-001"
        assert event_obj.extraction_status == "complete"

    def test_full_pipeline_uses_phone_tenant_fallback_when_metadata_missing(self, client: TestClient) -> None:
        captured_payloads: list[dict[str, Any]] = []

        def capture_supervisor(payload: dict[str, Any]) -> dict[str, Any]:
            captured_payloads.append(payload)
            return {"guardian_gate": {"gate_passed": True, "quarantine": False, "gate_failures": []}}

        payload = _realistic_payload(call_id="ret-phone-fallback-001", tenant_id="")
        payload["call"]["metadata"] = {}
        payload["call"]["to_number"] = "+13126463816"

        with patch("voice.post_call_router._run_voice_supervisor", side_effect=capture_supervisor):
            response = _post_call_ended(client, payload)

        assert response.status_code == 200
        records = _state()["call_records"]
        assert len(records) == 1
        record = records[0]
        assert record["tenant_id"] == "e51d9ae7-9cde-4dca-a49c-4744c39240bc"
        assert record["call_id"] == "ret-phone-fallback-001"
        assert record["extraction_status"] == "complete"
        assert captured_payloads[0]["tenant_id"] == "e51d9ae7-9cde-4dca-a49c-4744c39240bc"


class TestPipelinePartialExtraction:
    """When one extraction step throws, extraction_status should be 'partial'."""

    def test_partial_extraction_on_step_failure(self, client: TestClient) -> None:
        captured_payloads: list[dict[str, Any]] = []

        def capture_supervisor(payload: dict[str, Any]) -> dict[str, Any]:
            captured_payloads.append(payload)
            return {"guardian_gate": {"gate_passed": True, "quarantine": False, "gate_failures": []}}

        payload = _realistic_payload(call_id="ret-partial-001")

        with (
            patch("voice.post_call_router._run_voice_supervisor", side_effect=capture_supervisor),
            patch("voice.extraction.pipeline.infer_hvac_issue_type", side_effect=RuntimeError("Boom")),
        ):
            response = _post_call_ended(client, payload)

        assert response.status_code == 200
        data = response.json()
        assert data["extraction_status"] == "pending"

        records = _state()["call_records"]
        assert len(records) == 1
        assert records[0]["extraction_status"] == "partial"

        assert len(captured_payloads) == 1
        event_payload = captured_payloads[0]
        assert event_payload["extraction_status"] == "partial"

        event_obj = CallEndedEvent.model_validate(event_payload)
        assert event_obj.extraction_status == "partial"


class TestPipelineDuplicate:
    """Same call_id -> second request returns 200 with status='duplicate'."""

    def test_duplicate_skips_processing(self, client: TestClient) -> None:
        payload = _realistic_payload(call_id="ret-dup-001")

        with patch(
            "voice.post_call_router._run_voice_supervisor",
            return_value={"guardian_gate": {"gate_passed": True, "quarantine": False, "gate_failures": []}},
        ):
            response1 = _post_call_ended(client, payload)
        assert response1.status_code == 200
        assert response1.json()["status"] == "ok"

        with patch("voice.post_call_router._run_voice_supervisor") as mock_supervisor:
            response2 = _post_call_ended(client, payload)
        assert response2.status_code == 200
        assert response2.json()["status"] == "duplicate"

        mock_supervisor.assert_not_called()

        records = _state()["call_records"]
        assert len(records) == 1
