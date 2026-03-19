from __future__ import annotations

from copy import deepcopy
from typing import Any

from harness.approvals import maybe_create_approval_request
from db.repository import create_artifact, persist_run_record
from harness.resilience.recovery_journal import write_recovery_entry


def build_persist_record(state: dict[str, Any]) -> dict[str, Any]:
    verification = state.get("verification", {})
    guardian_gate = state.get("guardian_gate", {})
    quarantined = guardian_gate.get("quarantine", False)

    if quarantined:
        status = "quarantined"
    elif verification.get("passed"):
        status = "verified"
    else:
        status = verification.get("verdict", "blocked")

    return {
        "tenant_id": state.get("tenant_id"),
        "run_id": state.get("run_id"),
        "worker_id": state.get("worker_id"),
        "status": status,
        "quarantine": quarantined,
        "gate_failures": guardian_gate.get("gate_failures", []),
        "policy_verdict": state.get("policy_decision", {}).get("verdict"),
        "output": state.get("worker_output"),
        "verification": verification,
        "jobs": state.get("jobs", []),
    }


def persist_node(state: dict[str, Any]) -> dict[str, Any]:
    record = build_persist_record(state)
    approval_request = maybe_create_approval_request(state)
    try:
        persisted = persist_run_record(record)
        artifact = create_artifact(
            {
                "tenant_id": state.get("tenant_id"),
                "run_id": state.get("run_id"),
                "created_by": state.get("worker_id"),
                "artifact_type": "run_record",
                "source_job_id": persisted.get("job", {}).get("id"),
                "payload": deepcopy(persisted),
                "lineage": {"worker_id": state.get("worker_id"), "policy_verdict": state.get("policy_decision", {}).get("verdict")},
            }
        )
        persisted["artifact"] = artifact
        if approval_request is not None:
            persisted["approval_request"] = approval_request
        return {"persistence": persisted}
    except Exception as exc:
        recovery_path = write_recovery_entry(
            "persist-failure",
            {"record": record, "tenant_id": state.get("tenant_id"), "run_id": state.get("run_id"), "error": str(exc)},
        )
        return {
            "persistence": {
                **record,
                "approval_request": approval_request,
                "recovery_path": recovery_path,
                "persistence_status": "degraded",
                "error": str(exc),
            }
        }
