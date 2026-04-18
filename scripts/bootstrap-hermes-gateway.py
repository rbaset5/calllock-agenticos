#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import os
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_SRC = REPO_ROOT / "harness" / "src"
HERMES_TEMPLATE_DIR = HARNESS_SRC / "hermes_gateway"
HERMES_HOME = Path.home() / ".hermes"
RUNTIME_DIR = HERMES_HOME / "calllock-gateway"
RUNTIME_CONFIG_PATH = HERMES_HOME / "config.yaml"
MANAGED_SERVER_NAME = "calllock_ceo_gateway"


def _ensure_yaml():
    try:
        import yaml  # type: ignore

        return yaml
    except ModuleNotFoundError:
        fallback_python = REPO_ROOT / "harness" / ".venv" / "bin" / "python"
        if fallback_python.exists() and Path(sys.executable) != fallback_python:
            os.execv(str(fallback_python), [str(fallback_python), __file__, *sys.argv[1:]])
        raise


yaml = _ensure_yaml()

if str(HARNESS_SRC) not in sys.path:
    sys.path.insert(0, str(HARNESS_SRC))

from harness.tool_registry import tool_names, tools_json_text


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text()) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a YAML mapping at the top level.")
    return loaded


def _dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False)


def _desired_runtime_assets() -> dict[Path, str]:
    return {
        RUNTIME_DIR / "config.template.yaml": (HERMES_TEMPLATE_DIR / "config.yaml").read_text(),
        RUNTIME_DIR / "system_prompt.md": (HERMES_TEMPLATE_DIR / "system_prompt.md").read_text(),
        RUNTIME_DIR / "tools.json": tools_json_text(),
    }


def _desired_mcp_server_entry() -> dict[str, Any]:
    return {
        "command": str(REPO_ROOT / "harness" / ".venv" / "bin" / "python"),
        "args": ["-m", "harness.mcp_server"],
        "env": {
            "PYTHONPATH": str(HARNESS_SRC),
        },
        "tools": {
            "include": tool_names(),
            "prompts": False,
            "resources": False,
        },
    }


def _desired_runtime_config(existing: dict[str, Any]) -> dict[str, Any]:
    config = dict(existing)
    mcp_servers = dict(config.get("mcp_servers") or {})
    mcp_servers[MANAGED_SERVER_NAME] = _desired_mcp_server_entry()
    config["mcp_servers"] = mcp_servers

    managed = dict(config.get("calllock_gateway") or {})
    managed.update(
        {
            "runtime_dir": str(RUNTIME_DIR),
            "system_prompt_file": str(RUNTIME_DIR / "system_prompt.md"),
            "template_config_file": str(RUNTIME_DIR / "config.template.yaml"),
            "tools_file": str(RUNTIME_DIR / "tools.json"),
        }
    )
    config["calllock_gateway"] = managed
    return config


def _diff_text(path: Path, expected: str) -> str | None:
    actual = path.read_text() if path.exists() else ""
    if actual == expected:
        return None
    return "".join(
        difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=str(path),
            tofile=f"{path} (expected)",
        )
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _config_drift(existing: dict[str, Any]) -> list[str]:
    drifts: list[str] = []
    actual_servers = dict(existing.get("mcp_servers") or {})
    expected_server = _desired_mcp_server_entry()
    if actual_servers.get(MANAGED_SERVER_NAME) != expected_server:
        drifts.append(f"{RUNTIME_CONFIG_PATH}: missing or stale mcp_servers.{MANAGED_SERVER_NAME}")

    actual_gateway = dict(existing.get("calllock_gateway") or {})
    expected_gateway = _desired_runtime_config({}).get("calllock_gateway", {})
    if actual_gateway != expected_gateway:
        drifts.append(f"{RUNTIME_CONFIG_PATH}: missing or stale calllock_gateway metadata block")
    return drifts


def run(mode: str) -> int:
    repo_tools_path = HERMES_TEMPLATE_DIR / "tools.json"
    expected_repo_tools = tools_json_text()

    drift_messages: list[str] = []
    runtime_assets = _desired_runtime_assets()
    existing_runtime_config = _load_yaml(RUNTIME_CONFIG_PATH)
    runtime_config = _desired_runtime_config(existing_runtime_config)
    runtime_config_text = _dump_yaml(runtime_config)

    if mode == "write":
        _write_text(repo_tools_path, expected_repo_tools)
        for asset_path, content in runtime_assets.items():
            _write_text(asset_path, content)
        _write_text(RUNTIME_CONFIG_PATH, runtime_config_text)
    else:
        repo_tools_diff = _diff_text(repo_tools_path, expected_repo_tools)
        if repo_tools_diff:
            drift_messages.append(repo_tools_diff)
        for asset_path, content in runtime_assets.items():
            diff = _diff_text(asset_path, content)
            if diff:
                drift_messages.append(diff)
        drift_messages.extend(_config_drift(existing_runtime_config))

    print(f"Repo tools manifest: {repo_tools_path}")
    print(f"Hermes runtime dir: {RUNTIME_DIR}")
    print(f"Hermes config: {RUNTIME_CONFIG_PATH}")
    print("")
    print("Local run steps:")
    print(f"1. Run `python {REPO_ROOT / 'scripts' / 'bootstrap-hermes-gateway.py'} --write`")
    print("2. Set `DISCORD_BOT_TOKEN` and `DISCORD_ALLOWED_USERS` in `~/.hermes/.env`.")
    print(f"3. Optional: enable writes with `export CALLLOCK_GATEWAY_WRITE_ENABLED=1` before `hermes gateway`.")
    print(f"4. Smoke test MCP directly with `cd {REPO_ROOT / 'harness'} && PYTHONPATH=src ./.venv/bin/python -m harness.mcp_server`.")
    print("5. Start Hermes with `hermes gateway` and reload MCP if needed with `/reload-mcp`.")

    if mode == "check" and drift_messages:
        print("")
        print("Drift detected:")
        for message in drift_messages:
            print(message.rstrip())
        return 1

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the local Hermes CEO gateway runtime.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Detect drift without mutating ~/.hermes.")
    mode.add_argument("--write", action="store_true", help="Sync assets and update ~/.hermes/config.yaml.")
    args = parser.parse_args()
    raise SystemExit(run("write" if args.write else "check"))


if __name__ == "__main__":
    main()
