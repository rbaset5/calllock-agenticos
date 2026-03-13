from __future__ import annotations

from typing import Any
from uuid import uuid4

from db.repository import (
    create_job,
    create_tenant,
    create_tenant_config,
    delete_tenant,
    get_tenant,
    list_jobs,
    update_job_status,
    update_tenant_config,
)
from harness.audit import log_audit_event


def _verify_isolation(tenant_id: str) -> dict[str, Any]:
    probe = create_job(
        {
            "tenant_id": tenant_id,
            "origin_worker_id": "system",
            "origin_run_id": f"onboard-{tenant_id}",
            "job_type": "isolation_probe",
            "status": "queued",
            "idempotency_key": f"isolation-probe-{tenant_id}",
            "payload": {"probe": True},
            "created_by": "onboarding",
        }
    )
    visible = list_jobs(tenant_id=tenant_id, run_id=f"onboard-{tenant_id}")
    if not any(job["id"] == probe["id"] for job in visible):
        raise RuntimeError("Isolation verification failed for tenant job visibility")
    return {"probe_job_id": probe["id"], "job_count": len(visible)}


def onboard_tenant(request: dict[str, Any]) -> dict[str, Any]:
    tenant_id = request.get("tenant_id") or str(uuid4())
    actor_id = request.get("actor_id", "system")
    rollback_actions: list[tuple[str, str]] = []
    onboarding_job = create_job(
        {
            "tenant_id": tenant_id,
            "origin_worker_id": "system",
            "origin_run_id": f"onboarding-{tenant_id}",
            "job_type": "tenant_onboarding",
            "status": "running",
            "idempotency_key": f"tenant-onboarding-{tenant_id}",
            "payload": {"slug": request["slug"]},
            "created_by": "admin",
        }
    )
    try:
        tenant = create_tenant(
            {
                "id": tenant_id,
                "slug": request["slug"],
                "name": request["name"],
                "industry_pack_id": request.get("industry_pack_id", "hvac"),
                "status": "onboarding",
            }
        )
        log_audit_event(
            action_type="tenant.onboard.started",
            actor_id=actor_id,
            reason="Start tenant onboarding",
            tenant_id=tenant_id,
            target_type="tenant",
            target_id=tenant_id,
            payload={"slug": request["slug"], "name": request["name"]},
        )
        rollback_actions.append(("delete_tenant", tenant_id))
        config = create_tenant_config(
            {
                "tenant_id": tenant_id,
                "slug": request["slug"],
                "industry_pack_id": request.get("industry_pack_id", "hvac"),
                "allowed_tools": request.get("allowed_tools", []),
                "tone_profile": request.get("tone_profile", {"formality": "direct", "banned_words": []}),
                "feature_flags": request.get("feature_flags", {"harness_enabled": True}),
                "voice_agent": {"configured": False},
                "automations": [],
            }
        )
        if request.get("provision_automations", True):
            config = update_tenant_config(tenant_id, {"automations": ["post-call-analysis", "alert-review"]})
        if request.get("configure_voice_agent", True):
            config = update_tenant_config(tenant_id, {"voice_agent": {"configured": True, "provider": "retell"}})
        isolation = _verify_isolation(tenant_id)
        tenant["status"] = "active"
        update_job_status(onboarding_job["id"], "completed", result={"tenant_id": tenant_id, "isolation": isolation})
        log_audit_event(
            action_type="tenant.onboard.completed",
            actor_id=actor_id,
            reason="Tenant onboarding completed",
            tenant_id=tenant_id,
            target_type="tenant",
            target_id=tenant_id,
            payload={"isolation": isolation},
        )
        return {
            "tenant": get_tenant(tenant_id),
            "tenant_config": config,
            "rollback_log": rollback_actions,
            "isolation": isolation,
            "job": onboarding_job,
        }
    except Exception as exc:
        update_job_status(onboarding_job["id"], "failed", result={"error": str(exc)})
        log_audit_event(
            action_type="tenant.onboard.failed",
            actor_id=actor_id,
            reason="Tenant onboarding failed",
            tenant_id=tenant_id,
            target_type="tenant",
            target_id=tenant_id,
            payload={"error": str(exc)},
        )
        for action, value in reversed(rollback_actions):
            if action == "delete_tenant":
                delete_tenant(value)
        raise
