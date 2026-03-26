"""Tests for skill promotion pipeline."""
from __future__ import annotations

from harness.skill_promotion import _slugify, promote_skill


class TestSlugify:
    def test_basic(self):
        assert _slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert _slugify("Multi-Unit HVAC Parsing!") == "multi-unit-hvac-parsing"

    def test_max_length(self):
        long = "a" * 100
        assert len(_slugify(long)) <= 60

    def test_consecutive_hyphens(self):
        assert _slugify("hello   world") == "hello-world"


class TestPromoteSkill:
    def test_creates_skill_file(self, tmp_path):
        candidate = {
            "id": "cand-123",
            "worker_id": "eng-ai-voice",
            "task_type": "extraction",
            "run_id": "run-456",
            "tenant_id": "tenant-789",
        }

        from unittest.mock import patch

        with patch("harness.skill_promotion.SKILLS_DIR", tmp_path):
            with patch("harness.skill_promotion.REPO_ROOT", tmp_path.parent):
                result = promote_skill(
                    candidate=candidate,
                    skill_title="Multi Unit Parsing",
                    skill_body="When encountering multiple units, extract each separately.",
                    promoted_by="rashid",
                    universal=True,
                )

        assert "path" in result
        assert "content" in result
        assert "multi-unit-parsing" in result["path"]
        assert "universal: true" in result["content"]
        assert "promoted_by: rashid" in result["content"]

        skill_file = tmp_path / "eng-ai-voice" / "multi-unit-parsing.md"
        assert skill_file.exists()
        content = skill_file.read_text()
        assert "Multi Unit Parsing" in content
        assert "extract each separately" in content


class TestSkillCandidateDetection:
    def test_high_confidence_triggers(self):
        from harness.nodes.verification import check_skill_candidate

        result = check_skill_candidate(
            worker_output={"summary": "good", "status": "green", "violations": [], "a": 1, "b": 2},
            verification={"outcome": "pass", "confidence": 0.95},
            worker_id="eng-ai-voice",
            task_type="health-check",
            run_id="run-123",
        )
        assert result is not None
        assert "high_confidence_pass" in result["signals"]

    def test_low_confidence_no_trigger(self):
        from harness.nodes.verification import check_skill_candidate

        result = check_skill_candidate(
            worker_output={"summary": "ok"},
            verification={"outcome": "pass", "confidence": 0.5},
            worker_id="eng-ai-voice",
            task_type="health-check",
            run_id="run-123",
        )
        assert result is None

    def test_exploratory_solve_triggers(self):
        from harness.nodes.verification import check_skill_candidate

        result = check_skill_candidate(
            worker_output={"summary": "found it", "_hermes_iterations": 8},
            verification={"outcome": "pass", "confidence": 0.7},
            worker_id="eng-ai-voice",
            task_type="investigation",
            run_id="run-456",
        )
        assert result is not None
        assert "exploratory_solve" in result["signals"]
