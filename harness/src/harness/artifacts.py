from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]


def artifact_root() -> Path:
    configured = os.getenv("CALLLOCK_ARTIFACT_ROOT")
    return Path(configured) if configured else REPO_ROOT / ".context" / "artifacts"


def write_run_artifact(record: dict[str, Any]) -> str:
    target_dir = artifact_root() / "runs"
    target_dir.mkdir(parents=True, exist_ok=True)
    run_id = record.get("run_id", "unknown-run")
    target = target_dir / f"{run_id}.json"
    target.write_text(json.dumps(record, indent=2) + "\n")
    return str(target)
