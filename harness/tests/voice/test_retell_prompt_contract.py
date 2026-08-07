"""Contract checks for the Retell lookup-state prompt."""

from __future__ import annotations

from pathlib import Path

import yaml


def _agent_config() -> dict:
    path = Path(__file__).resolve().parents[3] / "knowledge" / "industry-packs" / "hvac" / "voice" / "retell-agent-v10.yaml"
    docs = [doc for doc in yaml.safe_load_all(path.read_text()) if isinstance(doc, dict)]
    return next(doc for doc in docs if "config" in doc)


def test_lookup_state_uses_known_name_as_statement_only() -> None:
    config = _agent_config()["config"]
    lookup_state = next(state for state in config["states"] if state["name"] == "lookup")
    prompt = lookup_state["state_prompt"]

    assert 'Response field "customerName"' in prompt
    assert "Good to hear from you again, [name]." in prompt
    assert "Do NOT ask follow-up questions." in prompt
    assert "Is this [name]" not in prompt
    assert "same system" not in prompt.lower()
