from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

try:
    from litellm import completion
except Exception:  # pragma: no cover
    completion = None  # type: ignore[assignment]

from knowledge.pack_loader import load_json_yaml


REPO_ROOT = Path(__file__).resolve().parents[4]

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
    if llm_enabled and not deterministic_mode and task.get("feature_flags", {}).get("llm_workers_enabled", True):
        try:
            generated = call_llm(build_prompt(task, worker_spec, output_fields), output_fields)
            return ensure_output_shape(generated, output_fields)
        except Exception:
            pass
    return ensure_output_shape(deterministic_builder(task), output_fields)
