from __future__ import annotations

from pathlib import Path

from harness import context_tools


def _configure_repo_memory(monkeypatch, tmp_path: Path) -> None:
    decisions_dir = tmp_path / "decisions"
    errors_dir = tmp_path / "errors"
    knowledge_dir = tmp_path / "knowledge"
    decisions_dir.mkdir()
    errors_dir.mkdir()
    knowledge_dir.mkdir()
    (decisions_dir / "_index.md").write_text(
        "# Decisions Index\n\n## Voice Pipeline\n\n(none yet)\n\n## Product\n\n(none yet)\n\n## Architecture\n\n(none yet)\n"
    )
    (errors_dir / "_index.md").write_text(
        "# Errors Index\n\n## Voice Pipeline\n\n(none yet)\n\n## Product\n\n(none yet)\n\n## Architecture\n\n(none yet)\n"
    )
    monkeypatch.setattr(context_tools, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(context_tools, "DECISIONS_DIR", decisions_dir)
    monkeypatch.setattr(context_tools, "ERRORS_DIR", errors_dir)
    monkeypatch.setattr(context_tools, "KNOWLEDGE_DIR", knowledge_dir)


def test_create_decision_updates_correct_index_section(monkeypatch, tmp_path) -> None:
    _configure_repo_memory(monkeypatch, tmp_path)

    result = context_tools.create_decision(
        title="CallLock App scope stays customer-facing",
        domain="product",
        context="Need a durable founder-facing scope line.",
        options=[{"name": "App", "description": "Put internal tools in the app."}],
        decision="Keep the app customer-facing only.",
        consequences="Internal ops stays outside web/.",
    )

    assert result["path"].startswith("decisions/product/DEC-")
    index_text = (tmp_path / "decisions" / "_index.md").read_text()
    assert "- [CallLock App scope stays customer-facing](product/" in index_text
    assert "## Product" in index_text


def test_log_error_third_occurrence_sets_extract_threshold(monkeypatch, tmp_path) -> None:
    _configure_repo_memory(monkeypatch, tmp_path)

    context_tools.log_error(title="Webhook signature mismatch", domain="voice-pipeline", symptoms="Retell calls fail.")
    second = context_tools.log_error(title="Webhook signature mismatch", domain="voice-pipeline", symptoms="Retell calls fail again.")
    third = context_tools.log_error(title="Webhook signature mismatch", domain="voice-pipeline", symptoms="Retell calls fail a third time.")

    assert second["action"] == "bumped"
    assert third["occurrences"] == 3
    assert third["should_extract_rule"] is True


def test_decompose_problem_detects_voice_domain(monkeypatch, tmp_path) -> None:
    _configure_repo_memory(monkeypatch, tmp_path)

    result = context_tools.decompose_problem(
        raw_input="Retell webhook call extraction is broken in the voice pipeline after post-call processing."
    )

    assert result["detected_domain"] == "voice-pipeline"


def test_update_knowledge_reports_created_then_appended(monkeypatch, tmp_path) -> None:
    _configure_repo_memory(monkeypatch, tmp_path)

    created = context_tools.update_knowledge(path="company/mission.md", content="Initial mission")
    appended = context_tools.update_knowledge(path="company/mission.md", content="New note", append=True)

    assert created["action"] == "created"
    assert appended["action"] == "appended"
    assert (tmp_path / "knowledge" / "company" / "mission.md").read_text() == "Initial mission\n\nNew note\n"
