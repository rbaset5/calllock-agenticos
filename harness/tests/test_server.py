from fastapi.testclient import TestClient

from harness.server import app


def test_process_call_endpoint_executes_customer_analyst() -> None:
    client = TestClient(app)
    response = client.post(
        "/process-call",
        json={
            "call_id": "call-1",
            "tenant_id": "tenant-alpha",
            "problem_description": "No heat and customer is upset.",
            "transcript": "Customer says there is no heat tonight and they are frustrated.",
            "tenant_config": {"allowed_tools": ["notify_dispatch"]},
            "compliance_rules": [{"id": "allow-default", "target": "*", "effect": "allow", "reason": "default"}],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_verdict"] == "allow"
    assert payload["verification_passed"] is True
    assert payload["output"]["lead_route"] == "dispatcher"


def test_process_call_endpoint_uses_local_seed_defaults() -> None:
    client = TestClient(app)
    response = client.post(
        "/process-call",
        json={
            "call_id": "call-2",
            "tenant_id": "tenant-alpha",
            "problem_description": "AC not cooling",
            "transcript": "Customer says the AC is not cooling.",
        },
    )
    assert response.status_code == 200
    assert response.json()["policy_verdict"] == "allow"


def test_event_endpoint_accepts_inngest_style_envelope() -> None:
    client = TestClient(app)
    response = client.post(
        "/events/process-call",
        json={
            "name": "harness/process-call",
            "data": {
                "call_id": "call-3",
                "tenant_id": "tenant-alpha",
                "problem_description": "No heat",
                "transcript": "Customer says there is no heat.",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["verification_passed"] is True


def test_event_endpoint_rejects_unknown_event_name() -> None:
    client = TestClient(app)
    response = client.post(
        "/events/process-call",
        json={
            "name": "unknown/event",
            "data": {
                "call_id": "call-4",
                "tenant_id": "tenant-alpha",
            },
        },
    )
    assert response.status_code == 400


def test_event_endpoint_requires_secret_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_EVENT_SECRET", "test-secret")
    client = TestClient(app)
    response = client.post(
        "/events/process-call",
        json={
            "name": "harness/process-call",
            "data": {
                "call_id": "call-5",
                "tenant_id": "tenant-alpha",
            },
        },
    )
    assert response.status_code == 401

    authorized = client.post(
        "/events/process-call",
        headers={"Authorization": "Bearer test-secret"},
        json={
            "name": "harness/process-call",
            "data": {
                "call_id": "call-6",
                "tenant_id": "tenant-alpha",
            },
        },
    )
    assert authorized.status_code == 200
