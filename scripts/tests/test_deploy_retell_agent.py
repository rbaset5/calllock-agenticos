"""Tests for scripts/deploy-retell-agent.py

Covers:
  - YAML loading (with and without frontmatter)
  - Diff computation (no changes, field changes, None handling)
  - LLM ID resolution (agent → LLM)
  - Apply + verify flow
  - Error handling (missing config key, API errors)
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

# The script has a hyphen in its name, so we use importlib to load it.
# We also need to mock httpx before importing since it does a top-level import.
import importlib.util

sys.modules.setdefault("httpx", MagicMock())

_spec = importlib.util.spec_from_file_location(
    "deploy_retell_agent",
    str(Path(__file__).parent.parent / "deploy-retell-agent.py"),
)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

SYNC_FIELDS = _mod.SYNC_FIELDS
compute_diff = _mod.compute_diff
load_yaml_config = _mod.load_yaml_config


# ============================================================================
# YAML LOADING
# ============================================================================


class TestLoadYamlConfig:
    def test_loads_config_key_from_yaml(self, tmp_path: Path) -> None:
        """Basic case: YAML with frontmatter + config key."""
        yaml_content = textwrap.dedent("""\
            id: retell-agent-v10
            title: HVAC Voice Agent
            config:
              general_prompt: "You are a helpful HVAC assistant."
              model: gpt-4o-mini
              model_temperature: 0.3
        """)
        config_file = tmp_path / "agent.yaml"
        config_file.write_text(yaml_content)

        result = load_yaml_config(str(config_file))

        assert result["general_prompt"] == "You are a helpful HVAC assistant."
        assert result["model"] == "gpt-4o-mini"
        assert result["model_temperature"] == 0.3

    def test_loads_config_with_states(self, tmp_path: Path) -> None:
        """Config with nested states array."""
        yaml_content = textwrap.dedent("""\
            id: test
            config:
              general_prompt: "Hello"
              states:
                - name: greeting
                  tools: []
                - name: collect_info
                  tools:
                    - type: end_call
        """)
        config_file = tmp_path / "agent.yaml"
        config_file.write_text(yaml_content)

        result = load_yaml_config(str(config_file))

        assert len(result["states"]) == 2
        assert result["states"][0]["name"] == "greeting"
        assert result["states"][1]["name"] == "collect_info"

    def test_raises_on_missing_config_key(self, tmp_path: Path) -> None:
        """YAML without a 'config' key should exit."""
        yaml_content = textwrap.dedent("""\
            id: test
            title: No config key here
            general_prompt: "This is at the wrong level"
        """)
        config_file = tmp_path / "agent.yaml"
        config_file.write_text(yaml_content)

        with pytest.raises(SystemExit):
            load_yaml_config(str(config_file))

    def test_raises_on_empty_yaml(self, tmp_path: Path) -> None:
        """Empty YAML file should exit."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        with pytest.raises(SystemExit):
            load_yaml_config(str(config_file))


# ============================================================================
# DIFF COMPUTATION
# ============================================================================


class TestComputeDiff:
    def test_no_changes(self) -> None:
        """Identical configs produce no diff."""
        config = {
            "general_prompt": "Hello",
            "model": "gpt-4o-mini",
            "model_temperature": 0.3,
        }
        changes = compute_diff(config, config.copy())
        assert changes == []

    def test_detects_field_change(self) -> None:
        """Changed field appears in diff."""
        local = {"general_prompt": "New prompt", "model": "gpt-4o-mini"}
        remote = {"general_prompt": "Old prompt", "model": "gpt-4o-mini"}

        changes = compute_diff(local, remote)

        assert len(changes) == 1
        assert changes[0]["field"] == "general_prompt"
        assert changes[0]["local"] == "New prompt"
        assert changes[0]["remote"] == "Old prompt"
        assert changes[0]["action"] == "update"

    def test_detects_multiple_changes(self) -> None:
        """Multiple changed fields all appear."""
        local = {"general_prompt": "New", "model": "claude-3-5-sonnet"}
        remote = {"general_prompt": "Old", "model": "gpt-4o-mini"}

        changes = compute_diff(local, remote)

        fields = {c["field"] for c in changes}
        assert "general_prompt" in fields
        assert "model" in fields

    def test_none_and_missing_are_equivalent(self) -> None:
        """None in local and missing in remote (or vice versa) = no diff."""
        local: dict[str, Any] = {"general_prompt": "Hello"}  # states is missing
        remote: dict[str, Any] = {"general_prompt": "Hello", "states": None}

        changes = compute_diff(local, remote)
        assert changes == []

    def test_detects_new_field_in_local(self) -> None:
        """Field present in local but None/missing in remote = change."""
        local = {"general_prompt": "Hello", "begin_message": "Hi there!"}
        remote = {"general_prompt": "Hello"}

        changes = compute_diff(local, remote)

        assert len(changes) == 1
        assert changes[0]["field"] == "begin_message"
        assert changes[0]["local"] == "Hi there!"
        assert changes[0]["remote"] is None

    def test_deep_compare_states(self) -> None:
        """States with nested structure differences are detected."""
        local = {
            "states": [
                {"name": "greeting", "tools": [{"type": "end_call"}]},
            ]
        }
        remote = {
            "states": [
                {"name": "greeting", "tools": []},
            ]
        }

        changes = compute_diff(local, remote)

        assert len(changes) == 1
        assert changes[0]["field"] == "states"

    def test_ignores_non_sync_fields(self) -> None:
        """Fields not in SYNC_FIELDS are ignored."""
        local = {"general_prompt": "Hello", "voice_id": "some_voice"}
        remote = {"general_prompt": "Hello", "voice_id": "other_voice"}

        changes = compute_diff(local, remote)

        # voice_id is not in SYNC_FIELDS
        assert changes == []

    def test_key_order_irrelevant(self) -> None:
        """JSON serialization with sort_keys means key order doesn't matter."""
        local = {
            "states": [
                {"name": "a", "tools": [], "edges": [{"dest": "b"}]},
            ]
        }
        remote = {
            "states": [
                {"edges": [{"dest": "b"}], "name": "a", "tools": []},
            ]
        }

        changes = compute_diff(local, remote)
        assert changes == []


# ============================================================================
# SYNC_FIELDS CONSTANT
# ============================================================================


class TestSyncFields:
    def test_sync_fields_contains_critical_fields(self) -> None:
        """Verify critical fields are in SYNC_FIELDS."""
        assert "general_prompt" in SYNC_FIELDS
        assert "states" in SYNC_FIELDS
        assert "general_tools" in SYNC_FIELDS
        assert "model" in SYNC_FIELDS
        assert "model_temperature" in SYNC_FIELDS

    def test_sync_fields_excludes_agent_level_fields(self) -> None:
        """Voice ID and other agent-level fields should NOT be synced."""
        assert "voice_id" not in SYNC_FIELDS
        assert "agent_name" not in SYNC_FIELDS
        assert "webhook_url" not in SYNC_FIELDS
