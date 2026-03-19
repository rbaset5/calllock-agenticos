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
