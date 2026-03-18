#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT_PATH = REPO_ROOT / "knowledge" / "voice-pipeline" / "seam-contract.yaml"
CALLS_SAMPLED = 10


@dataclass(frozen=True)
class ContractField:
    name: str
    extraction: str
    app_display: str
    supabase: str
    enum_values: tuple[str, ...]


def require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def load_contract(path: Path) -> list[ContractField]:
    if not path.exists():
        raise SystemExit(f"Seam contract not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    fields_section = raw.get("fields", raw)
    fields: list[ContractField] = []

    if isinstance(fields_section, list):
        for item in fields_section:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("field")
            if not isinstance(name, str) or not name:
                continue
            fields.append(parse_contract_field(name, item))
    elif isinstance(fields_section, dict):
        for name, spec in fields_section.items():
            if isinstance(name, str) and isinstance(spec, dict):
                fields.append(parse_contract_field(name, spec))

    if not fields:
        raise SystemExit(f"No fields found in seam contract: {path}")
    return fields


def parse_contract_field(name: str, spec: dict[str, Any]) -> ContractField:
    enum_values = spec.get("enum")
    if not isinstance(enum_values, list):
        enum_values = spec.get("enum_values")
    if not isinstance(enum_values, list):
        enum_values = []

    cleaned_enum_values = tuple(
        value for value in enum_values if isinstance(value, str) and value
    )
    return ContractField(
        name=name,
        extraction=str(spec.get("extraction", "")),
        app_display=str(spec.get("app_display", "")),
        supabase=str(spec.get("supabase", "")),
        enum_values=cleaned_enum_values,
    )


def fetch_recent_calls(
    supabase_url: str,
    supabase_key: str,
    *,
    limit: int = CALLS_SAMPLED,
    transport: httpx.BaseTransport | None = None,
) -> list[dict[str, Any]]:
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }
    params = {
        "select": "*",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    with httpx.Client(timeout=15.0, transport=transport) as client:
        response = client.get(f"{supabase_url.rstrip('/')}/rest/v1/call_records", headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, list):
        raise SystemExit("Unexpected Supabase response: expected a list of call_records")
    return [row for row in payload if isinstance(row, dict)]


def get_field_value(row: dict[str, Any], field_name: str) -> Any:
    if field_name in row:
        return row[field_name]

    extracted_fields = row.get("extracted_fields")
    if isinstance(extracted_fields, dict):
        return extracted_fields.get(field_name)

    return None


def has_extracted_field(row: dict[str, Any], field_name: str) -> bool:
    extracted_fields = row.get("extracted_fields")
    return isinstance(extracted_fields, dict) and field_name in extracted_fields


def add_check(
    checks: list[dict[str, str]],
    *,
    field: str,
    check: str,
    status: str,
    detail: str,
) -> None:
    checks.append(
        {
            "field": field,
            "check": check,
            "status": status,
            "detail": detail,
        }
    )


def run_checks(fields: list[ContractField], rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []

    for field in fields:
        if field.extraction == "required":
            present_count = sum(1 for row in rows if has_extracted_field(row, field.name))
            ratio = (present_count / len(rows)) if rows else 0.0
            status = "pass" if rows and ratio >= 0.95 else "fail"
            add_check(
                checks,
                field=field.name,
                check="extraction_completeness",
                status=status,
                detail=f"{present_count}/{len(rows)}",
            )

        if field.enum_values:
            allowed = set(field.enum_values)
            unknown_values: list[str] = []
            for row in rows:
                value = get_field_value(row, field.name)
                if value is None:
                    continue
                values = value if isinstance(value, list) else [value]
                for item in values:
                    if item is None:
                        continue
                    if item not in allowed and item not in unknown_values:
                        unknown_values.append(str(item))

            if unknown_values:
                detail = ", ".join(f"unknown value: {value!r}" for value in unknown_values)
                status = "fail"
            else:
                detail = "all values match enum"
                status = "pass"

            add_check(
                checks,
                field=field.name,
                check="enum_coverage",
                status=status,
                detail=detail,
            )

        orphaned = (
            field.extraction != "not_applicable"
            and field.app_display == "not_shown"
            and field.supabase == "not_stored"
        )
        add_check(
            checks,
            field=field.name,
            check="orphan_detection",
            status="warn" if orphaned else "pass",
            detail=(
                "extracts data but is neither shown in app nor stored in Supabase"
                if orphaned
                else "field has a visible or stored destination"
            ),
        )

    return checks


def summarize(checks: list[dict[str, str]]) -> dict[str, int]:
    summary = {"pass": 0, "fail": 0, "warn": 0}
    for check in checks:
        status = check["status"]
        if status in summary:
            summary[status] += 1
    return summary


def build_report(
    *,
    contract_path: Path,
    supabase_url: str,
    supabase_key: str,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    fields = load_contract(contract_path)
    rows = fetch_recent_calls(
        supabase_url,
        supabase_key,
        limit=CALLS_SAMPLED,
        transport=transport,
    )
    checks = run_checks(fields, rows)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "calls_sampled": CALLS_SAMPLED,
        "checks": checks,
        "summary": summarize(checks),
    }


def main() -> int:
    contract_path = Path(os.getenv("SEAM_CONTRACT_PATH", str(DEFAULT_CONTRACT_PATH)))
    report = build_report(
        contract_path=contract_path,
        supabase_url=require("SUPABASE_URL"),
        supabase_key=require("SUPABASE_SERVICE_ROLE_KEY"),
    )
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
