from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from inbound.backfill import backfill_account
from inbound.types import ParsedMessage


def _message(uid: int) -> ParsedMessage:
    return ParsedMessage(
        rfc_message_id=f"<msg-{uid}@example.com>",
        thread_id=f"<thread-{uid}@example.com>",
        imap_uid=uid,
        from_addr="owner@example.com",
        from_domain="example.com",
        to_addr="sales@calllock.test",
        subject="Need help",
        received_at=datetime.now(timezone.utc),
        body_html="<p>Hello</p>",
        body_text="Hello",
    )


@pytest.mark.asyncio
async def test_backfill_happy_path() -> None:
    repository = MagicMock()
    repository.get_poll_checkpoint.return_value = None
    repository.get_email_account.return_value = {
        "imap_host": "imap.example.com",
        "imap_port": 993,
        "imap_username": "owner",
        "imap_credential": "secret",
        "imap_auth_type": "password",
    }
    with patch("inbound.backfill.connect_imap", return_value=object()), patch(
        "inbound.backfill.fetch_new_messages",
        return_value=[_message(1), _message(2)],
    ), patch(
        "inbound.backfill.process_message",
        new=AsyncMock(return_value={"message_id": "msg"}),
    ):
        result = await backfill_account("tenant-1", "acct-1", repository, max_messages=50)

    assert result["messages_processed"] == 2
    assert result["messages_failed"] == 0
    assert result["checkpoint_uid"] == 2


@pytest.mark.asyncio
async def test_backfill_disabled() -> None:
    repository = MagicMock()

    result = await backfill_account("tenant-1", "acct-1", repository, config={"backfill": {"enabled": False}})

    assert result == {"account_id": "acct-1", "messages_processed": 0, "messages_failed": 0, "checkpoint_uid": 0}


@pytest.mark.asyncio
async def test_backfill_already_exists() -> None:
    repository = MagicMock()
    repository.get_poll_checkpoint.return_value = {"last_uid": 10}

    result = await backfill_account("tenant-1", "acct-1", repository)

    assert result["checkpoint_uid"] == 10
    repository.get_email_account.assert_not_called()


@pytest.mark.asyncio
async def test_backfill_account_not_found() -> None:
    repository = MagicMock()
    repository.get_poll_checkpoint.return_value = None
    repository.get_email_account.return_value = None

    result = await backfill_account("tenant-1", "acct-1", repository)

    assert result["messages_processed"] == 0
    assert result["checkpoint_uid"] == 0


@pytest.mark.asyncio
async def test_backfill_partial_failure() -> None:
    repository = MagicMock()
    repository.get_poll_checkpoint.return_value = None
    repository.get_email_account.return_value = {
        "imap_host": "imap.example.com",
        "imap_port": 993,
        "imap_username": "owner",
        "imap_credential": "secret",
        "imap_auth_type": "password",
    }
    with patch("inbound.backfill.connect_imap", return_value=object()), patch(
        "inbound.backfill.fetch_new_messages",
        return_value=[_message(1), _message(2)],
    ), patch(
        "inbound.backfill.process_message",
        new=AsyncMock(side_effect=[{"message_id": "ok"}, RuntimeError("boom")]),
    ):
        result = await backfill_account("tenant-1", "acct-1", repository)

    assert result["messages_processed"] == 1
    assert result["messages_failed"] == 1
    assert result["checkpoint_uid"] == 2
