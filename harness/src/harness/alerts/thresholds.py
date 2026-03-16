from __future__ import annotations

from typing import Any

DEFAULT_THRESHOLDS = {
    "policy_block_rate": 0.5,
    "worker_metric_degradation": 0.3,
    "job_failure_spike": 3,
    "external_service_error": 1,
    "scheduler_stale_claims": 1,
    "scheduler_backlog_age": 60,
}


def resolve_thresholds(tenant_config: dict[str, Any] | None = None) -> dict[str, float]:
    thresholds = dict(DEFAULT_THRESHOLDS)
    overrides = (tenant_config or {}).get("alert_thresholds", {})
    if not isinstance(overrides, dict):
        return thresholds

    for alert_type, value in overrides.items():
        if alert_type not in thresholds:
            continue
        if isinstance(value, bool):
            continue
        if not isinstance(value, (int, float)):
            continue
        if value < 0:
            continue
        thresholds[alert_type] = float(value)
    return thresholds
