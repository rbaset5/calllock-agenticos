"""Retell config snapshot capture."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import os
from typing import Any

import yaml

from db import repository
from voice.production.evidence import hash_payload

REPO_ROOT = Path(__file__).resolve().parents[4]
RETELL_CONFIG_PATH = REPO_ROOT / "knowledge" / "industry-packs" / "hvac" / "voice" / "retell-agent-v10.yaml"
_SECRET_KEY_PARTS = ("api_key", "auth", "secret", "token")


def _redact_secrets(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower() for part in _SECRET_KEY_PARTS):
                continue
            redacted[key_text] = _redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    return value


def _load_config_snapshot(path: Path = RETELL_CONFIG_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        docs = [doc for doc in yaml.safe_load_all(handle) if doc]
    payload: dict[str, Any] = {}
    for doc in docs:
        if not isinstance(doc, dict):
            raise RuntimeError(f"Retell config documents must be mappings: {path}")
        payload.update(doc)
    if not payload:
        raise RuntimeError(f"Retell config must be a mapping: {path}")
    return _redact_secrets(payload)


def build_retell_config_snapshot(*, call_id: str, tenant_id: str | None) -> dict[str, Any]:
    """Build a persistable Retell config snapshot for a call."""
    config_snapshot = _load_config_snapshot()
    retell_agent_id = os.getenv("RETELL_AGENT_ID")
    retell_llm_id = os.getenv("RETELL_LLM_ID")
    hash_input = {
        "config_snapshot": config_snapshot,
        "retell_agent_id": retell_agent_id,
        "retell_llm_id": retell_llm_id,
    }
    return {
        "tenant_id": tenant_id,
        "call_id": call_id,
        "retell_agent_id": retell_agent_id,
        "retell_llm_id": retell_llm_id,
        "config_source_path": str(RETELL_CONFIG_PATH.relative_to(REPO_ROOT)),
        "config_hash": hash_payload(hash_input),
        "config_snapshot": config_snapshot,
    }


def record_retell_config_snapshot(*, call_id: str, tenant_id: str | None) -> dict[str, Any]:
    """Build and persist the Retell config snapshot for a call."""
    return repository.record_voice_config_snapshot(
        build_retell_config_snapshot(call_id=call_id, tenant_id=tenant_id)
    )
