from __future__ import annotations

from pathlib import Path

import pytest

from harness import context_tools
from harness.mcp_server import MutatingToolDisabledError, ToolArgumentError, invoke_tool, list_mcp_tools
from outbound import store


def _configure_repo_memory(monkeypatch, tmp_path: Path) -> None:
    decisions_dir = tmp_path / "decisions"
    errors_dir = tmp_path / "errors"
    knowledge_dir = tmp_path / "knowledge"
    decisions_dir.mkdir()
    errors_dir.mkdir()
    knowledge_dir.mkdir()
    (decisions_dir / "_index.md").write_text(
        "# Decisions Index\n\n## Voice Pipeline\n\n(none yet)\n\n## Product\n\n(none yet)\n\n## Architecture\n\n(none yet)\n"
    )
    (errors_dir / "_index.md").write_text(
        "# Errors Index\n\n## Voice Pipeline\n\n(none yet)\n\n## Product\n\n(none yet)\n\n## Architecture\n\n(none yet)\n"
    )
    monkeypatch.setattr(context_tools, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(context_tools, "DECISIONS_DIR", decisions_dir)
    monkeypatch.setattr(context_tools, "ERRORS_DIR", errors_dir)
    monkeypatch.setattr(context_tools, "KNOWLEDGE_DIR", knowledge_dir)


def test_list_tools_matches_registry() -> None:
    tools = list_mcp_tools()
    assert len(tools) == 21
    assert tools[0].name == "dispatch_worker"


def test_mutating_tool_requires_write_enablement(monkeypatch, tmp_path) -> None:
    _configure_repo_memory(monkeypatch, tmp_path)
    monkeypatch.delenv("CALLLOCK_GATEWAY_WRITE_ENABLED", raising=False)

    with pytest.raises(MutatingToolDisabledError):
        invoke_tool(
            "create_decision",
            {
                "title": "Test",
                "domain": "product",
                "context": "ctx",
                "options": [{"name": "opt", "description": "desc"}],
                "decision": "Do it.",
                "consequences": "none",
            },
        )


def test_argument_validation_failure() -> None:
    with pytest.raises(ToolArgumentError):
        invoke_tool("create_decision", {"title": "Missing required fields"})


def test_happy_path_core_tool_invocation() -> None:
    result = invoke_tool("read_daily_memo", {"tenant_id": "tenant-alpha"})
    assert result["pending_approvals"] == 0
    assert "pending_skills" in result


def test_happy_path_outbound_tool_invocation() -> None:
    store.upsert_outbound_prospects(
        [
            {
                "id": "p1",
                "business_name": "Johnson HVAC",
                "phone_normalized": "+16025550142",
                "phone": "(602) 555-0142",
                "metro": "Phoenix",
                "trade": "hvac",
                "stage": "interested",
                "total_score": 92,
                "score_tier": "a_lead",
                "discovered_at": "2099-03-20T08:00:00+00:00",
            }
        ]
    )
    store.insert_outbound_call(
        {
            "prospect_id": "p1",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "twilio_call_sid": "CA123",
            "called_at": "2099-03-21T15:00:00+00:00",
            "outcome": "answered_interested",
            "demo_scheduled": True,
        }
    )

    result = invoke_tool("outbound_funnel_summary", {"days": 7})
    assert result["total_prospects"] == 1
    assert result["demos_scheduled"] == 1


def test_happy_path_context_tool_invocation(monkeypatch, tmp_path) -> None:
    _configure_repo_memory(monkeypatch, tmp_path)
    result = invoke_tool("check_decisions", {"query": "voice pipeline"})
    assert result["count"] == 0
