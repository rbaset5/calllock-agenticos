from __future__ import annotations

from typing import Any

from harness.verification import get_profile, resolve_verification_outcome, run_checks


def verify_output(
    output: dict[str, Any],
    *,
    worker_id: str,
    worker_spec: dict[str, Any],
    tenant_config: dict[str, Any],
    context_items: list[dict[str, Any]],
    retry_count: int = 0,
) -> dict[str, Any]:
    profile = get_profile(worker_id, worker_spec)
    findings = run_checks(
        output,
        worker_id=worker_id,
        worker_spec=worker_spec,
        tenant_config=tenant_config,
        context_items=context_items,
        profile=profile,
    )
    return resolve_verification_outcome(findings, retry_count=retry_count, max_retries=profile.get("max_retries", 1))


def verification_node(state: dict[str, Any]) -> dict[str, Any]:
    task = state["task"]
    return {
        "verification": verify_output(
            state.get("worker_output", {}),
            worker_id=state.get("worker_id", "customer-analyst"),
            worker_spec=task.get("worker_spec", {}),
            tenant_config=task.get("tenant_config", {}),
            context_items=state.get("context_items", []),
            retry_count=state.get("retry_count", 0),
        )
    }
