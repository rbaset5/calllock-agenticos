"""Hermes AIAgent adapter for the supervisor worker node.

Wraps NousResearch/hermes-agent as an execution engine for workers.
Workers gain multi-turn tool use (file ops, terminal, web, browser)
while the supervisor retains governance (policy gate, verification,
dispatch, audit).

Import: `from run_agent import AIAgent` — deferred to runtime.
hermes-agent is installed separately via git clone, not via pip.
"""
from __future__ import annotations

import json
import re
import signal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]

# Toolsets that must never be enabled for supervised workers.
BLOCKED_TOOLSETS = frozenset([
    "delegation",
    "memory",
    "clarify",
    "skills",
    "cronjob",
])

# Map from worker spec tools_allowed entries to Hermes toolset names.
TOOL_GRANT_TO_TOOLSET = {
    "read_code": "file",
    "supabase_read": "file",
    "write_code": "file",
    "git_branch_write": "terminal",
    "git_pr_review": "terminal",
    "issue_create": "terminal",
    "issue_comment": "terminal",
    "run_tests": "terminal",
    "extraction_rerun": "terminal",
    "scorecard_evaluate": "terminal",
    "retell_config_diff": "terminal",
    "app_sync_simulate": "terminal",
    "seam_contract_validate": "terminal",
    "app_contract_validate": "terminal",
    "inngest_emit": "terminal",
    "web_search": "web",
    "web_fetch": "web",
    "headless_browser": "browser",
    "app_render_check": "browser",
}

WALL_CLOCK_TIMEOUT_SECONDS = 120


def map_tool_grants_to_toolsets(
    tool_grants: list[str],
    blocked: frozenset[str] = BLOCKED_TOOLSETS,
) -> set[str]:
    """Map worker spec tool_grants to Hermes toolset names."""
    toolsets = {"file"}
    for grant in tool_grants:
        toolset = TOOL_GRANT_TO_TOOLSET.get(grant)
        if toolset and toolset not in blocked:
            toolsets.add(toolset)
    return toolsets


def load_worker_skills(worker_id: str, tenant_id: str = "") -> list[dict[str, Any]]:
    """Load accumulated skills for a worker from knowledge/worker-skills/."""
    skills_dir = REPO_ROOT / "knowledge" / "worker-skills" / worker_id
    if not skills_dir.is_dir():
        return []

    skills = []
    for skill_path in sorted(skills_dir.glob("*.md")):
        content = skill_path.read_text()
        is_universal = "universal: true" in content
        if not is_universal and tenant_id:
            if f"tenant_context: {tenant_id}" not in content:
                continue
        skills.append(
            {
                "source": "worker_skill",
                "content": content,
                "path": str(skill_path.relative_to(REPO_ROOT)),
            }
        )
    return skills


def build_hermes_system_prompt(
    *,
    spec: dict[str, Any],
    assembled_context: list[dict[str, Any]],
    worker_skills: list[dict[str, Any]],
    output_fields: list[str],
) -> str:
    """Build system prompt for Hermes from supervisor context."""
    sections = []

    sections.append(f"# Worker: {spec.get('title', spec.get('worker_id', 'unknown'))}")
    sections.append(f"Mission: {spec.get('mission', '')}")

    scope = spec.get("scope", {})
    if scope.get("can_do"):
        sections.append("\n## You CAN:")
        for item in scope["can_do"]:
            sections.append(f"- {item}")
    if scope.get("cannot_do"):
        sections.append("\n## You CANNOT:")
        for item in scope["cannot_do"]:
            sections.append(f"- {item}")

    if worker_skills:
        sections.append("\n## Accumulated Skills")
        for skill in worker_skills:
            sections.append(f"\n### {skill.get('path', 'skill')}")
            sections.append(skill["content"])

    if assembled_context:
        sections.append("\n## Context")
        for item in assembled_context:
            sections.append(f"[{item.get('source', 'unknown')}]: {item.get('content', '')}")

    sections.append("\n## Required Output")
    sections.append(
        f"When done, output a JSON block (```json ... ```) with these fields: "
        f"{', '.join(output_fields)}. "
        f"Include all fields even if the value is null or empty."
    )

    return "\n".join(sections)


def extract_structured_output(
    response_text: str,
    output_fields: list[str],
) -> dict[str, Any]:
    """Extract structured JSON output from Hermes's natural language response."""
    json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            if isinstance(parsed, dict):
                return {field: parsed.get(field) for field in output_fields}
        except json.JSONDecodeError:
            pass

    json_obj_match = re.search(r"\{[^{}]*\}", response_text, re.DOTALL)
    if json_obj_match:
        try:
            parsed = json.loads(json_obj_match.group(0))
            if isinstance(parsed, dict):
                return {field: parsed.get(field) for field in output_fields}
        except json.JSONDecodeError:
            pass

    result = {field: None for field in output_fields}
    if "summary" in output_fields:
        result["summary"] = response_text[:2000]
    return result


def resolve_model_for_hermes(worker_spec: dict[str, Any]) -> str:
    """Resolve the LLM model for a Hermes worker run."""
    model_map = {
        "zeroclaw": "meta-llama/llama-3.1-8b-instruct",
        "nanoclaw": "anthropic/claude-haiku-4-5-20251001",
        "codex": "anthropic/claude-sonnet-4-6",
        "exec": "anthropic/claude-opus-4-6",
    }
    model_tier = worker_spec.get("model_tier", "codex")
    return model_map.get(model_tier, "anthropic/claude-sonnet-4-6")


def run_hermes_worker(
    task: dict[str, Any],
    *,
    worker_id: str,
    worker_spec: dict[str, Any],
) -> dict[str, Any]:
    """Run a Hermes AIAgent as the worker execution engine.

    Raises:
        TimeoutError: if worker exceeds WALL_CLOCK_TIMEOUT_SECONDS
        ImportError: if hermes-agent is not installed
    """
    from run_agent import AIAgent  # deferred import

    from harness.graphs.workers.base import expected_output_fields

    context_items = task.get("context_items", [])
    tool_grants = task.get("tool_grants", [])
    tenant_id = task.get("tenant_id", "")
    output_fields = expected_output_fields(worker_spec)

    model = resolve_model_for_hermes(worker_spec)
    worker_skills = load_worker_skills(worker_id, tenant_id)

    system_prompt = build_hermes_system_prompt(
        spec=worker_spec,
        assembled_context=context_items,
        worker_skills=worker_skills,
        output_fields=output_fields,
    )

    toolsets = map_tool_grants_to_toolsets(tool_grants, blocked=BLOCKED_TOOLSETS)
    max_iterations = worker_spec.get("max_iterations", 15)

    user_message = (
        f"Problem: {task.get('problem_description', '')}\n"
        f"Transcript: {task.get('transcript', '')}\n"
        f"Task context: {json.dumps(task.get('task_context', {}), indent=2)}"
    )

    agent = AIAgent(
        model=model,
        max_iterations=max_iterations,
        enabled_toolsets=list(toolsets),
        disabled_toolsets=list(BLOCKED_TOOLSETS),
        skip_memory=True,
        skip_context_files=True,
        quiet_mode=True,
    )

    old_handler = signal.signal(
        signal.SIGALRM,
        lambda *_: (_ for _ in ()).throw(
            TimeoutError(f"Hermes worker {worker_id} exceeded {WALL_CLOCK_TIMEOUT_SECONDS}s")
        ),
    )
    signal.alarm(WALL_CLOCK_TIMEOUT_SECONDS)
    try:
        raw = agent.run_conversation(
            user_message=user_message,
            system_message=system_prompt,
        )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    if isinstance(raw, dict):
        response_text = raw.get("final_response", str(raw))
    else:
        response_text = str(raw)

    return extract_structured_output(response_text, output_fields)
