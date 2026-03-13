from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[4]


def artifact_root() -> Path:
    configured = os.getenv("CALLLOCK_ARTIFACT_ROOT")
    return Path(configured) if configured else REPO_ROOT / ".context" / "artifacts"


def normalize_artifact(record: dict[str, Any]) -> dict[str, Any]:
    artifact_id = record.get("id") or str(uuid4())
    return {
        "id": artifact_id,
        "tenant_id": record["tenant_id"],
        "run_id": record.get("run_id"),
        "created_by": record.get("created_by", "harness"),
        "artifact_type": record.get("artifact_type", "run_record"),
        "source_job_id": record.get("source_job_id"),
        "payload": record.get("payload", {}),
        "lineage": record.get("lineage", {}),
        "lifecycle_state": record.get("lifecycle_state", "created"),
        "created_at": record.get("created_at", datetime.now(timezone.utc).isoformat()),
    }


def write_run_artifact(record: dict[str, Any]) -> str:
    artifact = normalize_artifact(record)
    target_dir = artifact_root() / artifact["tenant_id"] / "runs"
    target_dir.mkdir(parents=True, exist_ok=True)
    run_id = artifact.get("run_id", artifact["id"])
    target = target_dir / f"{run_id}.json"
    target.write_text(json.dumps(artifact, indent=2) + "\n")
    return str(target)
