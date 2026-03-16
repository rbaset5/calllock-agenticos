from __future__ import annotations

from db.repository import save_customer_content
from observability.pii_redactor import redact_pii


def process_customer_content(payload: dict) -> dict:
    raw = payload["transcript"]
    sanitized = redact_pii(raw)
    structured = {
        "sentiment": "negative" if any(word in sanitized.lower() for word in ["angry", "upset", "frustrated"]) else "neutral",
        "topics": [topic for topic in ["no heat", "ac", "billing", "booking"] if topic in sanitized.lower()],
    }
    record = save_customer_content(
        {
            "tenant_id": payload["tenant_id"],
            "call_id": payload["call_id"],
            "consent_granted": payload.get("consent_granted", False),
            "raw_transcript": raw,
            "sanitized_transcript": sanitized,
            "structured_content": structured,
        }
    )
    return record
