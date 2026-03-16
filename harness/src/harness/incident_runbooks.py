from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from harness.incident_classification import incident_skill_lookup_keys


def _normalize_steps(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized_steps: list[dict[str, Any]] = []
    for index, step in enumerate(value, start=1):
        if isinstance(step, str) and step.strip():
            normalized_steps.append(
                {
                    "step_id": f"step-{index}",
                    "title": step.strip(),
                    "required": True,
                    "depends_on": [],
                    "parallel_group": None,
                }
            )
            continue
        if not isinstance(step, dict):
            continue
        title = step.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        depends_on = step.get("depends_on", [])
        if not isinstance(depends_on, list):
            depends_on = []
        normalized_steps.append(
            {
                "step_id": step.get("step_id") if isinstance(step.get("step_id"), str) and step.get("step_id") else f"step-{index}",
                "title": title.strip(),
                "required": bool(step.get("required", True)),
                "depends_on": [int(item) for item in depends_on if isinstance(item, int) and item >= 1],
                "parallel_group": step.get("parallel_group") if isinstance(step.get("parallel_group"), str) and step.get("parallel_group") else None,
            }
        )
    return normalized_steps


def _normalize_step_status(value: Any) -> str:
    if isinstance(value, str) and value.strip().lower() in {"pending", "completed"}:
        return value.strip().lower()
    return "pending"


def _parse_iso(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _claim_is_active(item: dict[str, Any], *, now: datetime) -> bool:
    expires_at = _parse_iso(item.get("claim_expires_at"))
    claimed_by = item.get("claimed_by")
    if not isinstance(claimed_by, str) or not claimed_by:
        return False
    if expires_at is None:
        return True
    return expires_at > now


def _normalize_required_statuses(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    statuses: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            lowered = item.strip().lower()
            if lowered not in statuses:
                statuses.append(lowered)
    return statuses


def _normalize_approval_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"required_workflow_statuses": []}
    return {
        "required_workflow_statuses": _normalize_required_statuses(value.get("required_workflow_statuses")),
        "notes": value.get("notes", "") if isinstance(value.get("notes"), str) else "",
    }


def _normalize_completion_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"required_workflow_statuses": []}
    return {
        "required_workflow_statuses": _normalize_required_statuses(value.get("required_workflow_statuses")),
        "notes": value.get("notes", "") if isinstance(value.get("notes"), str) else "",
    }


def resolve_incident_runbook(incident: dict[str, Any], tenant_config: dict[str, Any] | None = None) -> dict[str, Any]:
    configured = (tenant_config or {}).get("incident_runbooks", {})
    if not isinstance(configured, dict):
        configured = {}

    for lookup_key in incident_skill_lookup_keys(
        incident_type=incident.get("alert_type"),
        incident_category=incident.get("incident_category"),
        remediation_category=incident.get("remediation_category"),
        incident_domain=incident.get("incident_domain"),
        alert_type=incident.get("alert_type"),
    ):
        candidate = configured.get(lookup_key)
        if not isinstance(candidate, dict):
            continue
        return {
            "runbook_id": candidate.get("runbook_id") or lookup_key,
            "runbook_title": candidate.get("title") or lookup_key.replace("_", " ").title(),
            "runbook_steps": _normalize_steps(candidate.get("steps")),
            "completion_policy": _normalize_completion_policy(candidate.get("completion_policy")),
            "approval_policy": _normalize_approval_policy(candidate.get("approval_policy")),
        }

    fallback_title = incident.get("incident_category") or incident.get("alert_type") or "generic_incident"
    return {
        "runbook_id": None,
        "runbook_title": fallback_title.replace("_", " ").title() if isinstance(fallback_title, str) else "Generic Incident",
        "runbook_steps": [],
        "completion_policy": {"required_workflow_statuses": []},
        "approval_policy": {"required_workflow_statuses": []},
    }


def _apply_dependency_state(progress: list[dict[str, Any]]) -> list[dict[str, Any]]:
    completed_indexes = {
        int(item.get("step_index"))
        for item in progress
        if isinstance(item, dict) and item.get("status") == "completed" and isinstance(item.get("step_index"), int)
    }
    updated: list[dict[str, Any]] = []
    for item in progress:
        if not isinstance(item, dict):
            continue
        depends_on = [int(dep) for dep in item.get("depends_on", []) if isinstance(dep, int) and dep >= 1]
        blocked_by = [dep for dep in depends_on if dep not in completed_indexes]
        updated.append(
            {
                **item,
                "blocked_by": blocked_by,
                "is_blocked": bool(blocked_by),
            }
        )
    return updated


def build_runbook_progress(
    steps: list[dict[str, Any]],
    *,
    existing_progress: list[dict[str, Any]] | None = None,
    reset: bool = False,
) -> list[dict[str, Any]]:
    progress_by_step_id: dict[str, dict[str, Any]] = {}
    if not reset and isinstance(existing_progress, list):
        for item in existing_progress:
            if not isinstance(item, dict):
                continue
            step_id = item.get("step_id")
            if isinstance(step_id, str) and step_id:
                progress_by_step_id[step_id] = item

    progress: list[dict[str, Any]] = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        title = step.get("title")
        if not isinstance(title, str) or not title:
            continue
        step_id = step.get("step_id") if isinstance(step.get("step_id"), str) and step.get("step_id") else f"step-{index}"
        existing = progress_by_step_id.get(step_id, {})
        status = _normalize_step_status(existing.get("status"))
        progress.append(
            {
                "step_id": step_id,
                "step_index": index,
                "title": title,
                "required": bool(step.get("required", True)),
                "depends_on": [int(item) for item in step.get("depends_on", []) if isinstance(item, int) and item >= 1],
                "parallel_group": step.get("parallel_group") if isinstance(step.get("parallel_group"), str) and step.get("parallel_group") else None,
                "step_revision": int(existing.get("step_revision", 1)) if isinstance(existing.get("step_revision"), int) else 1,
                "status": status,
                "assigned_to": existing.get("assigned_to") if isinstance(existing.get("assigned_to"), str) else None,
                "claimed_by": existing.get("claimed_by") if isinstance(existing.get("claimed_by"), str) else None,
                "claimed_at": existing.get("claimed_at") if isinstance(existing.get("claimed_at"), str) else None,
                "claim_expires_at": existing.get("claim_expires_at") if isinstance(existing.get("claim_expires_at"), str) else None,
                "completed_at": existing.get("completed_at") if status == "completed" else None,
                "completed_by": existing.get("completed_by") if status == "completed" else None,
                "notes": existing.get("notes", "") if isinstance(existing.get("notes"), str) else "",
                "blocked_by": [],
                "is_blocked": False,
            }
        )
    return _apply_dependency_state(progress)


def summarize_runbook_progress(progress: list[dict[str, Any]] | None) -> dict[str, int]:
    if not isinstance(progress, list):
        return {
            "total_steps": 0,
            "completed_steps": 0,
            "pending_steps": 0,
            "required_steps": 0,
            "required_completed_steps": 0,
            "required_pending_steps": 0,
            "optional_steps": 0,
            "optional_pending_steps": 0,
            "blocked_steps": 0,
        }
    total_steps = len(progress)
    completed_steps = sum(1 for item in progress if isinstance(item, dict) and item.get("status") == "completed")
    required_steps = sum(1 for item in progress if isinstance(item, dict) and item.get("required", True))
    required_completed_steps = sum(
        1 for item in progress if isinstance(item, dict) and item.get("required", True) and item.get("status") == "completed"
    )
    optional_steps = max(total_steps - required_steps, 0)
    return {
        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "pending_steps": max(total_steps - completed_steps, 0),
        "required_steps": required_steps,
        "required_completed_steps": required_completed_steps,
        "required_pending_steps": max(required_steps - required_completed_steps, 0),
        "optional_steps": optional_steps,
        "optional_pending_steps": sum(
            1 for item in progress if isinstance(item, dict) and not item.get("required", True) and item.get("status") != "completed"
        ),
        "blocked_steps": sum(1 for item in progress if isinstance(item, dict) and item.get("is_blocked")),
    }


def build_runbook_execution_plan(progress: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not isinstance(progress, list):
        return {
            "next_runnable_steps": [],
            "blocked_steps": [],
            "completed_steps": [],
            "parallel_groups": {},
        }
    indexed_steps = {
        int(item.get("step_index")): item
        for item in progress
        if isinstance(item, dict) and isinstance(item.get("step_index"), int)
    }
    next_runnable_steps: list[dict[str, Any]] = []
    blocked_steps: list[dict[str, Any]] = []
    completed_steps: list[dict[str, Any]] = []
    parallel_groups: dict[str, list[dict[str, Any]]] = {}
    for item in progress:
        if not isinstance(item, dict):
            continue
        step_view = {
            "step_index": item.get("step_index"),
            "title": item.get("title"),
            "required": item.get("required", True),
            "parallel_group": item.get("parallel_group"),
            "assigned_to": item.get("assigned_to"),
            "claimed_by": item.get("claimed_by"),
            "claim_expires_at": item.get("claim_expires_at"),
        }
        if item.get("status") == "completed":
            completed_steps.append(step_view)
            continue
        if item.get("is_blocked"):
            waiting_on_indexes = [int(dep) for dep in item.get("blocked_by", []) if isinstance(dep, int)]
            blocked_steps.append(
                {
                    **step_view,
                    "waiting_on_indexes": waiting_on_indexes,
                    "waiting_on_titles": [
                        indexed_steps.get(dep, {}).get("title")
                        for dep in waiting_on_indexes
                        if isinstance(indexed_steps.get(dep, {}).get("title"), str)
                    ],
                }
            )
            continue
        next_runnable_steps.append(step_view)
        parallel_group = item.get("parallel_group")
        if isinstance(parallel_group, str) and parallel_group:
            parallel_groups.setdefault(parallel_group, []).append(step_view)
    return {
        "next_runnable_steps": next_runnable_steps,
        "blocked_steps": blocked_steps,
        "completed_steps": completed_steps,
        "parallel_groups": parallel_groups,
    }


def apply_runbook_step_update(
    incident: dict[str, Any],
    *,
    step_index: int,
    status: str,
    actor_id: str,
    note: str = "",
    now_iso: str | None = None,
) -> dict[str, Any]:
    if step_index < 1:
        raise IndexError("step_index must be >= 1")
    progress = incident.get("runbook_progress", [])
    if not isinstance(progress, list):
        progress = []
    if step_index > len(progress):
        raise IndexError("step_index is out of range")

    timestamp = now_iso or datetime.now(timezone.utc).isoformat()
    normalized_status = _normalize_step_status(status)
    target_step = next(
        (item for item in progress if isinstance(item, dict) and item.get("step_index") == step_index),
        None,
    )
    if target_step is None:
        raise IndexError("step_index is out of range")
    if normalized_status == "completed" and target_step.get("is_blocked"):
        raise ValueError(f"step {step_index} is blocked by dependencies: {target_step.get('blocked_by', [])}")

    updated_progress: list[dict[str, Any]] = []
    for item in progress:
        if not isinstance(item, dict):
            continue
        if item.get("step_index") != step_index:
            updated_progress.append(item)
            continue
        updated_progress.append(
            {
                **item,
                "step_revision": int(item.get("step_revision", 1)) + 1,
                "status": normalized_status,
                "claimed_by": None if normalized_status == "completed" else item.get("claimed_by"),
                "claimed_at": None if normalized_status == "completed" else item.get("claimed_at"),
                "claim_expires_at": None if normalized_status == "completed" else item.get("claim_expires_at"),
                "completed_at": timestamp if normalized_status == "completed" else None,
                "completed_by": actor_id if normalized_status == "completed" else None,
                "notes": note,
            }
        )

    updated_progress = _apply_dependency_state(updated_progress)
    return {
        "runbook_progress": updated_progress,
        "runbook_progress_summary": summarize_runbook_progress(updated_progress),
        "runbook_execution_plan": build_runbook_execution_plan(updated_progress),
        "last_reviewed_at": timestamp,
        "last_reviewed_by": actor_id,
    }


def apply_runbook_step_assignment(
    incident: dict[str, Any],
    *,
    step_index: int,
    actor_id: str,
    action: str,
    assigned_to: str | None = None,
    claim_ttl_seconds: int = 600,
    now_iso: str | None = None,
) -> dict[str, Any]:
    if step_index < 1:
        raise IndexError("step_index must be >= 1")
    progress = incident.get("runbook_progress", [])
    if not isinstance(progress, list):
        progress = []
    if step_index > len(progress):
        raise IndexError("step_index is out of range")
    timestamp = now_iso or datetime.now(timezone.utc).isoformat()
    now = _parse_iso(timestamp) or datetime.now(timezone.utc)
    normalized_action = action.strip().lower()
    if normalized_action not in {"assign", "claim", "heartbeat", "release"}:
        raise ValueError("action must be one of: assign, claim, heartbeat, release")
    if claim_ttl_seconds < 1:
        raise ValueError("claim_ttl_seconds must be >= 1")

    updated_progress: list[dict[str, Any]] = []
    for item in progress:
        if not isinstance(item, dict):
            continue
        if item.get("step_index") != step_index:
            updated_progress.append(item)
            continue
        updated_item = dict(item)
        active_claim = _claim_is_active(item, now=now)
        current_claimer = item.get("claimed_by") if isinstance(item.get("claimed_by"), str) else None
        if normalized_action == "assign":
            updated_item["step_revision"] = int(item.get("step_revision", 1)) + 1
            updated_item["assigned_to"] = assigned_to
            if not assigned_to:
                updated_item["claimed_by"] = None
                updated_item["claimed_at"] = None
                updated_item["claim_expires_at"] = None
        elif normalized_action == "claim":
            if item.get("status") == "completed":
                raise ValueError("cannot claim a completed step")
            if active_claim and current_claimer and current_claimer != actor_id:
                raise ValueError(f"step {step_index} is already claimed by {current_claimer}")
            updated_item["step_revision"] = int(item.get("step_revision", 1)) + 1
            updated_item["claimed_by"] = actor_id
            updated_item["claimed_at"] = timestamp
            updated_item["claim_expires_at"] = (now.timestamp() + int(claim_ttl_seconds))
            updated_item["claim_expires_at"] = datetime.fromtimestamp(updated_item["claim_expires_at"], tz=timezone.utc).isoformat()
            updated_item["assigned_to"] = assigned_to or item.get("assigned_to") or actor_id
        elif normalized_action == "heartbeat":
            if not active_claim or current_claimer != actor_id:
                raise ValueError(f"step {step_index} is not actively claimed by {actor_id}")
            updated_item["step_revision"] = int(item.get("step_revision", 1)) + 1
            updated_item["claim_expires_at"] = datetime.fromtimestamp(now.timestamp() + int(claim_ttl_seconds), tz=timezone.utc).isoformat()
        elif normalized_action == "release":
            if active_claim and current_claimer and current_claimer != actor_id:
                raise ValueError(f"step {step_index} is actively claimed by {current_claimer}")
            updated_item["step_revision"] = int(item.get("step_revision", 1)) + 1
            updated_item["claimed_by"] = None
            updated_item["claimed_at"] = None
            updated_item["claim_expires_at"] = None
            if assigned_to is not None:
                updated_item["assigned_to"] = assigned_to
        updated_progress.append(updated_item)

    updated_progress = _apply_dependency_state(updated_progress)
    return {
        "runbook_progress": updated_progress,
        "runbook_progress_summary": summarize_runbook_progress(updated_progress),
        "runbook_execution_plan": build_runbook_execution_plan(updated_progress),
        "last_reviewed_at": timestamp,
        "last_reviewed_by": actor_id,
    }


def workflow_requires_approval(incident: dict[str, Any], workflow_status: str) -> bool:
    policy = incident.get("approval_policy", {})
    if not isinstance(policy, dict):
        return False
    required_statuses = _normalize_required_statuses(policy.get("required_workflow_statuses"))
    return workflow_status.strip().lower() in required_statuses if isinstance(workflow_status, str) else False


def workflow_requires_completed_runbook(incident: dict[str, Any], workflow_status: str) -> bool:
    policy = incident.get("completion_policy", {})
    if not isinstance(policy, dict):
        return False
    required_statuses = _normalize_required_statuses(policy.get("required_workflow_statuses"))
    return workflow_status.strip().lower() in required_statuses if isinstance(workflow_status, str) else False


def pending_runbook_steps(incident: dict[str, Any]) -> list[dict[str, Any]]:
    progress = incident.get("runbook_progress", [])
    if not isinstance(progress, list):
        return []
    return [
        item
        for item in progress
        if isinstance(item, dict) and item.get("required", True) and item.get("status") != "completed"
    ]


def get_runbook_step(incident: dict[str, Any], step_index: int) -> dict[str, Any] | None:
    progress = incident.get("runbook_progress", [])
    if not isinstance(progress, list):
        return None
    for item in progress:
        if isinstance(item, dict) and item.get("step_index") == step_index:
            return item
    return None
