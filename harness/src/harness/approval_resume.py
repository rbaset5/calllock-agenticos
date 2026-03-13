from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from db.repository import get_tenant_config, update_incident_workflow
from harness.incident_notifications import notify_incident
from harness.graphs.supervisor import run_supervisor
from harness.nodes.persist import persist_node


def continue_approved_request(approval_request: dict[str, Any], *, actor_id: str, resolution_notes: str) -> dict[str, Any]:
    request_type = approval_request["request_type"]
    if request_type == "verification":
        resume_state = deepcopy(approval_request.get("payload", {}).get("resume_state", {}))
        if not resume_state:
            raise ValueError("Approval request does not contain resumable state")
        resume_state["approval_context"] = {
            "approval_request_id": approval_request["id"],
            "approved_by": actor_id,
            "resolution_notes": resolution_notes,
        }
        resume_state["verification"] = {
            "passed": True,
            "verdict": "pass",
            "reasons": [f"Approved by {actor_id}: {resolution_notes}"],
            "findings": [],
        }
        persisted = persist_node(resume_state)["persistence"]
        return {"mode": "verification_resume", "persistence": persisted}

    if request_type == "policy":
        resume_state = deepcopy(approval_request.get("payload", {}).get("resume_state", {}))
        if not resume_state:
            raise ValueError("Approval request does not contain resumable state")
        resume_state["approval_context"] = {
            "approval_request_id": approval_request["id"],
            "approved_by": actor_id,
            "resolution_notes": resolution_notes,
        }
        task = deepcopy(resume_state.get("task", {}))
        task["approval_override"] = True
        task["approval_override_notes"] = resolution_notes
        resumed = run_supervisor({**resume_state, "task": task})
        return {"mode": "policy_resume", "state": resumed}

    if request_type == "incident_workflow":
        incident_id = approval_request.get("payload", {}).get("incident_id")
        incident_updates = deepcopy(approval_request.get("payload", {}).get("incident_updates", {}))
        if not incident_id or not incident_updates:
            raise ValueError("Incident workflow approval is missing incident continuation data")
        timestamp = datetime.now(timezone.utc).isoformat()
        assignment_history = list(incident_updates.get("assignment_history", []))
        assignment_history_entry = assignment_history[-1] if assignment_history else None
        if isinstance(assignment_history_entry, dict):
            assignment_history_entry = {**assignment_history_entry, "at": timestamp}
        updated = update_incident_workflow(
            incident_id,
            workflow_status=incident_updates.get("workflow_status", "new"),
            actor_id=actor_id,
            assigned_to=incident_updates.get("assigned_to"),
            operator_notes=incident_updates.get("operator_notes", resolution_notes),
            last_assignment_reason=incident_updates.get("last_assignment_reason"),
            assignment_history_entry=assignment_history_entry if isinstance(assignment_history_entry, dict) else None,
            now_iso=timestamp,
        )
        if updated.get("assigned_to") and updated.get("workflow_status") in {"acknowledged", "investigating"}:
            tenant_config = get_tenant_config(updated["tenant_id"]) if updated.get("tenant_id") else {}
            updated["notification"] = notify_incident(updated, tenant_config, reminder=False)
        return {"mode": "incident_workflow_resume", "incident": updated}

    raise ValueError(f"Unsupported approval request type: {request_type}")
