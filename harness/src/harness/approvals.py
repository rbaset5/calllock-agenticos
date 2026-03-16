from __future__ import annotations

from typing import Any

from db.repository import create_approval_request, list_approval_requests, update_approval_request


def maybe_create_approval_request(state: dict[str, Any]) -> dict[str, Any] | None:
    policy_verdict = state.get("policy_decision", {}).get("verdict")
    verification_verdict = state.get("verification", {}).get("verdict")
    if policy_verdict != "escalate" and verification_verdict != "escalate":
        return None

    reason = "; ".join(state.get("verification", {}).get("reasons", []) or state.get("policy_decision", {}).get("reasons", []))
    return create_approval_request(
        {
            "tenant_id": state.get("tenant_id"),
            "run_id": state.get("run_id"),
            "worker_id": state.get("worker_id"),
            "status": "pending",
            "reason": reason or "Approval required",
            "requested_by": "harness",
            "request_type": "verification" if verification_verdict == "escalate" else "policy",
            "payload": {
                "policy_decision": state.get("policy_decision"),
                "verification": state.get("verification"),
                "worker_output": state.get("worker_output"),
                "approval_boundaries": state.get("task", {}).get("worker_spec", {}).get("approval_boundaries", []),
                "resume_state": {
                    "tenant_id": state.get("tenant_id"),
                    "run_id": state.get("run_id"),
                    "worker_id": state.get("worker_id"),
                    "task": state.get("task", {}),
                    "tool_name": state.get("tool_name"),
                    "tool_grants": state.get("tool_grants", []),
                    "context_items": state.get("context_items", []),
                    "context_budget_remaining": state.get("context_budget_remaining"),
                    "policy_decision": state.get("policy_decision"),
                    "worker_output": state.get("worker_output"),
                    "verification": state.get("verification"),
                    "jobs": state.get("jobs", []),
                    "retry_count": state.get("retry_count", 0),
                },
            },
        }
    )


def resolve_approval_request(approval_id: str, *, status: str, actor_id: str, resolution_notes: str) -> dict[str, Any]:
    return update_approval_request(
        approval_id,
        {
            "status": status,
            "resolved_by": actor_id,
            "resolution_notes": resolution_notes,
        },
    )


def approvals_for_api(*, tenant_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    return list_approval_requests(tenant_id=tenant_id, status=status)
