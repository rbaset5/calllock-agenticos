from __future__ import annotations

from harness.nodes.persist import build_persist_record


def test_build_persist_record_sets_quarantined_status() -> None:
    record = build_persist_record(
        {
            "tenant_id": "tenant-1",
            "run_id": "run-1",
            "worker_id": "eng-ai-voice",
            "verification": {"passed": True, "verdict": "pass"},
            "guardian_gate": {"quarantine": True, "gate_failures": ["missing_tenant_id"]},
        }
    )

    assert record["status"] == "quarantined"
    assert record["quarantine"] is True


def test_build_persist_record_includes_gate_failures() -> None:
    record = build_persist_record(
        {
            "tenant_id": "tenant-1",
            "run_id": "run-1",
            "worker_id": "eng-ai-voice",
            "verification": {"passed": False, "verdict": "retry"},
            "guardian_gate": {
                "quarantine": True,
                "gate_failures": ["verification_verdict=retry", "missing_tenant_id"],
            },
        }
    )

    assert record["gate_failures"] == [
        "verification_verdict=retry",
        "missing_tenant_id",
    ]


def test_build_persist_record_marks_verified_when_not_quarantined() -> None:
    record = build_persist_record(
        {
            "tenant_id": "tenant-1",
            "run_id": "run-1",
            "worker_id": "eng-ai-voice",
            "verification": {"passed": True, "verdict": "pass"},
            "guardian_gate": {"quarantine": False, "gate_failures": []},
        }
    )

    assert record["status"] == "verified"
    assert record["quarantine"] is False
