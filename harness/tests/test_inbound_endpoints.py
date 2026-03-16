"""Tests for inbound pipeline harness endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from harness.server import app


def test_inbound_poll_request_valid() -> None:
    from harness.models import InboundPollRequest

    req = InboundPollRequest(tenant_id="t1")
    assert req.tenant_id == "t1"
    assert req.account_ids == []


def test_inbound_poll_request_with_accounts() -> None:
    from harness.models import InboundPollRequest

    req = InboundPollRequest(tenant_id="t1", account_ids=["a1", "a2"])
    assert len(req.account_ids) == 2


def test_inbound_process_request_valid() -> None:
    from harness.models import InboundProcessRequest

    req = InboundProcessRequest(
        tenant_id="t1",
        account_id="a1",
        message_id="msg1",
        from_addr="test@example.com",
        from_domain="example.com",
        subject="Test",
    )
    assert req.source == "organic"


def test_inbound_process_request_reply() -> None:
    from harness.models import InboundProcessRequest

    req = InboundProcessRequest(
        tenant_id="t1",
        account_id="a1",
        message_id="msg1",
        from_addr="test@example.com",
        from_domain="example.com",
        subject="Re: Test",
        source="reply",
    )
    assert req.source == "reply"


def test_inbound_poll_response() -> None:
    from harness.models import InboundPollResponse

    resp = InboundPollResponse(results=[{"message_id": "m1", "action": "high"}], fetched=1, processed=1)
    assert resp.fetched == 1


def test_inbound_process_response() -> None:
    from harness.models import InboundProcessResponse

    resp = InboundProcessResponse(
        message_id="m1",
        action="exceptional",
        total_score=92,
        stage="qualified",
        draft_generated=True,
        escalated=True,
    )
    assert resp.escalated is True


def test_inbound_poll_endpoint_dispatches_pipeline() -> None:
    client = TestClient(app)
    mocked = AsyncMock(return_value=[{"message_id": "m1", "action": "high", "stage": "qualified"}])
    with patch("inbound.pipeline.run_poll", mocked):
        response = client.post("/inbound/poll", json={"tenant_id": "t1", "account_ids": ["a1"]})
    assert response.status_code == 200
    assert response.json()["fetched"] == 1
    mocked.assert_awaited_once()


def test_inbound_process_endpoint_returns_404_when_message_missing() -> None:
    client = TestClient(app)
    with patch("harness.server.db_repository.get_inbound_message", return_value=None):
        response = client.post(
            "/inbound/process",
            json={
                "tenant_id": "t1",
                "account_id": "a1",
                "message_id": "missing",
                "from_addr": "sender@example.com",
                "from_domain": "example.com",
                "subject": "Hello",
            },
        )
    assert response.status_code == 404


def test_inbound_process_endpoint_dispatches_pipeline() -> None:
    client = TestClient(app)
    msg_record = {
        "id": "stored-msg",
        "rfc_message_id": "<abc@example.com>",
        "thread_id": "thread-1",
        "imap_uid": 11,
        "from_addr": "sender@example.com",
        "from_domain": "example.com",
        "to_addr": "team@example.com",
        "subject": "Hello",
        "received_at": "2026-03-16T10:00:00+00:00",
        "body_html": "<p>Hello</p>",
        "body_text": "Hello",
    }
    mocked = AsyncMock(
        return_value={
            "message_id": "stored-msg",
            "action": "high",
            "total_score": 82,
            "stage": "qualified",
            "draft_generated": True,
            "escalated": False,
            "auto_archived": False,
        }
    )
    with patch("harness.server.db_repository.get_inbound_message", return_value=msg_record):
        with patch("inbound.pipeline.process_message", mocked):
            response = client.post(
                "/inbound/process",
                json={
                    "tenant_id": "t1",
                    "account_id": "a1",
                    "message_id": "stored-msg",
                    "from_addr": "sender@example.com",
                    "from_domain": "example.com",
                    "subject": "Hello",
                },
            )
    assert response.status_code == 200
    assert response.json()["action"] == "high"
    mocked.assert_awaited_once()
