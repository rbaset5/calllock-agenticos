from __future__ import annotations

from typing import Any

from observability.pii_redactor import redact_pii


def prepare_trace_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: redact_pii(value) if isinstance(value, str) else value
        for key, value in payload.items()
    }
