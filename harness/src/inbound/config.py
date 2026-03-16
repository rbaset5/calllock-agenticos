from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = {
    "polling": {
        "default_interval_minutes": 60,
        "imap_timeout_seconds": 30,
        "batch_size": 200,
        "backfill_max_messages": 50,
    },
    "scoring": {
        "model": "claude-sonnet-4-5-20250514",
        "max_tokens": 1024,
        "temperature": 0.1,
        "retry_max_attempts": 3,
        "retry_delay_seconds": 60,
    },
    "drafting": {
        "writer_model": "claude-sonnet-4-5-20250514",
        "reviewer_model": "claude-sonnet-4-5-20250514",
        "max_tokens": 2048,
    },
    "research": {
        "cache_ttl_hours": 168,
        "fetch_timeout_seconds": 10,
        "blocked_ip_ranges": [
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "127.0.0.0/8",
            "169.254.0.0/16",
            "::1/128",
            "fc00::/7",
        ],
    },
    "escalation": {
        "backend": "incidents",
        "consecutive_poll_failure_threshold": 3,
        "quarantine_rate_alert_threshold": 0.5,
    },
    "backfill": {
        "enabled": True,
        "max_messages": 50,
    },
}


def _merge_dicts(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_inbound_config(path: str = "config/inbound.yaml") -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return deepcopy(DEFAULT_CONFIG)
    loaded = yaml.safe_load(config_path.read_text()) or {}
    if not isinstance(loaded, dict):
        return deepcopy(DEFAULT_CONFIG)
    return _merge_dicts(DEFAULT_CONFIG, loaded)
