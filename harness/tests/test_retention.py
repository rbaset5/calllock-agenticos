from datetime import datetime, timedelta, timezone
from pathlib import Path

from db.repository import create_artifact, create_audit_log, save_customer_content
from harness.retention import run_retention_pass


def test_retention_archives_and_deletes_aged_records(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CALLLOCK_TRACE_ROOT", str(tmp_path / "traces"))
    monkeypatch.setenv("CALLLOCK_RECOVERY_ROOT", str(tmp_path / "recovery"))

    old_created = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    archived = create_artifact(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "run_id": "run-old-archived",
            "created_by": "customer-analyst",
            "artifact_type": "run_record",
            "payload": {"ok": True},
            "created_at": old_created,
            "lifecycle_state": "archived",
        }
    )
    active = create_artifact(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "run_id": "run-old-active",
            "created_by": "customer-analyst",
            "artifact_type": "run_record",
            "payload": {"ok": True},
            "created_at": old_created,
            "lifecycle_state": "active",
        }
    )
    save_customer_content(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "call_id": "call-old",
            "consent_granted": True,
            "raw_transcript": "old",
            "sanitized_transcript": "old",
            "structured_content": {},
            "created_at": old_created,
        }
    )
    create_audit_log(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "action_type": "test.old",
            "actor_id": "tester",
            "reason": "old",
            "created_at": old_created,
        }
    )

    report = run_retention_pass(tenant_id="00000000-0000-0000-0000-000000000001")
    tenant_report = report["tenants"][0]
    assert tenant_report["archived_artifacts"] >= 1
    assert tenant_report["deleted_artifacts"] >= 1
    assert tenant_report["deleted_customer_content"] >= 1
    assert tenant_report["deleted_audit_logs"] >= 1


def test_retention_prunes_local_trace_and_recovery_files(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CALLLOCK_TRACE_ROOT", str(tmp_path / "traces"))
    monkeypatch.setenv("CALLLOCK_RECOVERY_ROOT", str(tmp_path / "recovery"))
    trace_dir = tmp_path / "traces" / "00000000-0000-0000-0000-000000000001"
    trace_dir.mkdir(parents=True)
    recovery_dir = tmp_path / "recovery" / "00000000-0000-0000-0000-000000000001"
    recovery_dir.mkdir(parents=True)
    old_timestamp = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    (trace_dir / "local-traces.jsonl").write_text(
        '{"timestamp":"%s","payload":{"x":1}}\n' % old_timestamp
    )
    (recovery_dir / "persist-failure.jsonl").write_text(
        '{"created_at":"%s","payload":{"x":1}}\n' % old_timestamp
    )

    report = run_retention_pass(dry_run=False)
    tenant_report = report["tenants"][0]
    assert tenant_report["local_traces"]["deleted"] == 1
    assert tenant_report["local_recovery"]["persist-failure.jsonl"]["deleted"] == 1
