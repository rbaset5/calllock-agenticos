from __future__ import annotations

import datetime
from copy import deepcopy
import logging
from typing import Any

from harness.approvals import maybe_create_approval_request
from db.repository import create_artifact, persist_run_record, upsert_agent_report
from harness.resilience.recovery_journal import write_recovery_entry

GUARDIAN_AGENTS = {"eng-ai-voice", "eng-app", "eng-product-qa"}
logger = logging.getLogger(__name__)


def build_persist_record(state: dict[str, Any]) -> dict[str, Any]:
    verification = state.get("verification", {})
    return {
        "tenant_id": state.get("tenant_id"),
        "run_id": state.get("run_id"),
        "worker_id": state.get("worker_id"),
        "status": "verified" if verification.get("passed") else verification.get("verdict", "blocked"),
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
        if state.get("worker_id") in GUARDIAN_AGENTS:
            worker_output = state.get("worker_output", {})
            report_status = "green"
            if worker_output.get("violations") or worker_output.get("failures"):
                report_status = "red"
            elif worker_output.get("warnings"):
                report_status = "yellow"

            try:
                upsert_agent_report(
                    {
                        "agent_id": state["worker_id"],
                        "report_type": state.get("task", {}).get("task_context", {}).get("task_type", "health-check"),
                        "report_date": datetime.date.today().isoformat(),
                        "status": report_status,
                        "payload": worker_output,
                        "tenant_id": state["tenant_id"],
                    }
                )
            except Exception:
                logger.exception("Failed to persist guardian agent report", extra={"worker_id": state.get("worker_id")})
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
