from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[4]


def journal_root() -> Path:
    configured = os.getenv("CALLLOCK_RECOVERY_ROOT")
    return Path(configured) if configured else REPO_ROOT / ".context" / "recovery"


def _tenant_partition(tenant_id: str | None) -> str:
    if not tenant_id:
        return "global"
    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in tenant_id) or "global"


def journal_path(entry_type: str, tenant_id: str | None = None) -> Path:
    return journal_root() / _tenant_partition(tenant_id) / f"{entry_type}.jsonl"


def write_recovery_entry(entry_type: str, payload: dict[str, Any]) -> str:
    tenant_id = payload.get("tenant_id")
    if not isinstance(tenant_id, str):
        record = payload.get("record", {})
        tenant_id = record.get("tenant_id") if isinstance(record, dict) and isinstance(record.get("tenant_id"), str) else None
    target = journal_path(entry_type, tenant_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "id": str(uuid4()),
        "entry_type": entry_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tenant_scope": tenant_id,
        "payload": payload,
    }
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    return str(target)


def list_recovery_entries(entry_type: str | None = None) -> list[dict[str, Any]]:
    root = journal_root()
    if not root.exists():
        return []
    if entry_type:
        targets = sorted(path for path in root.rglob(f"{entry_type}.jsonl") if path.is_file())
    else:
        targets = sorted(path for path in root.rglob("*.jsonl") if path.is_file())
    records: list[dict[str, Any]] = []
    for target in targets:
        if not target.exists():
            continue
        with target.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
    return sorted(records, key=lambda item: item["created_at"], reverse=True)


def get_recovery_entry(entry_id: str) -> dict[str, Any]:
    for record in list_recovery_entries():
        if record["id"] == entry_id:
            return record
    raise KeyError(f"Unknown recovery entry: {entry_id}")
