from __future__ import annotations

from email.message import EmailMessage

from inbound import imap_client


def _sample_message_bytes() -> bytes:
    message = EmailMessage()
    message["Message-ID"] = "<msg-1@example.com>"
    message["In-Reply-To"] = "<thread-root@example.com>"
    message["From"] = "Example Owner <owner@example.com>"
    message["To"] = "Inbox <sales@calllock.test>"
    message["Subject"] = "Need missed-call help"
    message["Date"] = "Mon, 17 Mar 2026 10:00:00 +0000"
    message.set_content("Plain text fallback")
    message.add_alternative(
        "<html><body><p>Hello <b>team</b> https://example.com</p></body></html>",
        subtype="html",
    )
    return message.as_bytes()


def test_connect_imap_uses_password_and_oauth2(monkeypatch) -> None:
    calls: list[tuple[str, str, str]] = []

    class FakeIMAPClient:
        def __init__(self, host: str, *, port: int, ssl: bool) -> None:
            calls.append(("init", host, str(port)))

        def login(self, username: str, credential: str) -> None:
            calls.append(("login", username, credential))

        def oauth2_login(self, username: str, credential: str) -> None:
            calls.append(("oauth2", username, credential))

    monkeypatch.setattr(imap_client, "IMAPClient", FakeIMAPClient)

    password_client = imap_client.connect_imap("imap.example.com", 993, "owner", "secret")
    oauth_client = imap_client.connect_imap("imap.example.com", 993, "owner", "token", auth_type="oauth2")

    assert isinstance(password_client, FakeIMAPClient)
    assert isinstance(oauth_client, FakeIMAPClient)
    assert ("login", "owner", "secret") in calls
    assert ("oauth2", "owner", "token") in calls


def test_fetch_new_messages_parses_message_and_sanitizes_html() -> None:
    class FakeClient:
        def select_folder(self, folder: str) -> None:
            self.folder = folder

        def search(self, criteria):
            return [5]

        def fetch(self, uids, fields):
            return {5: {b"RFC822": _sample_message_bytes(), b"UID": 5}}

    messages = imap_client.fetch_new_messages(FakeClient(), "INBOX", since_uid=0)

    assert len(messages) == 1
    parsed = messages[0]
    assert parsed.rfc_message_id == "<msg-1@example.com>"
    assert parsed.thread_id == "<thread-root@example.com>"
    assert parsed.imap_uid == 5
    assert parsed.from_addr == "owner@example.com"
    assert parsed.from_domain == "example.com"
    assert parsed.body_html.startswith("<html>")
    assert parsed.body_text == "Hello team [link removed]"


def test_fetch_new_messages_respects_uid_filter_and_batch_size() -> None:
    class FakeClient:
        def select_folder(self, folder: str) -> None:
            return None

        def search(self, criteria):
            return [1, 2, 3, 4]

        def fetch(self, uids, fields):
            return {uid: {b"RFC822": _sample_message_bytes(), b"UID": uid} for uid in uids}

    messages = imap_client.fetch_new_messages(FakeClient(), "INBOX", since_uid=2, batch_size=1)

    assert [message.imap_uid for message in messages] == [3]


def test_fetch_new_messages_returns_empty_list_on_client_error() -> None:
    class BrokenClient:
        def select_folder(self, folder: str) -> None:
            raise RuntimeError("imap down")

    assert imap_client.fetch_new_messages(BrokenClient(), "INBOX", since_uid=0) == []
