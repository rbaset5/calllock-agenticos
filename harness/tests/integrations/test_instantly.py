from __future__ import annotations

import asyncio
import io
import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from urllib.error import HTTPError, URLError

import pytest

from integrations.instantly import (
    DEFAULT_BASE_URL,
    DEFAULT_DEDUP_WINDOW_HOURS,
    DEFAULT_MAX_BOUNCE_RATE,
    DEFAULT_MAX_COMPLAINT_RATE,
    DEFAULT_MIN_WARMUP_SCORE,
    DEFAULT_RATE_LIMIT_PER_ACCOUNT_PER_HOUR,
    InstantlyClient,
    InstantlyDedupError,
    InstantlyError,
    InstantlyRateLimitError,
    InstantlyReputationError,
    InstantlyWarmupError,
)


def test_client_init_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INSTANTLY_API_KEY", raising=False)
    monkeypatch.delenv("INSTANTLY_BASE_URL", raising=False)

    client = InstantlyClient(api_key="test-key")

    assert client.api_key == "test-key"
    assert client.base_url == DEFAULT_BASE_URL
    assert client.rate_limit_per_hour == DEFAULT_RATE_LIMIT_PER_ACCOUNT_PER_HOUR
    assert client.min_warmup_score == DEFAULT_MIN_WARMUP_SCORE
    assert client.max_bounce_rate == DEFAULT_MAX_BOUNCE_RATE
    assert client.max_complaint_rate == DEFAULT_MAX_COMPLAINT_RATE
    assert client.dedup_window_hours == DEFAULT_DEDUP_WINDOW_HOURS


def test_client_init_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INSTANTLY_API_KEY", "env-key")
    monkeypatch.setenv("INSTANTLY_BASE_URL", "https://example.com/api/")

    client = InstantlyClient()

    assert client.api_key == "env-key"
    assert client.base_url == "https://example.com/api"


def test_client_init_no_api_key_warns(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.delenv("INSTANTLY_API_KEY", raising=False)
    monkeypatch.delenv("INSTANTLY_BASE_URL", raising=False)

    with caplog.at_level(logging.WARNING, logger="integrations.instantly"):
        InstantlyClient()

    assert "instantly_no_api_key" in caplog.text


def test_rate_limit_under_threshold() -> None:
    client = InstantlyClient(api_key="test", rate_limit_per_hour=2)
    client._send_log["acct-1"] = [1.0]

    client._check_rate_limit("acct-1")


def test_rate_limit_at_threshold() -> None:
    client = InstantlyClient(api_key="test", rate_limit_per_hour=2)
    now = datetime.now(timezone.utc).timestamp()
    client._send_log["acct-1"] = [now - 60, now - 30]

    with pytest.raises(InstantlyRateLimitError):
        client._check_rate_limit("acct-1")


def test_rate_limit_old_entries_expire() -> None:
    client = InstantlyClient(api_key="test", rate_limit_per_hour=1)
    now = datetime.now(timezone.utc).timestamp()
    client._send_log["acct-1"] = [now - 4000]

    client._check_rate_limit("acct-1")

    assert client._send_log["acct-1"] == []


def test_send_happy_path() -> None:
    client = InstantlyClient(api_key="test")
    with patch.object(client, "get_warmup_status", new=AsyncMock(return_value={"score": 90})), patch.object(
        client,
        "check_reputation",
        new=AsyncMock(return_value={"bounce_rate": 0.01, "complaint_rate": 0.0}),
    ), patch.object(client, "get_send_log", new=AsyncMock(return_value=[])), patch.object(
        client,
        "_request",
        new=AsyncMock(return_value={"id": "send-1", "status": "queued"}),
    ) as request_mock:
        result = asyncio.run(
            client.send(
                from_email="from@example.com",
                to_email="to@example.com",
                subject="Hello",
                body="Body",
                account_id="acct-1",
                campaign_id="camp-1",
            )
        )

    assert result["id"] == "send-1"
    assert len(client._send_log["acct-1"]) == 1
    request_mock.assert_awaited_once()


def test_send_warmup_too_low() -> None:
    client = InstantlyClient(api_key="test")
    with patch.object(client, "get_warmup_status", new=AsyncMock(return_value={"score": 50})):
        with pytest.raises(InstantlyWarmupError):
            asyncio.run(
                client.send(
                    from_email="from@example.com",
                    to_email="to@example.com",
                    subject="Hello",
                    body="Body",
                    account_id="acct-1",
                )
            )


def test_send_bounce_rate_too_high() -> None:
    client = InstantlyClient(api_key="test")
    with patch.object(client, "get_warmup_status", new=AsyncMock(return_value={"score": 90})), patch.object(
        client,
        "check_reputation",
        new=AsyncMock(return_value={"bounce_rate": 0.06, "complaint_rate": 0.0}),
    ):
        with pytest.raises(InstantlyReputationError):
            asyncio.run(
                client.send(
                    from_email="from@example.com",
                    to_email="to@example.com",
                    subject="Hello",
                    body="Body",
                    account_id="acct-1",
                )
            )


def test_send_complaint_rate_too_high() -> None:
    client = InstantlyClient(api_key="test")
    with patch.object(client, "get_warmup_status", new=AsyncMock(return_value={"score": 90})), patch.object(
        client,
        "check_reputation",
        new=AsyncMock(return_value={"bounce_rate": 0.01, "complaint_rate": 0.02}),
    ):
        with pytest.raises(InstantlyReputationError):
            asyncio.run(
                client.send(
                    from_email="from@example.com",
                    to_email="to@example.com",
                    subject="Hello",
                    body="Body",
                    account_id="acct-1",
                )
            )


def test_send_skip_guardrails() -> None:
    client = InstantlyClient(api_key="test")
    with patch.object(client, "get_warmup_status", new=AsyncMock()) as warmup_mock, patch.object(
        client,
        "check_reputation",
        new=AsyncMock(),
    ) as reputation_mock, patch.object(client, "get_send_log", new=AsyncMock()) as send_log_mock, patch.object(
        client,
        "_request",
        new=AsyncMock(return_value={"id": "send-1"}),
    ):
        result = asyncio.run(
            client.send(
                from_email="from@example.com",
                to_email="to@example.com",
                subject="Hello",
                body="Body",
                account_id="acct-1",
                skip_guardrails=True,
            )
        )

    assert result["id"] == "send-1"
    warmup_mock.assert_not_awaited()
    reputation_mock.assert_not_awaited()
    send_log_mock.assert_not_awaited()


def test_check_replies_happy_path() -> None:
    client = InstantlyClient(api_key="test")
    with patch.object(client, "_request", new=AsyncMock(return_value={"data": [{"from": "a@example.com"}]})):
        replies = asyncio.run(client.check_replies("camp-1", email="lead@example.com"))

    assert replies == [{"from": "a@example.com"}]


def test_get_send_log_happy_path() -> None:
    client = InstantlyClient(api_key="test")
    with patch.object(client, "_request", new=AsyncMock(return_value={"data": [{"to": "lead@example.com"}]})):
        send_log = asyncio.run(client.get_send_log("acct-1"))

    assert send_log == [{"to": "lead@example.com"}]


def test_get_warmup_status() -> None:
    client = InstantlyClient(api_key="test")
    with patch.object(client, "_request", new=AsyncMock(return_value={"score": 88})) as request_mock:
        result = asyncio.run(client.get_warmup_status("acct-1"))

    assert result["score"] == 88
    request_mock.assert_awaited_once_with("GET", "/account/warmup/status", params={"email": "acct-1"})


def test_check_reputation() -> None:
    client = InstantlyClient(api_key="test")
    with patch.object(client, "_request", new=AsyncMock(return_value={"bounce_rate": 0.01})) as request_mock:
        result = asyncio.run(client.check_reputation("acct-1"))

    assert result["bounce_rate"] == 0.01
    request_mock.assert_awaited_once_with("GET", "/account/reputation", params={"email": "acct-1"})


def test_dedup_within_window() -> None:
    client = InstantlyClient(api_key="test", dedup_window_hours=72)
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    send_log = [{"to": "lead@example.com", "sent_at": recent.isoformat()}]

    with pytest.raises(InstantlyDedupError):
        client._check_dedup("acct-1", "lead@example.com", send_log)


def test_dedup_outside_window() -> None:
    client = InstantlyClient(api_key="test", dedup_window_hours=72)
    old = datetime.now(timezone.utc) - timedelta(hours=100)
    send_log = [{"to": "lead@example.com", "sent_at": old.isoformat()}]

    client._check_dedup("acct-1", "lead@example.com", send_log)


def test_request_http_error() -> None:
    client = InstantlyClient(api_key="test")
    error_body = io.BytesIO(b'{"error":"bad request"}')
    exc = HTTPError(
        url="https://example.com",
        code=400,
        msg="Bad Request",
        hdrs=None,
        fp=error_body,
    )
    with patch("urllib.request.urlopen", side_effect=exc):
        with pytest.raises(InstantlyError):
            asyncio.run(client._request("GET", "/email/replies"))


def test_request_connection_error() -> None:
    client = InstantlyClient(api_key="test")
    with patch("urllib.request.urlopen", side_effect=URLError("down")):
        with pytest.raises(InstantlyError):
            asyncio.run(client._request("GET", "/email/replies"))


def test_request_success() -> None:
    client = InstantlyClient(api_key="test")

    class _Response:
        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"ok": True}).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=_Response()):
        result = asyncio.run(client._request("GET", "/email/replies", params={"campaign_id": "camp-1"}))

    assert result == {"ok": True}
