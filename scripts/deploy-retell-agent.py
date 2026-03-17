#!/usr/bin/env python3
"""Deploy a Retell agent config from a local YAML knowledge node to Retell's API.

Usage:
    # Dry run with agent ID (resolves LLM ID automatically)
    python scripts/deploy-retell-agent.py --agent-id agent_xxx

    # Dry run with LLM ID directly
    python scripts/deploy-retell-agent.py --llm-id llm_xxx

    # Apply changes to production
    python scripts/deploy-retell-agent.py --agent-id agent_xxx --apply

    # Use a different YAML source
    python scripts/deploy-retell-agent.py --agent-id agent_xxx --config path/to/config.yaml

    # Diff only (exit 0 if no changes, exit 1 if changes exist)
    python scripts/deploy-retell-agent.py --agent-id agent_xxx --diff-only

Environment:
    RETELL_API_KEY — required. Found in Retell dashboard → API Keys.

How it works:
    1. Loads the YAML config (strips knowledge node frontmatter, extracts 'config' key)
    2. Fetches the current LLM config from Retell API
    3. Computes a field-by-field diff
    4. In dry-run mode: prints the diff and exits
    5. With --apply: PATCHes the LLM config via Retell API
    6. Verifies the update by re-fetching and comparing

The YAML 'config' key maps directly to Retell's LLM request body:
    config.general_prompt → general_prompt
    config.states → states
    config.general_tools → general_tools
    config.model → model
    etc.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install with: pip install httpx", file=sys.stderr)
    sys.exit(1)


RETELL_API_BASE = "https://api.retellai.com"
DEFAULT_CONFIG = "knowledge/industry-packs/hvac/voice/retell-agent-v10.yaml"

# Fields we sync from YAML to Retell. Other fields (voice_id, etc.) are agent-level, not LLM-level.
SYNC_FIELDS = [
    "general_prompt",
    "general_tools",
    "states",
    "starting_state",
    "model",
    "model_temperature",
    "model_high_priority",
    "tool_call_strict_mode",
    "begin_message",
    "default_dynamic_variables",
]


def resolve_llm_id(agent_id: str, api_key: str) -> str:
    """Fetch agent config from Retell and extract the LLM ID.

    Retell separates agents (phone routing, voice) from LLMs (prompts, states, tools).
    The agent references the LLM via response_engine.llm_id.
    """
    resp = httpx.get(
        f"{RETELL_API_BASE}/get-agent/{agent_id}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"Error: Retell API returned {resp.status_code} for agent {agent_id}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    agent = resp.json()

    # Try response_engine.llm_id (current API format)
    llm_id = None
    response_engine = agent.get("response_engine")
    if isinstance(response_engine, dict):
        llm_id = response_engine.get("llm_id")

    # Fallback: try top-level llm_websocket_url which contains the llm_id
    if not llm_id:
        ws_url = agent.get("llm_websocket_url", "")
        if ws_url:
            llm_id = ws_url.rstrip("/").split("/")[-1]

    if not llm_id:
        print(f"Error: Could not find LLM ID for agent {agent_id}. Agent response keys: {list(agent.keys())}", file=sys.stderr)
        sys.exit(1)

    return llm_id


def load_yaml_config(path: str) -> dict[str, Any]:
    """Load the Retell LLM config from a YAML knowledge node.

    Strips the frontmatter (id, title, graph, etc.) and returns the 'config' dict.
    """
    with open(path) as f:
        doc = yaml.safe_load(f)

    if "config" not in doc:
        print(f"Error: YAML file {path} has no 'config' key.", file=sys.stderr)
        sys.exit(1)

    return doc["config"]


def fetch_current_config(llm_id: str, api_key: str) -> dict[str, Any]:
    """Fetch the current LLM config from Retell API."""
    resp = httpx.get(
        f"{RETELL_API_BASE}/get-retell-llm/{llm_id}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"Error: Retell API returned {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def compute_diff(local: dict, remote: dict) -> list[dict]:
    """Compare local YAML config against remote Retell config.

    Returns a list of changes: [{field, local, remote, action}]
    """
    changes = []
    for field in SYNC_FIELDS:
        local_val = local.get(field)
        remote_val = remote.get(field)

        # Normalize: None and missing are equivalent
        if local_val is None and remote_val is None:
            continue

        # Deep compare for complex types (states, tools)
        if json.dumps(local_val, sort_keys=True) != json.dumps(remote_val, sort_keys=True):
            changes.append({
                "field": field,
                "local": local_val,
                "remote": remote_val,
                "action": "update",
            })

    return changes


def print_diff(changes: list[dict]) -> None:
    """Print a human-readable diff."""
    if not changes:
        print("No changes detected. Local YAML matches Retell.")
        return

    print(f"\n{'='*60}")
    print(f"  {len(changes)} field(s) differ between local YAML and Retell")
    print(f"{'='*60}\n")

    for change in changes:
        field = change["field"]
        local = change["local"]
        remote = change["remote"]

        if field in ("general_prompt",):
            # For long strings, show a truncated diff
            local_str = (local or "")[:200]
            remote_str = (remote or "")[:200]
            print(f"  {field}:")
            print(f"    - remote: {remote_str!r}...")
            print(f"    + local:  {local_str!r}...")
        elif field in ("states",):
            # For states, show count and names
            local_names = [s.get("name", "?") for s in (local or [])]
            remote_names = [s.get("name", "?") for s in (remote or [])]
            print(f"  {field}:")
            print(f"    - remote: {len(remote_names)} states {remote_names}")
            print(f"    + local:  {len(local_names)} states {local_names}")
            # Show which states differ
            for name in set(local_names) | set(remote_names):
                local_state = next((s for s in (local or []) if s.get("name") == name), None)
                remote_state = next((s for s in (remote or []) if s.get("name") == name), None)
                if local_state and not remote_state:
                    print(f"      + NEW state: {name}")
                elif remote_state and not local_state:
                    print(f"      - REMOVED state: {name}")
                elif json.dumps(local_state, sort_keys=True) != json.dumps(remote_state, sort_keys=True):
                    print(f"      ~ CHANGED state: {name}")
        elif field in ("general_tools",):
            local_count = len(local or [])
            remote_count = len(remote or [])
            print(f"  {field}:")
            print(f"    - remote: {remote_count} tools")
            print(f"    + local:  {local_count} tools")
        else:
            print(f"  {field}:")
            print(f"    - remote: {remote!r}")
            print(f"    + local:  {local!r}")
        print()


def apply_config(llm_id: str, api_key: str, local: dict, changes: list[dict]) -> dict:
    """PATCH the Retell LLM with changed fields from local YAML."""
    payload = {}
    for change in changes:
        field = change["field"]
        payload[field] = local.get(field)

    resp = httpx.patch(
        f"{RETELL_API_BASE}/update-retell-llm/{llm_id}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"Error: Retell API returned {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    return resp.json()


def main():
    parser = argparse.ArgumentParser(
        description="Deploy Retell agent config from YAML to Retell API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    id_group = parser.add_mutually_exclusive_group(required=True)
    id_group.add_argument("--agent-id", help="Retell Agent ID (e.g., agent_xxx) — resolves LLM ID automatically")
    id_group.add_argument("--llm-id", help="Retell LLM ID directly (e.g., llm_xxx)")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help=f"YAML config path (default: {DEFAULT_CONFIG})")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    parser.add_argument("--diff-only", action="store_true", help="Exit 0 if no changes, 1 if changes exist")
    args = parser.parse_args()

    api_key = os.environ.get("RETELL_API_KEY")
    if not api_key:
        print("Error: RETELL_API_KEY environment variable is required.", file=sys.stderr)
        sys.exit(1)

    # Resolve LLM ID from agent ID if needed
    llm_id = args.llm_id
    if args.agent_id:
        print(f"Resolving LLM ID for agent: {args.agent_id}")
        llm_id = resolve_llm_id(args.agent_id, api_key)
        print(f"Resolved LLM ID: {llm_id}")

    # Resolve config path relative to repo root
    config_path = Path(args.config)
    if not config_path.is_absolute():
        # Try relative to CWD, then relative to repo root
        if not config_path.exists():
            repo_root = Path(__file__).parent.parent
            config_path = repo_root / args.config
    if not config_path.exists():
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading local config: {config_path}")
    local = load_yaml_config(str(config_path))

    print(f"Fetching remote config: {llm_id}")
    remote = fetch_current_config(llm_id, api_key)

    changes = compute_diff(local, remote)
    print_diff(changes)

    if args.diff_only:
        sys.exit(1 if changes else 0)

    if not changes:
        sys.exit(0)

    if not args.apply:
        print("Dry run — no changes applied. Use --apply to push to Retell.")
        sys.exit(0)

    print(f"Applying {len(changes)} change(s) to Retell LLM {llm_id}...")
    result = apply_config(llm_id, api_key, local, changes)

    # Verify
    print("Verifying...")
    updated = fetch_current_config(llm_id, api_key)
    verify_changes = compute_diff(local, updated)
    if verify_changes:
        print(f"WARNING: {len(verify_changes)} field(s) still differ after update!", file=sys.stderr)
        print_diff(verify_changes)
        sys.exit(1)
    else:
        version = result.get("version", "?")
        print(f"\nDeployed successfully. Retell LLM version: {version}")
        print(f"Verify in Retell dashboard: https://dashboard.retellai.com")


if __name__ == "__main__":
    main()
