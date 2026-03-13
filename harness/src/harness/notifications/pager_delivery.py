from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[4]


def pager_outbox_root() -> Path:
    configured = os.getenv("CALLLOCK_PAGER_OUTBOX_ROOT")
    return Path(configured) if configured else REPO_ROOT / ".context" / "pager-outbox"


def _normalize_targets(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    targets: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip() and item.strip() not in targets:
            targets.append(item.strip())
    return targets


def _write_outbox(category: str, record: dict[str, Any]) -> Path:
    root = pager_outbox_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{category}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")
    return path


def deliver_pager(
    *,
    category: str,
    targets: Any,
    summary: str,
    severity: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    resolved_targets = _normalize_targets(targets)
    if not resolved_targets:
        return {"channel": "pager", "delivered": False, "reason": "missing_pager_target"}

    outbox_record = {
        "targets": resolved_targets,
        "summary": summary,
        "severity": severity,
        "payload": payload,
    }

    webhook_url = os.getenv("PAGER_WEBHOOK_URL")
    if not webhook_url:
        path = _write_outbox(category, outbox_record)
        return {
            "channel": "pager",
            "delivered": True,
            "backend": "outbox",
            "destination": str(path),
            "targets": resolved_targets,
        }

    if httpx is None:
        path = _write_outbox(category, {**outbox_record, "webhook_error": "httpx_unavailable"})
        return {
            "channel": "pager",
            "delivered": False,
            "backend": "webhook_error_outbox",
            "destination": str(path),
            "targets": resolved_targets,
            "reason": "httpx_unavailable",
        }

    request_payload = {
        "targets": resolved_targets,
        "summary": summary,
        "severity": severity,
        "payload": payload,
    }
    integration_key = os.getenv("PAGER_INTEGRATION_KEY")
    headers = {"Authorization": f"Bearer {integration_key}"} if integration_key else None
    try:
        response = httpx.post(webhook_url, json=request_payload, headers=headers, timeout=5.0)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - exercised in tests via outbox path
        path = _write_outbox(category, {**outbox_record, "webhook_error": str(exc)})
        return {
            "channel": "pager",
            "delivered": False,
            "backend": "webhook_error_outbox",
            "destination": str(path),
            "targets": resolved_targets,
            "reason": str(exc),
        }

    return {
        "channel": "pager",
        "delivered": True,
        "backend": "webhook",
        "destination": webhook_url,
        "targets": resolved_targets,
    }
