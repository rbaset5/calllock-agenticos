from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Callable

try:
    from litellm import completion
except Exception:  # pragma: no cover
    completion = None  # type: ignore[assignment]

from knowledge.pack_loader import load_json_yaml


REPO_ROOT = Path(__file__).resolve().parents[4]
logger = logging.getLogger(__name__)

OUTPUT_FIELD_ALIASES = {
    "lead routing decisions": "lead_route",
    "summary": "summary",
    "sentiment": "sentiment",
    "churn risk": "churn_risk",
    "plans": "plans",
    "prioritized requirements": "prioritized_requirements",
    "decision memos": "decision_memos",
    "code": "code",
    "tests": "tests",
    "migration plans": "migration_plans",
    "design specs": "design_specs",
    "content patterns": "content_patterns",
    "interaction flows": "interaction_flows",
    "messaging": "messaging",
    "release notes": "release_notes",
    "campaign drafts": "campaign_drafts",
}


def load_worker_spec(worker_id: str) -> dict[str, Any]:
    return load_json_yaml(REPO_ROOT / "knowledge" / "worker-specs" / f"{worker_id}.yaml")


def expected_output_fields(worker_spec: dict[str, Any]) -> list[str]:
    fields = []
    for output in worker_spec.get("outputs", []):
        lowered = str(output).strip().lower()
        fields.append(OUTPUT_FIELD_ALIASES.get(lowered, lowered.replace(" ", "_").replace("-", "_")))
    return fields


def build_prompt(task: dict[str, Any], worker_spec: dict[str, Any], output_fields: list[str]) -> str:
    context_sections = [
        f"Mission: {worker_spec.get('mission', '')}",
        f"Problem: {task.get('problem_description', '')}",
        f"Transcript: {task.get('transcript', '')}",
        f"Task context: {json.dumps(task.get('task_context', {}), indent=2)}",
    ]
    return "\n".join(context_sections + [f"Return strict JSON with keys: {', '.join(output_fields)}"])


def call_llm(prompt: str, output_fields: list[str]) -> dict[str, Any]:
    if completion is None:
        raise RuntimeError("litellm is not installed")
    model = os.getenv("LITELLM_MODEL", "claude-sonnet-4-6")
    response = completion(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Return valid JSON only. Keep outputs concise and grounded in the provided context.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    content = response.choices[0].message.content
    parsed = json.loads(content)
    return {field: parsed.get(field) for field in output_fields}


def ensure_output_shape(output: dict[str, Any], output_fields: list[str]) -> dict[str, Any]:
    shaped = dict(output)
    for field in output_fields:
        shaped.setdefault(field, "" if field not in {"prioritized_requirements", "content_patterns", "interaction_flows"} else [])
    return shaped


def run_worker(
    task: dict[str, Any],
    *,
    worker_id: str,
    deterministic_builder: Callable[[dict[str, Any]], dict[str, Any]],
    llm_enabled: bool = True,
) -> dict[str, Any]:
    worker_spec = task.get("worker_spec") or load_worker_spec(worker_id)
    output_fields = expected_output_fields(worker_spec)
    deterministic_mode = task.get("tenant_config", {}).get("deterministic_mode", False)
    feature_flags = task.get("feature_flags", {})

    # Shadow mode: run BOTH engines, compare, return baseline
    if (llm_enabled and not deterministic_mode
            and feature_flags.get(f"shadow_hermes_{worker_id}", False)):
        return _run_shadow_mode(
            task,
            worker_id=worker_id,
            worker_spec=worker_spec,
            output_fields=output_fields,
            deterministic_builder=deterministic_builder,
        )

    # Hermes path: multi-turn agent loop (per-worker opt-in)
    if (llm_enabled and not deterministic_mode
            and feature_flags.get(f"hermes_worker_{worker_id}", False)):
        try:
            from harness.hermes_adapter import run_hermes_worker
            generated = run_hermes_worker(task, worker_id=worker_id, worker_spec=worker_spec)
            return ensure_output_shape(generated, output_fields)
        except Exception:
            pass  # fall through to existing LLM path

    if llm_enabled and not deterministic_mode and feature_flags.get("llm_workers_enabled", True):
        try:
            generated = call_llm(build_prompt(task, worker_spec, output_fields), output_fields)
            return ensure_output_shape(generated, output_fields)
        except Exception:
            pass
    return ensure_output_shape(deterministic_builder(task), output_fields)


def _run_shadow_mode(
    task: dict[str, Any],
    *,
    worker_id: str,
    worker_spec: dict[str, Any],
    output_fields: list[str],
    deterministic_builder: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Run both call_llm and Hermes, compare, return baseline result."""
    baseline_start = time.monotonic()
    try:
        baseline = call_llm(build_prompt(task, worker_spec, output_fields), output_fields)
        baseline = ensure_output_shape(baseline, output_fields)
    except Exception:
        baseline = ensure_output_shape(deterministic_builder(task), output_fields)
    baseline_ms = int((time.monotonic() - baseline_start) * 1000)

    hermes_output = None
    hermes_error = None
    hermes_ms = 0
    hermes_iterations = 0
    try:
        from harness.hermes_adapter import run_hermes_worker

        hermes_start = time.monotonic()
        hermes_output = run_hermes_worker(task, worker_id=worker_id, worker_spec=worker_spec)
        hermes_output = ensure_output_shape(hermes_output, output_fields)
        hermes_ms = int((time.monotonic() - hermes_start) * 1000)
    except Exception as exc:
        hermes_error = f"{type(exc).__name__}: {exc}"
        logger.warning("Shadow Hermes failed for %s: %s", worker_id, hermes_error)

    comparison = _compare_outputs(baseline, hermes_output, output_fields)

    try:
        _log_shadow_comparison(
            task=task,
            worker_id=worker_id,
            baseline=baseline,
            hermes_output=hermes_output,
            hermes_error=hermes_error,
            comparison=comparison,
            baseline_ms=baseline_ms,
            hermes_ms=hermes_ms,
            hermes_iterations=hermes_iterations,
        )
    except Exception as exc:
        logger.warning("Failed to log shadow comparison: %s", exc)

    return baseline


def _compare_outputs(
    baseline: dict[str, Any],
    hermes: dict[str, Any] | None,
    output_fields: list[str],
) -> dict[str, Any]:
    """Compare two outputs field-by-field."""
    if hermes is None:
        return {"match_count": 0, "total": len(output_fields), "match_rate": 0.0, "mismatches": output_fields}

    match_count = 0
    mismatches = []
    for field in output_fields:
        baseline_value = baseline.get(field)
        hermes_value = hermes.get(field)
        if baseline_value == hermes_value:
            match_count += 1
        elif (
            isinstance(baseline_value, str)
            and isinstance(hermes_value, str)
            and baseline_value.strip().lower() == hermes_value.strip().lower()
        ):
            match_count += 1
        else:
            mismatches.append(field)

    total = len(output_fields)
    return {
        "match_count": match_count,
        "total": total,
        "match_rate": match_count / total if total > 0 else 0.0,
        "mismatches": mismatches,
    }


def _log_shadow_comparison(
    *,
    task: dict[str, Any],
    worker_id: str,
    baseline: dict[str, Any],
    hermes_output: dict[str, Any] | None,
    hermes_error: str | None,
    comparison: dict[str, Any],
    baseline_ms: int,
    hermes_ms: int,
    hermes_iterations: int,
) -> None:
    """Log shadow comparison to the active repository (best-effort)."""
    try:
        from db.repository import create_shadow_comparison
    except Exception:
        logger.info(
            "Shadow comparison [%s]: match_rate=%.2f baseline_ms=%d hermes_ms=%d error=%s",
            worker_id,
            comparison["match_rate"],
            baseline_ms,
            hermes_ms,
            hermes_error,
        )
        return

    create_shadow_comparison(
        {
            "tenant_id": task.get("tenant_id", ""),
            "worker_id": worker_id,
            "run_id": task.get("run_id", ""),
            "task_type": task.get("task_context", {}).get("task_type", ""),
            "baseline_output": baseline,
            "hermes_output": hermes_output,
            "hermes_error": hermes_error,
            "field_match_count": comparison["match_count"],
            "field_total": comparison["total"],
            "field_match_rate": comparison["match_rate"],
            "baseline_latency_ms": baseline_ms,
            "hermes_latency_ms": hermes_ms,
            "hermes_iterations": hermes_iterations,
        }
    )
