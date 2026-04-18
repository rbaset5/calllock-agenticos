from __future__ import annotations

import json

from harness.ceo_agent_config import CEO_TOOL_NAMES
from harness.tool_registry import export_tools_json, mutating_tool_names, tool_names


def test_registry_has_expected_tool_count() -> None:
    assert len(tool_names()) == 21
    assert len(set(tool_names())) == 21
    assert len(mutating_tool_names()) > 0


def test_ceo_config_derives_from_registry() -> None:
    assert CEO_TOOL_NAMES == tool_names()


def test_generated_tools_json_parity(tmp_path) -> None:
    output_path = tmp_path / "tools.json"
    export_tools_json(output_path)

    payload = json.loads(output_path.read_text())
    exported_names = [tool["name"] for tool in payload["tools"]]

    assert exported_names == tool_names()
    assert set(exported_names) == set(CEO_TOOL_NAMES)
