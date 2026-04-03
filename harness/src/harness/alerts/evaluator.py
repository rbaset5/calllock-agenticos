from __future__ import annotations

from typing import Any

from harness.detection.evaluator import evaluate_detection


def evaluate_alerts(*, tenant_id: str | None = None, window_minutes: int = 15) -> list[dict[str, Any]]:
    return evaluate_detection(tenant_id=tenant_id, window_minutes=window_minutes)
