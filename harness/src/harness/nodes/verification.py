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


def check_skill_candidate(
    worker_output: dict[str, Any],
    verification: dict[str, Any],
    worker_id: str,
    task_type: str,
    run_id: str,
) -> dict[str, Any] | None:
    """Check if this run should be flagged as a skill candidate.

    Uses heuristics from run data — no extra LLM call needed.
    """
    signals = []
    confidence = float(verification.get("confidence", 1.0 if verification.get("passed") else 0.0))
    outcome = verification.get("outcome", verification.get("verdict", ""))

    if confidence >= 0.9 and outcome == "pass":
        signals.append("high_confidence_pass")

    iterations = worker_output.get("_hermes_iterations", 0)
    if isinstance(iterations, int) and iterations > 5:
        signals.append("exploratory_solve")

    non_null_fields = sum(1 for value in worker_output.values() if value is not None and value != "")
    if non_null_fields >= 5 and confidence >= 0.8:
        signals.append("thorough_output")

    if not signals:
        return None

    return {
        "worker_id": worker_id,
        "task_type": task_type,
        "run_id": run_id,
        "signals": signals,
        "summary": f"Skill candidate: {', '.join(signals)} (confidence={confidence:.2f})",
    }


def verification_node(state: dict[str, Any]) -> dict[str, Any]:
    task = state["task"]
    verification = verify_output(
        state.get("worker_output", {}),
        worker_id=state.get("worker_id", "customer-analyst"),
        worker_spec=task.get("worker_spec", {}),
        tenant_config=task.get("tenant_config", {}),
        context_items=state.get("context_items", []),
        retry_count=state.get("retry_count", 0),
    )

    skill_candidate = check_skill_candidate(
        worker_output=state.get("worker_output", {}),
        verification=verification,
        worker_id=state.get("worker_id", ""),
        task_type=task.get("task_context", {}).get("task_type", task.get("task_type", "")),
        run_id=state.get("run_id", ""),
    )

    if skill_candidate:
        try:
            from db import repository

            repository.create_skill_candidate(
                {
                    "tenant_id": task.get("tenant_id", state.get("tenant_id", "")),
                    "worker_id": skill_candidate["worker_id"],
                    "task_type": skill_candidate["task_type"],
                    "run_id": skill_candidate["run_id"],
                    "signals": skill_candidate["signals"],
                    "summary": skill_candidate["summary"],
                }
            )
        except Exception:
            pass

    result = {"verification": verification}
    if skill_candidate:
        result["skill_candidate"] = skill_candidate
    return result
