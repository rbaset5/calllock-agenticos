from __future__ import annotations

from hashlib import sha256
import re
from typing import Any


PHONE_RE = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")
ADDRESS_RE = re.compile(r"\b\d{1,6}\s+[A-Za-z0-9.\- ]+\s(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)\b", re.IGNORECASE)
ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")


def _redact_string(text: str) -> str:
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = ADDRESS_RE.sub("[REDACTED_ADDRESS]", text)
    return ZIP_RE.sub("[REDACTED_ZIP]", text)


def redact_pii(text: str) -> str:
    return _redact_string(text)


def hash_identifier(value: str) -> str:
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()[:16]}"


def redact_pii_recursive(value: Any) -> Any:
    if isinstance(value, str):
        return redact_pii(value)
    if isinstance(value, list):
        return [redact_pii_recursive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_pii_recursive(item) for item in value)
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"tenant_id", "call_id", "run_id", "job_id"} and isinstance(item, str):
                redacted[key] = hash_identifier(item)
            else:
                redacted[key] = redact_pii_recursive(item)
        return redacted
    return value
