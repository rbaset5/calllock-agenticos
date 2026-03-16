from __future__ import annotations

import logging
from typing import Any

from inbound.config import DEFAULT_CONFIG
from inbound.imap_client import connect_imap, fetch_new_messages
from inbound.pipeline import process_message


logger = logging.getLogger(__name__)


async def backfill_account(
    tenant_id: str,
    account_id: str,
    repository: Any,
    max_messages: int = 50,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_config = config or DEFAULT_CONFIG
    backfill_config = effective_config.get("backfill", DEFAULT_CONFIG["backfill"])
    if not backfill_config.get("enabled", True):
        return {
            "account_id": account_id,
            "messages_processed": 0,
            "messages_failed": 0,
            "checkpoint_uid": 0,
        }

    checkpoint = repository.get_poll_checkpoint(tenant_id, account_id, "INBOX")
    if checkpoint is not None:
        return {
            "account_id": account_id,
            "messages_processed": 0,
            "messages_failed": 0,
            "checkpoint_uid": int(checkpoint.get("last_uid", 0)),
        }

    account = repository.get_email_account(tenant_id, account_id)
    if not account:
        logger.warning("inbound_backfill_account_missing", extra={"tenant_id": tenant_id, "account_id": account_id})
        return {
            "account_id": account_id,
            "messages_processed": 0,
            "messages_failed": 0,
            "checkpoint_uid": 0,
        }

    client = connect_imap(
        account["imap_host"],
        int(account["imap_port"]),
        account["imap_username"],
        account["imap_credential"],
        auth_type=account.get("imap_auth_type", "password"),
    )
    messages = fetch_new_messages(client, "INBOX", 0, batch_size=max_messages)

    processed = 0
    failed = 0
    max_uid = 0
    for message in messages:
        max_uid = max(max_uid, message.imap_uid)
        try:
            await process_message(message, tenant_id, repository, source="organic", config=effective_config)
            processed += 1
        except Exception:
            failed += 1
            logger.exception(
                "inbound_backfill_message_failed",
                extra={"tenant_id": tenant_id, "account_id": account_id, "imap_uid": message.imap_uid},
            )

    repository.upsert_poll_checkpoint(tenant_id, account_id, "INBOX", max_uid)
    return {
        "account_id": account_id,
        "messages_processed": processed,
        "messages_failed": failed,
        "checkpoint_uid": max_uid,
    }
