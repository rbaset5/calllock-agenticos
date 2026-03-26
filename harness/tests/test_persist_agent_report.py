"""Tests for guardian agent report persistence."""
from __future__ import annotations

from unittest.mock import patch

from harness.nodes.persist import GUARDIAN_AGENTS, persist_node


def _make_state(worker_id: str, output: dict | None = None) -> dict:
    return {
        "tenant_id": "test-tenant",
        "run_id": "run-001",
        "worker_id": worker_id,
        "worker_output": output or {},
        "task": {"task_context": {"task_type": "voice-health-check"}},
        "policy_decision": {"verdict": "allow"},
        "verification": {"passed": True, "verdict": "pass"},
        "jobs": [],
    }


@patch("harness.nodes.persist.create_artifact", return_value={})
@patch("harness.nodes.persist.persist_run_record", return_value={"job": {"id": "j1"}})
@patch("harness.nodes.persist.maybe_create_approval_request", return_value=None)
class TestGuardianAgentReports:
    @patch("harness.nodes.persist.upsert_agent_report")
    def test_guardian_agent_writes_report(self, mock_upsert, _approval, _persist, _artifact):
        state = _make_state("eng-ai-voice", {"summary": "all good"})
        persist_node(state)
        mock_upsert.assert_called_once()
        call_args = mock_upsert.call_args[0][0]
        assert call_args["agent_id"] == "eng-ai-voice"
        assert call_args["status"] == "green"
        assert call_args["report_type"] == "voice-health-check"

    @patch("harness.nodes.persist.upsert_agent_report")
    def test_guardian_agent_red_on_violations(self, mock_upsert, _approval, _persist, _artifact):
        state = _make_state("eng-product-qa", {"violations": [{"field": "urgency_tier"}]})
        persist_node(state)
        call_args = mock_upsert.call_args[0][0]
        assert call_args["status"] == "red"

    @patch("harness.nodes.persist.upsert_agent_report")
    def test_guardian_agent_yellow_on_warnings(self, mock_upsert, _approval, _persist, _artifact):
        state = _make_state("eng-app", {"warnings": ["stale data"]})
        persist_node(state)
        call_args = mock_upsert.call_args[0][0]
        assert call_args["status"] == "yellow"

    @patch("harness.nodes.persist.upsert_agent_report", side_effect=Exception("boom"))
    def test_report_failure_does_not_crash_persist(self, mock_upsert, _approval, _persist, _artifact):
        """Report write failure must not break the main persist flow."""
        state = _make_state("eng-ai-voice")
        result = persist_node(state)
        assert "persistence" in result

    def test_non_guardian_agent_skips_report(self, _approval, _persist, _artifact):
        with patch("harness.nodes.persist.upsert_agent_report") as mock_upsert:
            state = _make_state("customer-analyst")
            persist_node(state)
            mock_upsert.assert_not_called()


def test_guardian_agent_ids():
    """Verify the set matches the three Product Guardian agents."""
    assert GUARDIAN_AGENTS == {"eng-ai-voice", "eng-app", "eng-product-qa"}
