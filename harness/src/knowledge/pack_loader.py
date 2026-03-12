from __future__ import annotations

import json
from pathlib import Path


def load_json_yaml(path: str | Path) -> dict[str, object]:
    return json.loads(Path(path).read_text())
