from __future__ import annotations

from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default
from email.utils import parseaddr, parsedate_to_datetime
import logging
from typing import Any

try:
    from imapclient import IMAPClient
except Exception:  # pragma: no cover
    IMAPClient = None  # type: ignore[assignment]

from inbound.quarantine import run_full_quarantine
from inbound.types import ParsedMessage


logger = logging.getLogger(__name__)


def connect_imap(host: str, port: int, username: str, credential: str, auth_type: str = "password") -> IMAPClient:
    if IMAPClient is None:
        raise RuntimeError("imapclient is required for IMAP access")
    client = IMAPClient(host, port=port, ssl=True)
    if auth_type == "oauth2":
        client.oauth2_login(username, credential)
    else:
        client.login(username, credential)
    return client


def _decode_message_bytes(payload: bytes) -> Any:
    return BytesParser(policy=default).parsebytes(payload)


def _extract_body_parts(message: Any) -> tuple[str, str]:
    html_parts: list[str] = []
    text_parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                continue
            content_type = part.get_content_type()
            try:
                content = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                content = payload.decode(charset, errors="replace")
            if not isinstance(content, str):
                continue
            if content_type == "text/html":
                html_parts.append(content)
            elif content_type == "text/plain":
                text_parts.append(content)
    else:
        content = message.get_content()
        if isinstance(content, str):
            if message.get_content_type() == "text/html":
                html_parts.append(content)
            else:
                text_parts.append(content)
    return ("\n".join(html_parts), "\n".join(text_parts))


def _parse_received_at(date_header: str | None) -> datetime:
    if not date_header:
        return datetime.now(timezone.utc)
    try:
        parsed = parsedate_to_datetime(date_header)
    except (TypeError, ValueError, IndexError):
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _thread_id(message: Any, rfc_message_id: str) -> str:
    references = str(message.get("References", "")).split()
    if references:
        return references[-1]
    in_reply_to = str(message.get("In-Reply-To", "")).strip()
    if in_reply_to:
        return in_reply_to
    return rfc_message_id


def fetch_new_messages(client: Any, folder: str, since_uid: int, batch_size: int = 200) -> list[ParsedMessage]:
    try:
        client.select_folder(folder)
        uids = sorted(int(uid) for uid in client.search(["UID", f"{since_uid + 1}:*"]) if int(uid) > since_uid)[:batch_size]
        if not uids:
            return []
        fetched = client.fetch(uids, ["RFC822", "UID"])
    except Exception:
        logger.exception("imap_fetch_failed", extra={"folder": folder, "since_uid": since_uid})
        return []

    messages: list[ParsedMessage] = []
    for uid in uids:
        row = fetched.get(uid, {})
        payload = row.get(b"RFC822") or row.get("RFC822")
        if not isinstance(payload, (bytes, bytearray)):
            continue
        message = _decode_message_bytes(bytes(payload))
        rfc_message_id = str(message.get("Message-ID") or f"<uid-{uid}>")
        from_addr = parseaddr(str(message.get("From", "")))[1]
        to_addr = parseaddr(str(message.get("To", "")))[1]
        body_html, body_plain = _extract_body_parts(message)
        quarantine_input = body_html or body_plain
        sanitized = run_full_quarantine(quarantine_input)
        messages.append(
            ParsedMessage(
                rfc_message_id=rfc_message_id,
                thread_id=_thread_id(message, rfc_message_id),
                imap_uid=uid,
                from_addr=from_addr,
                from_domain=from_addr.split("@", 1)[1].lower() if "@" in from_addr else "",
                to_addr=to_addr,
                subject=str(message.get("Subject", "")),
                received_at=_parse_received_at(message.get("Date")),
                body_html=body_html,
                body_text=sanitized.sanitized_text,
            )
        )
    return messages
