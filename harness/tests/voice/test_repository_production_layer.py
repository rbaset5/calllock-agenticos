"""Tests for voice production-layer repository records."""

from __future__ import annotations

from db import repository


def test_records_and_lists_voice_call_events() -> None:
    event = repository.record_voice_call_event(
        {
            "tenant_id": "tenant-ace-001",
            "call_id": "call-001",
            "retell_call_id": "ret-001",
            "event_type": "call_ended",
            "source": "retell",
            "payload": {"call_id": "ret-001"},
            "payload_hash": "hash-001",
        }
    )

    assert event["id"]
    assert event["event_type"] == "call_ended"

    repository.record_voice_call_event(
        {
            "tenant_id": "tenant-ace-001",
            "call_id": "other-call",
            "retell_call_id": "ret-002",
            "event_type": "call_ended",
            "source": "retell",
            "payload": {},
            "payload_hash": "hash-002",
        }
    )

    rows = repository.list_voice_call_events("tenant-ace-001", "call-001")
    assert [row["call_id"] for row in rows] == ["call-001"]


def test_records_and_lists_voice_tool_calls() -> None:
    tool_call = repository.record_voice_tool_call(
        {
            "tenant_id": "tenant-ace-001",
            "call_id": "call-001",
            "retell_call_id": "ret-001",
            "tool_name": "lookup_caller",
            "request_payload": {"args": {"phone_number": "+15125550101"}},
            "response_payload": {"found": False},
            "status": "success",
            "latency_ms": 12,
        }
    )

    assert tool_call["id"]
    assert tool_call["status"] == "success"

    rows = repository.list_voice_tool_calls("tenant-ace-001", "call-001")
    assert len(rows) == 1
    assert rows[0]["tool_name"] == "lookup_caller"
    assert rows[0]["latency_ms"] == 12


def test_config_snapshot_is_upserted_per_call() -> None:
    first = repository.record_voice_config_snapshot(
        {
            "tenant_id": "tenant-ace-001",
            "call_id": "call-001",
            "retell_agent_id": "agent-old",
            "retell_llm_id": "llm-old",
            "config_source_path": "knowledge/industry-packs/hvac/voice/retell-agent-v10.yaml",
            "config_hash": "hash-old",
            "config_snapshot": {"config": {"model": "gpt-4o"}},
        }
    )
    second = repository.record_voice_config_snapshot(
        {
            "tenant_id": "tenant-ace-001",
            "call_id": "call-001",
            "retell_agent_id": "agent-new",
            "retell_llm_id": "llm-new",
            "config_source_path": "knowledge/industry-packs/hvac/voice/retell-agent-v10.yaml",
            "config_hash": "hash-new",
            "config_snapshot": {"config": {"model": "gpt-4o-mini"}},
        }
    )

    assert second["id"] == first["id"]
    assert second["config_hash"] == "hash-new"

    stored = repository.get_voice_config_snapshot("tenant-ace-001", "call-001")
    assert stored is not None
    assert stored["retell_agent_id"] == "agent-new"

