import logging

import httpx

from harness.graphs.supervisor import run_supervisor
from observability.inngest_emitter import (
    AGENT_STATE_CHANGED_EVENT,
    InngestEventEmitter,
)


def test_emit_node_entry_posts_event_when_dashboard_enabled(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_post(url: str, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        captured["headers"] = kwargs["headers"]

        class _Response:
            def raise_for_status(self) -> None:
                return None

        return _Response()

    monkeypatch.setenv("INNGEST_EVENT_URL", "https://inngest.example/events")
    monkeypatch.setenv("INNGEST_EVENT_KEY", "secret-key")
    monkeypatch.setattr(httpx, "post", _fake_post)

    emitter = InngestEventEmitter()
    result = emitter.emit_node_entry(
        agent_id="eng-ai-voice",
        tenant_id="tenant-123",
        department="engineering",
        role="worker",
        from_state="policy_gate",
        to_state="verification",
        description="AI/Voice Engineer",
        tenant_config={"office_dashboard_enabled": True},
    )

    assert result is None
    assert captured["url"] == "https://inngest.example/events"
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "Authorization": "Bearer secret-key",
    }
    assert captured["json"] == {
        "name": AGENT_STATE_CHANGED_EVENT,
        "data": {
            "agent_id": "eng-ai-voice",
            "tenant_id": "tenant-123",
            "department": "engineering",
            "role": "worker",
            "from_state": "policy_gate",
            "to_state": "verification",
            "description": "AI/Voice Engineer",
        },
    }


def test_emit_node_entry_skips_when_dashboard_disabled(monkeypatch) -> None:
    called = {"post": False}

    def _fake_post(*args, **kwargs):
        called["post"] = True
        raise AssertionError("httpx.post should not be called")

    monkeypatch.setenv("INNGEST_EVENT_URL", "https://inngest.example/events")
    monkeypatch.setattr(httpx, "post", _fake_post)

    emitter = InngestEventEmitter()
    emitter.emit_node_entry(
        agent_id="eng-ai-voice",
        tenant_id="tenant-123",
        department="engineering",
        role="worker",
        from_state="context_assembly",
        to_state="policy_gate",
        tenant_config={"office_dashboard_enabled": False},
    )

    assert called["post"] is False


def test_emit_node_entry_swallows_connect_error(monkeypatch, caplog) -> None:
    monkeypatch.setenv("INNGEST_EVENT_URL", "https://inngest.example/events")

    def _fail_post(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", _fail_post)
    emitter = InngestEventEmitter()

    with caplog.at_level(logging.ERROR, logger="observability.inngest_emitter"):
        result = emitter.emit_node_entry(
            agent_id="eng-ai-voice",
            tenant_id="tenant-123",
            department="engineering",
            role="worker",
            from_state="worker",
            to_state="verification",
            tenant_config={"office_dashboard_enabled": True},
        )

    assert result is None
    assert "connection" in caplog.text.lower()


def test_run_supervisor_emits_on_each_node_entry(monkeypatch) -> None:
    emitted: list[tuple[str | None, str]] = []

    def _capture_emit(**kwargs):
        emitted.append((kwargs.get("from_state"), kwargs["to_state"]))
        return None

    monkeypatch.setattr(
        "harness.graphs.supervisor.AGENT_STATE_EMITTER.emit_node_entry",
        _capture_emit,
    )

    state = {
        "tenant_id": "tenant-alpha",
        "run_id": "run-1",
        "worker_id": "customer-analyst",
        "tool_name": None,
        "task": {
            "problem_description": "No heat in the house",
            "transcript": "Customer is upset and has no heat tonight.",
            "worker_spec": {
                "title": "AI/Voice Engineer",
                "department": "engineering",
                "role": "worker",
                "mission": "Analyze post-call outcomes.",
                "tools_allowed": ["notify_dispatch"],
            },
            "tenant_config": {
                "allowed_tools": ["notify_dispatch"],
                "office_dashboard_enabled": True,
            },
            "industry_pack": {"summary": "HVAC pack"},
            "knowledge_nodes": [{"summary": "Emergency no-heat calls should route to dispatch."}],
            "feature_flags": {"harness_enabled": True},
            "compliance_rules": [{"id": "allow-default", "target": "*", "effect": "allow"}],
        },
    }

    result = run_supervisor(state)

    assert result["verification"]["passed"] is True
    assert [entry[1] for entry in emitted] == [
        "context_assembly",
        "policy_gate",
        "worker",
        "verification",
        "guardian_gate",
        "job_dispatch",
        "persist",
    ]
