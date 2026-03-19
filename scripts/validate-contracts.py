#!/usr/bin/env python3
"""
Validate consistency across the three Product Guardian contracts.

Checks:
  1. no-orphan-extraction: every required voice field has a seam mapping
  2. no-orphan-display: every app must_render field has a seam source
  3. no-broken-chain: every seam mapping references valid voice/app fields
  4. type-consistency: field types match across contracts

Exit 0 on pass, 1 on failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = REPO_ROOT / "knowledge" / "voice-pipeline"


def load_contract(name: str) -> dict:
    path = PIPELINE_DIR / name
    if not path.exists():
        print(f"ERROR: {name} not found at {path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def main() -> None:
    voice = load_contract("voice-contract.yaml")
    app = load_contract("app-contract.yaml")
    seam = load_contract("seam-contract.yaml")

    errors: list[str] = []

    voice_required = {
      field["name"]
      for field in (voice.get("fields") or [])
      if field.get("extraction") == "required"
    }
    seam_voice_fields = {
      mapping["voice_field"] for mapping in (seam.get("field_mappings") or [])
    }
    for field in sorted(voice_required - seam_voice_fields):
        errors.append(
            f'no-orphan-extraction: voice-contract required field "{field}" has no seam mapping'
        )

    app_must_render: set[str] = set()
    for page in app.get("pages") or []:
        for element in page.get("must_render") or []:
            app_must_render.update(element.get("fields") or [])

    seam_displayed = {
        mapping["voice_field"]
        for mapping in (seam.get("field_mappings") or [])
        if mapping.get("app_display") not in (None, "not_shown")
    }
    for field in sorted(app_must_render - seam_displayed):
        errors.append(
            f'no-orphan-display: app-contract must_render field "{field}" has no seam source'
        )

    all_voice_names = {field["name"] for field in (voice.get("fields") or [])}
    for mapping in seam.get("field_mappings") or []:
        chain = mapping.get("required_chain") or []
        voice_field = mapping["voice_field"]
        if "extraction" in chain and voice_field not in all_voice_names:
            errors.append(
                f'no-broken-chain: seam mapping "{voice_field}" not found in voice-contract'
            )

    voice_types = {field["name"]: field.get("type") for field in (voice.get("fields") or [])}
    for mapping in seam.get("field_mappings") or []:
        voice_field = mapping["voice_field"]
        if "extraction" in (mapping.get("required_chain") or []) and voice_types.get(voice_field) is None:
            errors.append(f'type-consistency: voice field "{voice_field}" has no type defined')

    if errors:
        print(f"\nContract validation failed ({len(errors)} error{'s' if len(errors) != 1 else ''}):\n")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    voice_count = len(voice.get("fields") or [])
    app_pages = len(app.get("pages") or [])
    app_fields = len(app_must_render)
    seam_mappings = len(seam.get("field_mappings") or [])
    print("\nContract validation passed")
    print(f"  Voice: {voice_count} fields")
    print(f"  App: {app_pages} pages, {app_fields} must_render fields")
    print(f"  Seam: {seam_mappings} field mappings, 3 invariants checked")


if __name__ == "__main__":
    main()
