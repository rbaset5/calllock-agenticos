from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
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


def _run(coro):
    return asyncio.run(coro)


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
    assert client._send_log == {}


def test_client_init_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INSTANTLY_API_KEY", "env-key")
    monkeypatch.setenv("INSTANTLY_BASE_URL", "https://instantly.example/api/")

    client = InstantlyClient()

    assert client.api_key == "env-key"
    assert client.base_url == "https://instantly.example/api"


def test_client_init_no_api_key_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("INSTANTLY_API_KEY", raising=False)
    monkeypatch.delenv("INSTANTLY_BASE_URL", raising=False)

    with caplog.at_level("WARNING"):
        client = InstantlyClient()

    assert client.api_key == ""
    assert any(record.message == "instantly_no_api_key" for record in caplog.records)


def test_rate_limit_under_threshold() -> None:
    client = InstantlyClient(api_key="test-key", rate_limit_per_hour=2)
    client._send_log["acct-1"] = [1.0]

    with patch("integrations.instantly.time.time", return_value=3600.0):
        client._check_rate_limit("acct-1")


def test_rate_limit_at_threshold() -> None:
    client = InstantlyClient(api_key="test-key", rate_limit_per_hour=2)
    client._send_log["acct-1"] = [100.0, 200.0]

    with patch("integrations.instantly.time.time", return_value=1000.0):
        with pytest.raises(InstantlyRateLimitError):
            client._check_rate_limit("acct-1")


def test_rate_limit_old_entries_expire() -> None:
    client = InstantlyClient(api_key="test-key", rate_limit_per_hour=2)
    now = 10_000.0
    client._send_log["acct-1"] = [now - 7200.0, now - 10.0]

    with patch("integrations.instantly.time.time", return_value=now):
        client._check_rate_limit("acct-1")

    assert client._send_log["acct-1"] == [now - 10.0]


def test_send_happy_path() -> None:
    client = InstantlyClient(api_key="test-key")
    client.get_warmup_status = AsyncMock(return_value={"score": 90})
    client.check_reputation = AsyncMock(
        return_value={"bounce_rate": 0.01, "complaint_rate": 0.001}
    )
    client.get_send_log = AsyncMock(return_value=[])

    with patch.object(client, "_request", new_callable=AsyncMock) as request_mock:
        request_mock.return_value = {"id": "send-1", "status": "queued"}
        result = _run(
            client.send(
                from_email="owner@calllock.test",
                to_email="lead@example.com",
                subject="Hello",
                body="World",
                account_id="acct-1",
                campaign_id="camp-1",
                reply_to_message_id="<msg-1>",
                variables={"name": "Lead"},
            )
        )

    assert result == {"id": "send-1", "status": "queued"}
    client.get_warmup_status.assert_awaited_once_with("acct-1")
    client.check_reputation.assert_awaited_once_with("acct-1")
    client.get_send_log.assert_awaited_once_with("acct-1")
    request_mock.assert_awaited_once_with(
        "POST",
        "/email/send",
        json_body={
            "from": "owner@calllock.test",
            "to": ["lead@example.com"],
            "subject": "Hello",
            "body": "World",
            "campaign_id": "camp-1",
            "reply_to_message_id": "<msg-1>",
            "variables": {"name": "Lead"},
        },
    )
    assert len(client._send_log["acct-1"]) == 1


def test_send_warmup_too_low() -> None:
    client = InstantlyClient(api_key="test-key")
    client.get_warmup_status = AsyncMock(return_value={"score": 50})
    client.check_reputation = AsyncMock()
    client.get_send_log = AsyncMock()

    with patch.object(client, "_request", new_callable=AsyncMock) as request_mock:
        with pytest.raises(InstantlyWarmupError):
            _run(
                client.send(
                    from_email="owner@calllock.test",
                    to_email="lead@example.com",
                    subject="Hello",
                    body="World",
                    account_id="acct-1",
                )
            )

    request_mock.assert_not_awaited()
    client.check_reputation.assert_not_awaited()
    client.get_send_log.assert_not_awaited()


def test_send_bounce_rate_too_high() -> None:
    client = InstantlyClient(api_key="test-key")
    client.get_warmup_status = AsyncMock(return_value={"score": 90})
    client.check_reputation = AsyncMock(
        return_value={"bounce_rate": 0.06, "complaint_rate": 0.0}
    )
    client.get_send_log = AsyncMock()

    with patch.object(client, "_request", new_callable=AsyncMock) as request_mock:
        with pytest.raises(InstantlyReputationError):
            _run(
                client.send(
                    from_email="owner@calllock.test",
                    to_email="lead@example.com",
                    subject="Hello",
                    body="World",
                    account_id="acct-1",
                )
            )

    request_mock.assert_not_awaited()
    client.get_send_log.assert_not_awaited()


def test_send_complaint_rate_too_high() -> None:
    client = InstantlyClient(api_key="test-key")
    client.get_warmup_status = AsyncMock(return_value={"score": 90})
    client.check_reputation = AsyncMock(
        return_value={"bounce_rate": 0.01, "complaint_rate": 0.02}
    )
    client.get_send_log = AsyncMock()

    with patch.object(client, "_request", new_callable=AsyncMock) as request_mock:
        with pytest.raises(InstantlyReputationError):
            _run(
                client.send(
                    from_email="owner@calllock.test",
                    to_email="lead@example.com",
                    subject="Hello",
                    body="World",
                    account_id="acct-1",
                )
            )

    request_mock.assert_not_awaited()
    client.get_send_log.assert_not_awaited()


def test_send_skip_guardrails() -> None:
    client = InstantlyClient(api_key="test-key")
    client.get_warmup_status = AsyncMock()
    client.check_reputation = AsyncMock()
    client.get_send_log = AsyncMock()

    with patch.object(client, "_request", new_callable=AsyncMock) as request_mock:
        request_mock.return_value = {"id": "send-1"}
        result = _run(
            client.send(
                from_email="owner@calllock.test",
                to_email="lead@example.com",
                subject="Hello",
                body="World",
                account_id="acct-1",
                skip_guardrails=True,
            )
        )

    assert result == {"id": "send-1"}
    client.get_warmup_status.assert_not_awaited()
    client.check_reputation.assert_not_awaited()
    client.get_send_log.assert_not_awaited()


def test_check_replies_happy_path() -> None:
    client = InstantlyClient(api_key="test-key")

    with patch.object(client, "_request", new_callable=AsyncMock) as request_mock:
        request_mock.return_value = {
            "data": [
                {
                    "from": "lead@example.com",
                    "to": "owner@calllock.test",
                    "subject": "Re: Hello",
                    "body": "Interested",
                    "received_at": "2026-03-16T10:00:00Z",
                }
            ]
        }
        replies = _run(
            client.check_replies(
                "camp-1",
                email="lead@example.com",
                since="2026-03-15T00:00:00Z",
            )
        )

    assert replies[0]["from"] == "lead@example.com"
    request_mock.assert_awaited_once_with(
        "GET",
        "/email/replies",
        params={
            "campaign_id": "camp-1",
            "email": "lead@example.com",
            "since": "2026-03-15T00:00:00Z",
        },
    )


def test_get_send_log_happy_path() -> None:
    client = InstantlyClient(api_key="test-key")

    with patch.object(client, "_request", new_callable=AsyncMock) as request_mock:
        request_mock.return_value = {
            "data": [{"to": "lead@example.com", "sent_at": "2026-03-16T10:00:00Z"}]
        }
        send_log = _run(
            client.get_send_log(
                "acct-1",
                since="2026-03-15T00:00:00Z",
                limit=10,
            )
        )

    assert send_log == [{"to": "lead@example.com", "sent_at": "2026-03-16T10:00:00Z"}]
    request_mock.assert_awaited_once_with(
        "GET",
        "/email/send-log",
        params={"email": "acct-1", "limit": "10", "since": "2026-03-15T00:00:00Z"},
    )


def test_get_warmup_status() -> None:
    client = InstantlyClient(api_key="test-key")

    with patch.object(client, "_request", new_callable=AsyncMock) as request_mock:
        request_mock.return_value = {
            "score": 82,
            "status": "warmed",
            "emails_sent_today": 12,
            "daily_limit": 40,
        }
        result = _run(client.get_warmup_status("acct-1"))

    assert result["score"] == 82
    request_mock.assert_awaited_once_with(
        "GET",
        "/account/warmup/status",
        params={"email": "acct-1"},
    )


def test_check_reputation() -> None:
    client = InstantlyClient(api_key="test-key")

    with patch.object(client, "_request", new_callable=AsyncMock) as request_mock:
        request_mock.return_value = {
            "bounce_rate": 0.01,
            "complaint_rate": 0.001,
            "delivery_rate": 0.98,
            "domain_health": "good",
        }
        result = _run(client.check_reputation("acct-1"))

    assert result["domain_health"] == "good"
    request_mock.assert_awaited_once_with(
        "GET",
        "/account/reputation",
        params={"email": "acct-1"},
    )


def test_dedup_within_window() -> None:
    client = InstantlyClient(api_key="test-key", dedup_window_hours=72)
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace(
        "+00:00", "Z"
    )

    with pytest.raises(InstantlyDedupError):
        client._check_dedup(
            "acct-1",
            "lead@example.com",
            [{"to": "lead@example.com", "sent_at": recent}],
        )


def test_dedup_outside_window() -> None:
    client = InstantlyClient(api_key="test-key", dedup_window_hours=72)
    old = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat().replace(
        "+00:00", "Z"
    )

    client._check_dedup(
        "acct-1",
        "lead@example.com",
        [{"to": "lead@example.com", "sent_at": old}],
    )


def test_request_http_error() -> None:
    client = InstantlyClient(api_key="test-key")
    http_error = HTTPError(
        url="https://api.instantly.ai/api/v1/email/send",
        code=500,
        msg="Server Error",
        hdrs=None,
        fp=BytesIO(b'{"error":"boom"}'),
    )

    with patch("urllib.request.urlopen", side_effect=http_error):
        with pytest.raises(InstantlyError, match="Instantly API POST /email/send failed"):
            _run(client._request("POST", "/email/send", json_body={"subject": "Hello"}))


def test_request_connection_error() -> None:
    client = InstantlyClient(api_key="test-key")

    with patch("urllib.request.urlopen", side_effect=URLError("down")):
        with pytest.raises(InstantlyError, match="Instantly API connection error"):
            _run(client._request("GET", "/email/replies"))
