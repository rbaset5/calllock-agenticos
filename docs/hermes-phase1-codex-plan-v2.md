# Hermes Phase 1 — Codex Execution Plan (v2)

## Goal

Create the adapter that lets any worker run as a multi-turn Hermes
AIAgent instead of a single-shot `call_llm()`. Per-worker feature
flags enable incremental rollout. No workers are switched to Hermes
yet — this is the foundation only.

**NOTE:** hermes-agent is NOT a pip dependency. It will be installed
via `git clone + pip install -e` at deploy time. The adapter uses a
deferred import (`from run_agent import AIAgent` inside the function)
so the package is only required when a worker's Hermes flag is enabled.
All tests mock the AIAgent import.

## Verified Hermes API (from hermes-agent v0.4.0 source)

```python
from run_agent import AIAgent

AIAgent(
    model="anthropic/claude-sonnet-4-6",
    max_iterations=15,
    enabled_toolsets=["file", "terminal"],
    disabled_toolsets=["delegation", "memory", "clarify"],
    skip_memory=True,
    skip_context_files=True,
    quiet_mode=True,
)

result = agent.run_conversation(
    user_message="...",
    system_message="...",
)
# Returns: Dict[str, Any] with "final_response" key
```

---

## Task 1: Hermes Adapter

### File: `harness/src/harness/hermes_adapter.py`

**Create this file:**

```python
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
        skills.append({
            "source": "worker_skill",
            "content": content,
            "path": str(skill_path.relative_to(REPO_ROOT)),
        })
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

    sections.append(f"\n## Required Output")
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

    old_handler = signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(
        TimeoutError(f"Hermes worker {worker_id} exceeded {WALL_CLOCK_TIMEOUT_SECONDS}s")
    ))
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
```

### Verification

```bash
cd harness && python -c "from harness.hermes_adapter import BLOCKED_TOOLSETS; print('Adapter imports OK')"
```

---

## Task 2: Feature Flag Branch in run_worker()

### File: `harness/src/harness/graphs/workers/base.py`

**Change:** Add the Hermes path before the existing LLM path in the `run_worker` function.

Find the `run_worker` function. Add this block BEFORE the existing `call_llm` block:

```python
    # Hermes path: multi-turn agent loop (per-worker opt-in)
    if (llm_enabled and not deterministic_mode
            and feature_flags.get(f"hermes_worker_{worker_id}", False)):
        try:
            from harness.hermes_adapter import run_hermes_worker
            generated = run_hermes_worker(task, worker_id=worker_id, worker_spec=worker_spec)
            return ensure_output_shape(generated, output_fields)
        except Exception:
            pass  # fall through to existing LLM path
```

Make sure `feature_flags` is extracted from the task dict. Add this line near the top of `run_worker`:

```python
    feature_flags = task.get("feature_flags", {})
```

The existing `call_llm` block should also check feature flags:

```python
    if llm_enabled and not deterministic_mode and feature_flags.get("llm_workers_enabled", True):
```

### Verification

```bash
cd harness && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -10
```

All existing tests must pass — the Hermes path is behind a feature flag
that defaults to False.

---

## Task 3: Worker Skills in Context Assembly

### File: `harness/src/harness/nodes/context_assembly.py`

**Change:** Add `worker_skills` as priority 2 (after worker_spec, before task_context).

Find the `PRIORITY_ORDER` list. Add `"worker_skills"` after `"worker_spec"`:

```python
PRIORITY_ORDER = [
    "worker_spec",
    "worker_skills",    # NEW: accumulated procedures from past runs
    "task_context",
    ...
]
```

Update the `assemble_context` function to accept and include `worker_skills`:
- Add `worker_skills: list[dict[str, Any]]` parameter
- Add items with source `"worker_skills"` after the worker_spec items

Update `context_assembly_node` to pass `worker_skills=task.get("worker_skills", [])`.

### Directory: `knowledge/worker-skills/`

**Create:** `knowledge/worker-skills/.gitkeep`

### Verification

```bash
cd harness && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -10
```

---

## Task 4: Skill Candidate Detection Stub

### File: `harness/src/harness/nodes/verification.py`

**Change:** Add a `check_skill_candidate` function that returns None (stub).
Call it from `verification_node` and include the result in the return dict
if non-None.

```python
def check_skill_candidate(
    worker_output: dict[str, Any],
    verification: dict[str, Any],
    worker_id: str,
    task_type: str,
    run_id: str,
) -> dict[str, Any] | None:
    """Check if this run should be flagged as a skill candidate.
    Stub — returns None until Hermes workers are active."""
    return None
```

In `verification_node`, after the `verify_output` call, add:

```python
    skill_candidate = check_skill_candidate(
        worker_output=state.get("worker_output", {}),
        verification=verification,
        worker_id=state.get("worker_id", ""),
        task_type=task.get("task_context", {}).get("task_type", ""),
        run_id=state.get("run_id", ""),
    )

    result = {"verification": verification}
    if skill_candidate:
        result["skill_candidate"] = skill_candidate
```

### Verification

```bash
cd harness && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -10
```

---

## Task 5: Adapter Tests

### File: `harness/tests/test_hermes_adapter.py`

**Create this file:**

```python
"""Tests for Hermes AIAgent adapter.

All tests exercise adapter logic WITHOUT importing hermes-agent.
The run_hermes_worker function is NOT tested here because it
requires the hermes-agent package. Only the pure functions are tested.
"""
from __future__ import annotations

import pytest

from harness.hermes_adapter import (
    BLOCKED_TOOLSETS,
    WALL_CLOCK_TIMEOUT_SECONDS,
    build_hermes_system_prompt,
    extract_structured_output,
    load_worker_skills,
    map_tool_grants_to_toolsets,
    resolve_model_for_hermes,
)


class TestToolGrantMapping:
    def test_baseline_always_includes_file(self):
        result = map_tool_grants_to_toolsets([])
        assert "file" in result

    def test_maps_known_grants(self):
        result = map_tool_grants_to_toolsets(["read_code", "web_search", "headless_browser"])
        assert "file" in result
        assert "web" in result
        assert "browser" in result

    def test_blocks_delegation(self):
        result = map_tool_grants_to_toolsets(["read_code"])
        assert "delegation" not in result
        assert "memory" not in result
        assert "clarify" not in result

    def test_unknown_grants_ignored(self):
        result = map_tool_grants_to_toolsets(["unknown_tool_xyz"])
        assert result == {"file"}

    def test_terminal_from_write_tools(self):
        result = map_tool_grants_to_toolsets(["git_branch_write", "run_tests"])
        assert "terminal" in result


class TestBlockedToolsets:
    def test_blocked_set(self):
        assert "delegation" in BLOCKED_TOOLSETS
        assert "memory" in BLOCKED_TOOLSETS
        assert "clarify" in BLOCKED_TOOLSETS
        assert "skills" in BLOCKED_TOOLSETS
        assert "cronjob" in BLOCKED_TOOLSETS

    def test_file_not_blocked(self):
        assert "file" not in BLOCKED_TOOLSETS
        assert "terminal" not in BLOCKED_TOOLSETS
        assert "web" not in BLOCKED_TOOLSETS
        assert "browser" not in BLOCKED_TOOLSETS


class TestSystemPrompt:
    def test_includes_mission(self):
        prompt = build_hermes_system_prompt(
            spec={"mission": "Guard the voice pipeline", "title": "AI/Voice Engineer"},
            assembled_context=[],
            worker_skills=[],
            output_fields=["summary"],
        )
        assert "Guard the voice pipeline" in prompt
        assert "AI/Voice Engineer" in prompt

    def test_includes_scope(self):
        prompt = build_hermes_system_prompt(
            spec={"mission": "test", "scope": {
                "can_do": ["read files"],
                "cannot_do": ["deploy"],
            }},
            assembled_context=[],
            worker_skills=[],
            output_fields=["summary"],
        )
        assert "read files" in prompt
        assert "deploy" in prompt

    def test_includes_output_contract(self):
        prompt = build_hermes_system_prompt(
            spec={"mission": "test"},
            assembled_context=[],
            worker_skills=[],
            output_fields=["summary", "status", "violations"],
        )
        assert "summary" in prompt
        assert "status" in prompt
        assert "violations" in prompt

    def test_includes_skills(self):
        prompt = build_hermes_system_prompt(
            spec={"mission": "test"},
            assembled_context=[],
            worker_skills=[{"content": "# Skill: Handle multi-unit calls", "path": "skills/multi-unit.md"}],
            output_fields=["summary"],
        )
        assert "Handle multi-unit calls" in prompt

    def test_includes_context(self):
        prompt = build_hermes_system_prompt(
            spec={"mission": "test"},
            assembled_context=[{"source": "tenant_config", "content": "HVAC tenant"}],
            worker_skills=[],
            output_fields=["summary"],
        )
        assert "HVAC tenant" in prompt


class TestOutputExtraction:
    def test_extracts_json_block(self):
        response = 'Here is the result:\n```json\n{"summary": "all good", "status": "green"}\n```'
        result = extract_structured_output(response, ["summary", "status"])
        assert result["summary"] == "all good"
        assert result["status"] == "green"

    def test_extracts_inline_json(self):
        response = 'The result is {"summary": "found 2 issues", "count": 2}'
        result = extract_structured_output(response, ["summary", "count"])
        assert result["summary"] == "found 2 issues"
        assert result["count"] == 2

    def test_fallback_to_summary(self):
        response = "I checked everything and it looks fine."
        result = extract_structured_output(response, ["summary", "status"])
        assert result["summary"] == response
        assert result["status"] is None

    def test_missing_fields_are_none(self):
        response = '```json\n{"summary": "ok"}\n```'
        result = extract_structured_output(response, ["summary", "status", "violations"])
        assert result["summary"] == "ok"
        assert result["status"] is None
        assert result["violations"] is None

    def test_invalid_json_falls_back(self):
        response = '```json\n{invalid json}\n```'
        result = extract_structured_output(response, ["summary"])
        assert result["summary"] is None or isinstance(result["summary"], str)


class TestModelResolution:
    def test_default_is_codex(self):
        model = resolve_model_for_hermes({})
        assert model == "anthropic/claude-sonnet-4-6"

    def test_exec_tier(self):
        model = resolve_model_for_hermes({"model_tier": "exec"})
        assert model == "anthropic/claude-opus-4-6"

    def test_nanoclaw_tier(self):
        model = resolve_model_for_hermes({"model_tier": "nanoclaw"})
        assert "haiku" in model

    def test_unknown_tier_defaults(self):
        model = resolve_model_for_hermes({"model_tier": "unknown_xyz"})
        assert model == "anthropic/claude-sonnet-4-6"


class TestConstants:
    def test_timeout_is_reasonable(self):
        assert 60 <= WALL_CLOCK_TIMEOUT_SECONDS <= 300
```

### Verification

```bash
cd harness && python -m pytest tests/test_hermes_adapter.py -x -q
```

---

## Task 6: Run Full Test Suite

### Verification

```bash
cd harness && python -m pytest tests/ -x -q --timeout=60 2>&1 | tail -20
```

Also verify worker spec validation:

```bash
node scripts/validate-worker-specs.ts
python scripts/validate-contracts.py
```

---

## Execution Order

```
Task 1  →  Create hermes_adapter.py
Task 2  →  Feature flag branch in base.py:run_worker()
Task 3  →  Worker skills in context_assembly.py + knowledge/worker-skills/
Task 4  →  Skill candidate detection stub in verification.py
Task 5  →  Adapter tests
Task 6  →  Full test suite verification
```

One commit per task. Verify after each. Stop on first failure.
