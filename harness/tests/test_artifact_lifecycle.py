import pytest

from db.repository import create_artifact, update_artifact_lifecycle


def test_artifact_lifecycle_valid_transitions(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CALLLOCK_ARTIFACT_ROOT", str(tmp_path))
    artifact = create_artifact(
        {
            "tenant_id": "tenant-alpha",
            "run_id": "run-1",
            "created_by": "customer-analyst",
            "artifact_type": "run_record",
            "payload": {"summary": "ok"},
        }
    )
    assert update_artifact_lifecycle(artifact["id"], "active", tenant_id="tenant-alpha")["lifecycle_state"] == "active"
    assert update_artifact_lifecycle(artifact["id"], "archived", tenant_id="tenant-alpha")["lifecycle_state"] == "archived"


def test_artifact_lifecycle_rejects_skipped_transition(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CALLLOCK_ARTIFACT_ROOT", str(tmp_path))
    artifact = create_artifact(
        {
            "tenant_id": "tenant-alpha",
            "run_id": "run-1",
            "created_by": "customer-analyst",
            "artifact_type": "run_record",
            "payload": {"summary": "ok"},
        }
    )
    with pytest.raises(ValueError):
        update_artifact_lifecycle(artifact["id"], "archived", tenant_id="tenant-alpha")
