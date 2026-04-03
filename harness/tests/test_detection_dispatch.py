from harness.dispatch import DispatchResult
from harness.detection.dispatch import build_detection_dispatches
from harness.detection.evaluator import evaluate_detection
from harness.graphs.workers.eng_product_qa import run_eng_product_qa


def test_investigate_dispatches_to_voice_builder() -> None:
    requests = build_detection_dispatches(
        {
            "tenant_id": "tenant-alpha",
            "alert_type": "voice_route_missing_spike",
            "metrics": {
                "detection": {
                    "triage_outcome": "investigate",
                    "dedupe_key": "tenant-alpha:voice_route_missing_spike",
                }
            },
        }
    )

    assert len(requests) == 1
    assert requests[0].worker_id == "voice-builder"
    assert requests[0].task_type == "detection-investigate"
    assert requests[0].priority == "medium"
    assert requests[0].requires_approval is False


def test_escalation_dispatches_to_eng_product_qa_with_approval() -> None:
    requests = build_detection_dispatches(
        {
            "tenant_id": "tenant-alpha",
            "alert_type": "voice_safety_emergency_mismatch_signal",
            "metrics": {
                "detection": {
                    "triage_outcome": "escalate",
                    "dedupe_key": "tenant-alpha:voice_safety_emergency_mismatch_signal",
                }
            },
        }
    )

    assert len(requests) == 1
    assert requests[0].worker_id == "eng-product-qa"
    assert requests[0].task_type == "detection-investigate"
    assert requests[0].priority == "high"
    assert requests[0].requires_approval is True


def test_evaluator_attaches_dispatch_result(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr("harness.detection.evaluator.get_tenant_config", lambda tenant_id: {})
    monkeypatch.setattr("harness.detection.evaluator.list_jobs", lambda tenant_id=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_scheduler_backlog", lambda tenant_id=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_incidents", lambda tenant_id=None, status=None: [])
    monkeypatch.setattr(
        "harness.detection.evaluator.load_voice_monitor_catalog",
        lambda: {
            "monitors": [
                {
                    "monitor_id": "voice_route_missing_spike",
                    "alert_type": "voice_route_missing_spike",
                    "summary": "Route missing spike.",
                    "severity": "high",
                    "effective_threshold": {
                        "metric": "route_missing_rate",
                        "operator": ">=",
                        "value": 0.1,
                        "window_minutes": 60,
                        "min_sample_size": 1,
                    },
                }
            ]
        },
    )
    monkeypatch.setattr(
        "harness.detection.evaluator.list_recent_call_records",
        lambda **_: [{"tenant_id": "tenant-alpha", "call_id": "call-1", "extracted_fields": {"urgency_tier": "urgent"}, "route": ""}],
    )
    monkeypatch.setattr("harness.detection.evaluator.suppress_duplicate_alert", lambda **kwargs: None)
    monkeypatch.setattr("harness.detection.evaluator.auto_resolve_recovered_alerts", lambda **kwargs: [])
    monkeypatch.setattr(
        "harness.detection.evaluator.create_alert_and_sync_incident",
        lambda payload: {"id": "alert-1", **payload},
    )
    monkeypatch.setattr(
        "harness.detection.evaluator.notify",
        lambda alert, tenant_config=None: {"alert_id": alert["id"], "delivered": False, "channels": []},
    )
    monkeypatch.setattr(
        "harness.detection.evaluator.dispatch_job_requests",
        lambda **kwargs: captured.update(kwargs) or DispatchResult(dispatched=["voice-builder"], queued=[], blocked=[]),
    )

    results = evaluate_detection(tenant_id="tenant-alpha", window_minutes=15)

    assert results[0]["detection_dispatch"] == {
        "dispatched": ["voice-builder"],
        "queued": [],
        "blocked": [],
    }
    assert captured["origin_worker_id"] == "voice-truth"


def test_eng_product_qa_summarizes_detection_coordination() -> None:
    result = run_eng_product_qa(
        {
            "task_context": {
                "task_type": "detection-investigate",
                "detection_issue": {
                    "alert_type": "voice_safety_emergency_mismatch_signal",
                    "triage_outcome": "escalate",
                    "incident_key": "tenant-alpha:voice_safety_emergency_mismatch_signal",
                },
            }
        }
    )

    assert "detection" in result["summary"].lower()
    assert result["next_owner"] == "voice-builder"
