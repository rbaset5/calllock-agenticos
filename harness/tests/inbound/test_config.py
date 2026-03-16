from __future__ import annotations

from pathlib import Path

from inbound.config import DEFAULT_CONFIG, load_inbound_config


def test_load_inbound_config_returns_defaults_for_missing_file(tmp_path: Path) -> None:
    config = load_inbound_config(str(tmp_path / "missing.yaml"))

    assert config == DEFAULT_CONFIG


def test_load_inbound_config_returns_defaults_for_empty_file(tmp_path: Path) -> None:
    config_path = tmp_path / "inbound.yaml"
    config_path.write_text("")

    config = load_inbound_config(str(config_path))

    assert config == DEFAULT_CONFIG


def test_load_inbound_config_merges_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "inbound.yaml"
    config_path.write_text(
        """
polling:
  batch_size: 50
research:
  fetch_timeout_seconds: 3
backfill:
  enabled: false
"""
    )

    config = load_inbound_config(str(config_path))

    assert config["polling"]["default_interval_minutes"] == 60
    assert config["polling"]["batch_size"] == 50
    assert config["research"]["cache_ttl_hours"] == 168
    assert config["research"]["fetch_timeout_seconds"] == 3
    assert config["backfill"]["enabled"] is False
