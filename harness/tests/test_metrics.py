import logging

import pytest

from harness.metrics import MetricsEmitter


def test_emit_returns_none_on_success() -> None:
    emitter = MetricsEmitter()
    result = emitter.emit(
        category="policy_gate",
        event_name="blocked",
        tenant_id="tenant-alpha",
        run_id="run-1",
    )
    assert result is None


def test_emit_skips_write_when_category_is_none(caplog) -> None:
    emitter = MetricsEmitter()
    with caplog.at_level(logging.WARNING, logger="harness.metrics"):
        emitter.emit(category=None, event_name="blocked")
    assert "category" in caplog.text.lower()


def test_emit_skips_write_when_event_name_is_none(caplog) -> None:
    emitter = MetricsEmitter()
    with caplog.at_level(logging.WARNING, logger="harness.metrics"):
        emitter.emit(category="policy_gate", event_name=None)
    assert "event_name" in caplog.text.lower()


def _make_emitter_with_failing_post(monkeypatch, exception):
    """Helper: configure emitter to raise the given exception on post."""
    import httpx

    def _fail_post(*args, **kwargs):
        raise exception

    emitter = MetricsEmitter()
    monkeypatch.setattr(httpx, "post", _fail_post)
    monkeypatch.setenv("SUPABASE_URL", "http://fake")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")
    return emitter


def test_emit_swallows_timeout_exception(monkeypatch, caplog) -> None:
    """Emitter must never crash the pipeline on timeout."""
    import httpx

    emitter = _make_emitter_with_failing_post(monkeypatch, httpx.TimeoutException("connection timed out"))
    with caplog.at_level(logging.ERROR, logger="harness.metrics"):
        result = emitter.emit(category="verification", event_name="block", tenant_id="t-1", run_id="r-1")
    assert result is None
    assert "timeout" in caplog.text.lower() or "timed out" in caplog.text.lower()


def test_emit_swallows_connect_error(monkeypatch, caplog) -> None:
    """Emitter must never crash the pipeline on connection refused."""
    import httpx

    emitter = _make_emitter_with_failing_post(monkeypatch, httpx.ConnectError("connection refused"))
    with caplog.at_level(logging.ERROR, logger="harness.metrics"):
        result = emitter.emit(category="policy_gate", event_name="blocked", tenant_id="t-1")
    assert result is None
    assert "connect" in caplog.text.lower() or "refused" in caplog.text.lower()


def test_emit_swallows_http_status_error(monkeypatch, caplog) -> None:
    """Emitter must never crash the pipeline on 5xx response."""
    import httpx

    response = httpx.Response(500, request=httpx.Request("POST", "http://fake"))
    emitter = _make_emitter_with_failing_post(monkeypatch, httpx.HTTPStatusError("server error", request=response.request, response=response))
    with caplog.at_level(logging.ERROR, logger="harness.metrics"):
        result = emitter.emit(category="job_failure", event_name="timeout", tenant_id="t-1")
    assert result is None
    assert "error" in caplog.text.lower()


VALID_CATEGORIES = ["policy_gate", "verification", "job_failure", "external_service"]


@pytest.mark.parametrize("category", VALID_CATEGORIES)
def test_emit_accepts_all_valid_categories(category: str) -> None:
    emitter = MetricsEmitter()
    result = emitter.emit(category=category, event_name="test")
    assert result is None


# --- Snapshot endpoint tests ---

from fastapi.testclient import TestClient

from harness.server import app


def test_snapshot_returns_empty_window() -> None:
    client = TestClient(app)
    response = client.get("/metrics/snapshot", params={"category": "policy_gate"})
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "policy_gate"
    assert data["window_minutes"] == 60
    assert data["total_count"] == 0
    assert data["groups"] == []
    assert data["oldest_event"] is None
    assert data["newest_event"] is None
    assert "applied_filters" in data


def test_snapshot_rejects_invalid_category() -> None:
    client = TestClient(app)
    response = client.get("/metrics/snapshot", params={"category": "invalid"})
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "invalid_category"
    assert "detail" in data


def test_snapshot_rejects_invalid_group_by() -> None:
    client = TestClient(app)
    response = client.get(
        "/metrics/snapshot",
        params={"category": "policy_gate", "group_by": "dimensions"},
    )
    assert response.status_code == 400


def test_snapshot_rejects_window_out_of_range() -> None:
    client = TestClient(app)
    response = client.get(
        "/metrics/snapshot",
        params={"category": "policy_gate", "window": "2000"},
    )
    assert response.status_code == 400


def test_snapshot_requires_category() -> None:
    client = TestClient(app)
    response = client.get("/metrics/snapshot")
    assert response.status_code == 400


def test_snapshot_requires_auth_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_EVENT_SECRET", "test-secret")
    client = TestClient(app)
    response = client.get("/metrics/snapshot", params={"category": "policy_gate"})
    assert response.status_code == 401

    authorized = client.get(
        "/metrics/snapshot",
        params={"category": "policy_gate"},
        headers={"Authorization": "Bearer test-secret"},
    )
    assert authorized.status_code == 200


def test_snapshot_returns_503_on_rpc_failure(monkeypatch) -> None:
    """Snapshot must return 503 when the RPC call to Supabase fails."""
    import httpx as _httpx

    monkeypatch.setenv("SUPABASE_URL", "http://fake")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")

    def _fail_post(*args, **kwargs):
        raise _httpx.ConnectError("connection refused")

    monkeypatch.setattr(_httpx, "post", _fail_post)
    client = TestClient(app)
    response = client.get("/metrics/snapshot", params={"category": "policy_gate"})
    assert response.status_code == 503
    data = response.json()
    assert data["error"] == "upstream_unavailable"


def test_snapshot_auth_error_shape(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_EVENT_SECRET", "test-secret")
    client = TestClient(app)
    response = client.get("/metrics/snapshot", params={"category": "policy_gate"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "auth_failed"
    assert "detail" in data


def test_snapshot_includes_applied_filters() -> None:
    client = TestClient(app)
    response = client.get(
        "/metrics/snapshot",
        params={
            "category": "verification",
            "tenant_id": "tenant-alpha",
            "group_by": "event_name",
            "window": "30",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["applied_filters"]["tenant_id"] == "tenant-alpha"
    assert data["applied_filters"]["group_by"] == "event_name"
    assert data["window_minutes"] == 30
