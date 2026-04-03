from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any


def _voice_catalog() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "catalog_id": "voice-monitor-spec",
        "surface": "voice",
        "domain": "detection",
        "ownership": {"team": "voice-platform", "pager": "ops-voice"},
        "default_threshold": {
            "metric": "rate",
            "operator": ">=",
            "value": 0.05,
            "window_minutes": 60,
            "min_sample_size": 1,
        },
        "triage_default": {"priority": "investigate_today", "queue": "voice-monitoring"},
        "notification_default": {"channel": "ops", "target": "voice-monitoring"},
        "monitors": [
            {
                "monitor_id": "voice_route_missing_spike",
                "alert_type": "voice_route_missing_spike",
                "summary": "Voice calls are missing routing decisions more often than expected.",
                "severity": "high",
                "threshold": {
                    "metric": "route_missing_rate",
                    "operator": ">=",
                    "value": 0.1,
                    "window_minutes": 60,
                    "min_sample_size": 1,
                },
                "surface": "voice",
                "domain": "detection",
                "ownership": {"team": "voice-platform", "pager": "ops-voice"},
                "triage_default": {"priority": "investigate_today", "queue": "voice-monitoring"},
                "notification_default": {"channel": "ops", "target": "voice-monitoring"},
                "effective_threshold": {
                    "metric": "route_missing_rate",
                    "operator": ">=",
                    "value": 0.1,
                    "window_minutes": 60,
                    "min_sample_size": 1,
                },
            }
        ],
    }


def test_detection_evaluator_persists_triage_metadata(monkeypatch) -> None:
    from harness.detection.evaluator import evaluate_detection

    created: list[dict[str, Any]] = []

    monkeypatch.setattr("harness.detection.evaluator.get_tenant_config", lambda tenant_id: {})
    monkeypatch.setattr("harness.detection.evaluator.list_jobs", lambda tenant_id=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_scheduler_backlog", lambda tenant_id=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_incidents", lambda tenant_id=None, status=None: [])
    monkeypatch.setattr("harness.detection.evaluator.load_voice_monitor_catalog", lambda: _voice_catalog())
    monkeypatch.setattr(
        "harness.detection.evaluator.list_recent_call_records",
        lambda **_: [
            {
                "tenant_id": "tenant-alpha",
                "call_id": "call-1",
                "extracted_fields": {"urgency_tier": "urgent"},
                "route": "",
                "scorecard_warnings": [],
            }
        ],
    )
    monkeypatch.setattr("harness.detection.evaluator.suppress_duplicate_alert", lambda **kwargs: None)
    monkeypatch.setattr("harness.detection.evaluator.auto_resolve_recovered_alerts", lambda **kwargs: [])

    def _create_alert(payload: dict[str, Any]) -> dict[str, Any]:
        record = {"id": "alert-1", **payload}
        created.append(record)
        return record

    monkeypatch.setattr("harness.detection.evaluator.create_alert_and_sync_incident", _create_alert)
    monkeypatch.setattr(
        "harness.detection.evaluator.notify",
        lambda alert, tenant_config=None: {"alert_id": alert["id"], "delivered": False, "channels": []},
    )
    monkeypatch.setattr(
        "harness.detection.evaluator.dispatch_job_requests",
        lambda **kwargs: SimpleNamespace(dispatched=["voice-builder"], queued=[], blocked=[]),
    )

    results = evaluate_detection(tenant_id="tenant-alpha", window_minutes=15)

    assert len(results) == 1
    assert len(created) == 1
    first = results[0]
    assert first["alert_type"] == "voice_route_missing_spike"
    assert first["metrics"]["detection"]["triage_outcome"] == "investigate"
    assert first["metrics"]["detection"]["notification_outcome"] == "internal_only"
    assert first["metrics"]["detection"]["dedupe_key"] == "tenant-alpha:voice_route_missing_spike"
    assert first["metrics"]["window_minutes"] == 60


def test_detection_evaluator_excludes_unscoped_rows_from_tenant_metrics(monkeypatch) -> None:
    from harness.detection.evaluator import evaluate_detection

    now_iso = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr("harness.detection.evaluator.get_tenant_config", lambda tenant_id: {})
    monkeypatch.setattr("harness.detection.evaluator.list_jobs", lambda tenant_id=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_scheduler_backlog", lambda tenant_id=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_incidents", lambda tenant_id=None, status=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_alerts", lambda tenant_id=None: [])
    monkeypatch.setattr("harness.detection.evaluator.load_voice_monitor_catalog", lambda: _voice_catalog())
    monkeypatch.setattr(
        "harness.detection.evaluator.list_recent_call_records",
        lambda **_: [
            {
                "tenant_id": "tenant-alpha",
                "call_id": "call-1",
                "created_at": now_iso,
                "extracted_fields": {"customer_phone": "5551112222", "urgency_tier": "urgent", "route": "dispatcher"},
                "route": "dispatcher",
            },
            {
                "tenant_id": None,
                "call_id": "call-2",
                "created_at": now_iso,
                "extracted_fields": {"urgency_tier": "urgent"},
                "route": "",
            },
        ],
    )
    monkeypatch.setattr("harness.detection.evaluator.suppress_duplicate_alert", lambda **kwargs: None)
    monkeypatch.setattr("harness.detection.evaluator.auto_resolve_recovered_alerts", lambda **kwargs: [])
    monkeypatch.setattr("harness.detection.evaluator.create_alert_and_sync_incident", lambda payload: {"id": "alert-1", **payload})
    monkeypatch.setattr("harness.detection.evaluator.notify", lambda alert, tenant_config=None: {"alert_id": alert["id"], "delivered": False, "channels": []})
    monkeypatch.setattr("harness.detection.evaluator.dispatch_job_requests", lambda **kwargs: SimpleNamespace(dispatched=[], queued=[], blocked=[]))

    results = evaluate_detection(tenant_id="tenant-alpha", window_minutes=15)

    assert results == []


def test_detection_evaluator_respects_monitor_window_for_breach_calculation(monkeypatch) -> None:
    from harness.detection.evaluator import evaluate_detection

    now = datetime.now(timezone.utc)
    monkeypatch.setattr("harness.detection.evaluator.get_tenant_config", lambda tenant_id: {})
    monkeypatch.setattr("harness.detection.evaluator.list_jobs", lambda tenant_id=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_scheduler_backlog", lambda tenant_id=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_incidents", lambda tenant_id=None, status=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_alerts", lambda tenant_id=None: [])
    monkeypatch.setattr("harness.detection.evaluator.load_voice_monitor_catalog", lambda: _voice_catalog())
    monkeypatch.setattr(
        "harness.detection.evaluator.list_recent_call_records",
        lambda **_: [
            {
                "tenant_id": "tenant-alpha",
                "call_id": "call-stale",
                "created_at": (now - timedelta(hours=2)).isoformat(),
                "extracted_fields": {"urgency_tier": "urgent"},
                "route": "",
            }
        ],
    )
    monkeypatch.setattr("harness.detection.evaluator.suppress_duplicate_alert", lambda **kwargs: None)
    monkeypatch.setattr("harness.detection.evaluator.auto_resolve_recovered_alerts", lambda **kwargs: [])
    monkeypatch.setattr("harness.detection.evaluator.create_alert_and_sync_incident", lambda payload: {"id": "alert-1", **payload})
    monkeypatch.setattr("harness.detection.evaluator.notify", lambda alert, tenant_config=None: {"alert_id": alert["id"], "delivered": False, "channels": []})
    monkeypatch.setattr("harness.detection.evaluator.dispatch_job_requests", lambda **kwargs: SimpleNamespace(dispatched=[], queued=[], blocked=[]))

    results = evaluate_detection(tenant_id="tenant-alpha", window_minutes=15)

    assert results == []


def test_detection_evaluator_stands_down_duplicate_open_issue(monkeypatch) -> None:
    from harness.detection.evaluator import evaluate_detection

    suppressed_metrics: dict[str, Any] = {}

    monkeypatch.setattr("harness.detection.evaluator.get_tenant_config", lambda tenant_id: {})
    monkeypatch.setattr("harness.detection.evaluator.list_jobs", lambda tenant_id=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_scheduler_backlog", lambda tenant_id=None: [])
    monkeypatch.setattr(
        "harness.detection.evaluator.list_incidents",
        lambda tenant_id=None, status=None: [{"incident_key": "tenant-alpha:voice_route_missing_spike", "status": "open"}],
    )
    monkeypatch.setattr("harness.detection.evaluator.load_voice_monitor_catalog", lambda: _voice_catalog())
    monkeypatch.setattr(
        "harness.detection.evaluator.list_recent_call_records",
        lambda **_: [
            {
                "tenant_id": "tenant-alpha",
                "call_id": "call-1",
                "extracted_fields": {"urgency_tier": "urgent"},
                "route": "",
                "scorecard_warnings": [],
            }
        ],
    )
    monkeypatch.setattr("harness.detection.evaluator.auto_resolve_recovered_alerts", lambda **kwargs: [])

    def _suppress_duplicate_alert(**kwargs: Any) -> dict[str, Any]:
        suppressed_metrics.update(kwargs["metrics"])
        return {
            "id": "alert-existing",
            "tenant_id": kwargs["tenant_id"],
            "alert_type": kwargs["alert_type"],
            "severity": "high",
            "status": "open",
            "message": "duplicate detection",
            "metrics": kwargs["metrics"],
        }

    monkeypatch.setattr("harness.detection.evaluator.suppress_duplicate_alert", _suppress_duplicate_alert)
    monkeypatch.setattr(
        "harness.detection.evaluator.create_alert_and_sync_incident",
        lambda payload: (_ for _ in ()).throw(AssertionError("should not create a new alert for stand_down")),
    )
    monkeypatch.setattr(
        "harness.detection.evaluator.notify",
        lambda alert, tenant_config=None: {
            "alert_id": alert["id"],
            "delivered": False,
            "channels": alert["metrics"]["detection"]["channels"],
        },
    )
    monkeypatch.setattr(
        "harness.detection.evaluator.dispatch_job_requests",
        lambda **kwargs: SimpleNamespace(dispatched=[], queued=[], blocked=[]),
    )

    results = evaluate_detection(tenant_id="tenant-alpha", window_minutes=15)

    assert len(results) == 1
    assert suppressed_metrics["detection"]["triage_outcome"] == "stand_down"
    assert suppressed_metrics["detection"]["notification_outcome"] == "silent_stand_down"
    assert results[0]["notification"]["channels"] == []


def test_detection_evaluator_auto_resolves_recovered_detection_alert(monkeypatch) -> None:
    from harness.detection.evaluator import evaluate_detection

    now = datetime.now(timezone.utc)
    existing_alert = {
        "id": "alert-existing",
        "tenant_id": "tenant-alpha",
        "alert_type": "voice_route_missing_spike",
        "severity": "high",
        "status": "open",
        "created_at": (now - timedelta(hours=1)).isoformat(),
        "last_observed_at": (now - timedelta(minutes=30)).isoformat(),
        "metrics": {
            "metric_name": "route_missing_rate",
            "metric_value": 1.0,
            "sample_size": 1,
            "window_minutes": 60,
            "threshold": 0.1,
            "threshold_operator": ">=",
            "min_sample_size": 1,
            "detection": {
                "monitor_id": "voice_route_missing_spike",
                "notification_outcome": "internal_only",
            },
        },
    }

    monkeypatch.setattr("harness.detection.evaluator.get_tenant_config", lambda tenant_id: {})
    monkeypatch.setattr("harness.detection.evaluator.list_jobs", lambda tenant_id=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_scheduler_backlog", lambda tenant_id=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_incidents", lambda tenant_id=None, status=None: [])
    monkeypatch.setattr("harness.detection.evaluator.list_alerts", lambda tenant_id=None: [existing_alert])
    monkeypatch.setattr("harness.detection.evaluator.load_voice_monitor_catalog", lambda: _voice_catalog())
    monkeypatch.setattr(
        "harness.detection.evaluator.list_recent_call_records",
        lambda **_: [
            {
                "tenant_id": "tenant-alpha",
                "call_id": "call-recovered",
                "created_at": now.isoformat(),
                "extracted_fields": {
                    "customer_phone": "5551112222",
                    "urgency_tier": "urgent",
                    "route": "dispatcher",
                },
                "route": "dispatcher",
            }
        ],
    )
    monkeypatch.setattr("harness.detection.evaluator.suppress_duplicate_alert", lambda **kwargs: None)
    monkeypatch.setattr("harness.detection.evaluator.auto_resolve_recovered_alerts", lambda **kwargs: [])
    monkeypatch.setattr(
        "harness.detection.evaluator.create_alert_and_sync_incident",
        lambda payload: (_ for _ in ()).throw(AssertionError("should not create a new alert after recovery")),
    )
    monkeypatch.setattr(
        "harness.detection.evaluator.update_alert_and_sync_incident",
        lambda alert_id, updates: {**existing_alert, **updates, "id": alert_id},
    )
    monkeypatch.setattr("harness.detection.evaluator.notify", lambda alert, tenant_config=None: {"alert_id": alert["id"], "delivered": False, "channels": []})
    monkeypatch.setattr("harness.detection.evaluator.dispatch_job_requests", lambda **kwargs: SimpleNamespace(dispatched=[], queued=[], blocked=[]))

    results = evaluate_detection(tenant_id="tenant-alpha", window_minutes=15)

    assert len(results) == 1
    assert results[0]["status"] == "resolved"
    assert results[0]["resolved_by"] == "system:detection-recovery"
    assert results[0]["metrics"]["recovered_value"] == 0.0
