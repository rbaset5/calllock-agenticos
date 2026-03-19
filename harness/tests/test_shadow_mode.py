"""Tests for shadow mode comparison logic."""
from __future__ import annotations

from harness.graphs.workers.base import _compare_outputs


class TestCompareOutputs:
    def test_exact_match(self):
        baseline = {"summary": "all good", "status": "green"}
        hermes = {"summary": "all good", "status": "green"}
        result = _compare_outputs(baseline, hermes, ["summary", "status"])
        assert result["match_count"] == 2
        assert result["match_rate"] == 1.0
        assert result["mismatches"] == []

    def test_partial_match(self):
        baseline = {"summary": "all good", "status": "green"}
        hermes = {"summary": "all good", "status": "yellow"}
        result = _compare_outputs(baseline, hermes, ["summary", "status"])
        assert result["match_count"] == 1
        assert result["match_rate"] == 0.5
        assert result["mismatches"] == ["status"]

    def test_no_match(self):
        baseline = {"summary": "all good", "status": "green"}
        hermes = {"summary": "bad", "status": "red"}
        result = _compare_outputs(baseline, hermes, ["summary", "status"])
        assert result["match_count"] == 0
        assert result["match_rate"] == 0.0

    def test_hermes_none(self):
        baseline = {"summary": "all good", "status": "green"}
        result = _compare_outputs(baseline, None, ["summary", "status"])
        assert result["match_count"] == 0
        assert result["match_rate"] == 0.0
        assert result["mismatches"] == ["summary", "status"]

    def test_case_insensitive_string_match(self):
        baseline = {"summary": "All Good"}
        hermes = {"summary": "all good"}
        result = _compare_outputs(baseline, hermes, ["summary"])
        assert result["match_count"] == 1
        assert result["match_rate"] == 1.0

    def test_empty_fields(self):
        result = _compare_outputs({}, {}, [])
        assert result["match_count"] == 0
        assert result["match_rate"] == 0.0
        assert result["mismatches"] == []

    def test_none_values_match(self):
        baseline = {"summary": None}
        hermes = {"summary": None}
        result = _compare_outputs(baseline, hermes, ["summary"])
        assert result["match_count"] == 1
