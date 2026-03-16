from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    from langsmith import Client
except Exception:  # pragma: no cover
    Client = None  # type: ignore[assignment]

from observability.pii_redactor import redact_pii_recursive


REPO_ROOT = Path(__file__).resolve().parents[3]


def trace_root() -> Path:
    configured = os.getenv("CALLLOCK_TRACE_ROOT")
    return Path(configured) if configured else REPO_ROOT / ".context" / "traces"


def _tenant_partition(tenant_id: str | None) -> str:
    if not tenant_id:
        return "global"
    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in tenant_id) or "global"


def trace_path(tenant_id: str | None = None) -> Path:
    return trace_root() / _tenant_partition(tenant_id) / "local-traces.jsonl"


def _trace_client() -> Any:
    if Client is None or not os.getenv("LANGSMITH_API_KEY"):
        return None
    return Client(api_key=os.getenv("LANGSMITH_API_KEY"))

def prepare_trace_payload(payload: dict[str, Any]) -> dict[str, Any]:
    prepared = redact_pii_recursive(payload)
    prepared["data_classification"] = "pii-redacted"
    return prepared


def write_local_trace(payload: dict[str, Any], *, tenant_id: str | None = None) -> dict[str, Any]:
    path = trace_path(tenant_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    trace_record = {
        "trace_id": payload.get("trace_id", str(uuid4())),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tenant_scope": tenant_id,
        "payload": payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(trace_record) + "\n")
    return {"backend": "local", "trace_id": trace_record["trace_id"], "path": str(path)}


def submit_trace(*, name: str, payload: dict[str, Any], run_type: str = "chain") -> dict[str, Any]:
    tenant_scope = payload.get("tenant_id") if isinstance(payload.get("tenant_id"), str) else None
    prepared = prepare_trace_payload(payload)
    client = _trace_client()
    if client is None:
        return write_local_trace({"name": name, "run_type": run_type, **prepared}, tenant_id=tenant_scope)

    trace_id = str(uuid4())
    project_name = prepared.get("trace_namespace") or os.getenv("LANGSMITH_PROJECT", "calllock-agentos")
    try:
        client.create_run(
            id=trace_id,
            name=name,
            run_type=run_type,
            inputs=prepared.get("inputs", {}),
            outputs=prepared.get("outputs", {}),
            extra={
                "tenant_id": prepared.get("tenant_id"),
                "worker_id": prepared.get("worker_id"),
                "data_classification": prepared.get("data_classification"),
            },
            project_name=project_name,
        )
        return {"backend": "langsmith", "trace_id": trace_id, "project_name": project_name}
    except Exception:
        return write_local_trace({"name": name, "run_type": run_type, **prepared}, tenant_id=tenant_scope)
