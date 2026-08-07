"""Tests for Retell config snapshot capture."""

from __future__ import annotations

from db import repository
from voice.production.config_snapshot import build_retell_config_snapshot, record_retell_config_snapshot


def test_build_retell_config_snapshot_hashes_yaml_config(monkeypatch) -> None:
    monkeypatch.setenv("RETELL_AGENT_ID", "agent-test")
    monkeypatch.setenv("RETELL_LLM_ID", "llm-test")

    snapshot = build_retell_config_snapshot(call_id="call-001", tenant_id="tenant-ace-001")

    assert snapshot["tenant_id"] == "tenant-ace-001"
    assert snapshot["call_id"] == "call-001"
    assert snapshot["retell_agent_id"] == "agent-test"
    assert snapshot["retell_llm_id"] == "llm-test"
    assert snapshot["config_hash"]
    assert snapshot["config_source_path"].endswith("retell-agent-v10.yaml")
    assert "config" in snapshot["config_snapshot"]


def test_record_retell_config_snapshot_upserts(monkeypatch) -> None:
    monkeypatch.setenv("RETELL_AGENT_ID", "agent-test")
    monkeypatch.setenv("RETELL_LLM_ID", "llm-test")

    first = record_retell_config_snapshot(call_id="call-001", tenant_id="tenant-ace-001")
    second = record_retell_config_snapshot(call_id="call-001", tenant_id="tenant-ace-001")

    assert second["id"] == first["id"]
    stored = repository.get_voice_config_snapshot("tenant-ace-001", "call-001")
    assert stored is not None
    assert stored["config_hash"] == first["config_hash"]

