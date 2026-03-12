from __future__ import annotations

from typing import Any

from db.repository import persist_run_record


def build_persist_record(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "tenant_id": state.get("tenant_id"),
        "run_id": state.get("run_id"),
        "worker_id": state.get("worker_id"),
        "status": "verified" if state.get("verification", {}).get("passed") else "blocked",
        "policy_verdict": state.get("policy_decision", {}).get("verdict"),
        "output": state.get("worker_output"),
    }


def persist_node(state: dict[str, Any]) -> dict[str, Any]:
    record = build_persist_record(state)
    return {"persistence": persist_run_record(record)}
