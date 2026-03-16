from pathlib import Path

from harness.jobs.dispatch import dispatch_job_requests
from harness.nodes.persist import persist_node
from harness.resilience.recovery_journal import get_recovery_entry, list_recovery_entries
from harness.resilience.replayer import replay_recovery_entry


def test_persist_node_writes_recovery_entry_on_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CALLLOCK_RECOVERY_ROOT", str(tmp_path))
    monkeypatch.setattr("harness.nodes.persist.persist_run_record", lambda record: (_ for _ in ()).throw(RuntimeError("supabase down")))
    result = persist_node(
        {
            "tenant_id": "tenant-alpha",
            "run_id": "run-1",
            "worker_id": "customer-analyst",
            "policy_decision": {"verdict": "allow"},
            "worker_output": {"summary": "ok"},
            "verification": {"passed": True, "verdict": "pass"},
        }
    )
    assert result["persistence"]["persistence_status"] == "degraded"
    target = Path(result["persistence"]["recovery_path"])
    assert target.exists()


def test_job_dispatch_records_recovery_path_when_inngest_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CALLLOCK_RECOVERY_ROOT", str(tmp_path))
    monkeypatch.setenv("INNGEST_EVENT_URL", "https://example.invalid")

    class FakeHttpx:
        @staticmethod
        def post(*args, **kwargs):
            raise RuntimeError("inngest unavailable")

    monkeypatch.setattr("harness.jobs.dispatch.httpx", FakeHttpx)
    jobs = dispatch_job_requests(
        [{"idempotency_key": "job-1", "job_type": "follow_up"}],
        tenant_id="00000000-0000-0000-0000-000000000001",
        origin_worker_id="customer-analyst",
        origin_run_id="run-1",
    )
    assert jobs[0]["dispatch"]["dispatched"] is False
    assert "recovery_path" in jobs[0]["dispatch"]


def test_recovery_entries_can_be_listed_and_replayed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CALLLOCK_RECOVERY_ROOT", str(tmp_path))
    monkeypatch.setattr("harness.nodes.persist.persist_run_record", lambda record: (_ for _ in ()).throw(RuntimeError("supabase down")))
    result = persist_node(
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "run_id": "run-replay",
            "worker_id": "customer-analyst",
            "policy_decision": {"verdict": "allow"},
            "worker_output": {"summary": "ok"},
            "verification": {"passed": True, "verdict": "pass"},
        }
    )
    recovery_entries = list_recovery_entries("persist-failure")
    assert len(recovery_entries) == 1
    entry = get_recovery_entry(recovery_entries[0]["id"])
    replayed = replay_recovery_entry(entry["id"])
    assert replayed["replayed"] is True
    assert replayed["persisted"]["job"]["idempotency_key"] == "run-replay"
