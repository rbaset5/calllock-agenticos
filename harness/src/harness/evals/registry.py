from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
EVAL_ROOT = REPO_ROOT / "evals"


def infer_level(path: Path) -> str:
    worker = path.parent.name
    if worker == "customer-analyst":
        return "industry"
    return "core"


def discover_eval_datasets() -> list[dict]:
    datasets = []
    for path in sorted(EVAL_ROOT.glob("*/*.json")):
        datasets.append(
            {
                "id": f"{path.parent.name}:{path.stem}",
                "worker_id": path.parent.name,
                "metric": path.stem,
                "path": path,
                "level": infer_level(path),
                "examples": json.loads(path.read_text()),
            }
        )
    return datasets
