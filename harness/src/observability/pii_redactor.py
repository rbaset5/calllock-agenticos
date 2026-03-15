from __future__ import annotations

import re


PHONE_RE = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")


def redact_pii(text: str) -> str:
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    return EMAIL_RE.sub("[REDACTED_EMAIL]", text)
