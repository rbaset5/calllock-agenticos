"""Daily voice health check service for eng-ai-voice."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Literal, TypedDict

import httpx
import yaml

from voice.extraction.pipeline import run_extraction

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
SEAM_CONTRACT_PATH = REPO_ROOT / "knowledge" / "voice-pipeline" / "seam-contract.yaml"
VOICE_CONTRACT_PATH = REPO_ROOT / "knowledge" / "voice-pipeline" / "voice-contract.yaml"
TAXONOMY_PATH = REPO_ROOT / "knowledge" / "industry-packs" / "hvac" / "taxonomy.yaml"
DEPLOY_SCRIPT_PATH = REPO_ROOT / "scripts" / "deploy-retell-agent.py"
CALL_SAMPLE_LIMIT = 10
EXTRACTION_TARGET = 0.95
CLASSIFICATION_TARGET = 0.97
ZERO_TAG_TARGET_MAX = 0.05

_COLUMN_FALLBACKS = {
    "customer_phone": "phone_number",
    "urgency_tier": "urgency_tier",
    "caller_type": "caller_type",
    "primary_intent": "primary_intent",
    "route": "route",
    "end_call_reason": "end_call_reason",
    "revenue_tier": "revenue_tier",
    "tags": "tags",
    "quality_score": "quality_score",
}
_CLASSIFICATION_FIELDS = {
    "caller_type",
    "dashboard_urgency",
    "end_call_reason",
    "hvac_issue_type",
    "primary_intent",
    "quality_score",
    "revenue_estimate",
    "revenue_tier",
    "route",
    "safety_emergency",
    "scorecard_warnings",
    "tag_categories",
    "tags",
    "urgency_tier",
}


class HealthReport(TypedDict):
    agent: Literal["eng-ai-voice"]
    report_type: Literal["voice-health-check"]
    date: str
    status: Literal["green", "yellow", "red"]
    calls_sampled: int
    extraction_accuracy: float
    classification_accuracy: float
    zero_tag_rate: float
    config_drift: bool
    scorecard_warnings: int
    issues_created: int
    prs_created: int


@dataclass(frozen=True)
class ContractField:
    name: str
    extraction: str


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _supabase_headers() -> dict[str, str]:
    key = _require_env("SUPABASE_SERVICE_ROLE_KEY")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }


def list_recent_call_records(
    *,
    limit: int = CALL_SAMPLE_LIMIT,
    transport: httpx.BaseTransport | None = None,
) -> list[dict[str, Any]]:
    url = f"{_require_env('SUPABASE_URL').rstrip('/')}/rest/v1/call_records"
    params = {
        "select": "call_id,transcript,raw_retell_payload,extracted_fields,tags,quality_score,urgency_tier,caller_type,primary_intent,route,revenue_tier,end_call_reason,phone_number,created_at",
        "order": "created_at.desc",
        "limit": str(limit),
    }

    with httpx.Client(timeout=15.0, transport=transport) as client:
        response = client.get(url, headers=_supabase_headers(), params=params)
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, list):
        raise RuntimeError("Supabase call_records query returned a non-list payload")
    return [row for row in payload if isinstance(row, dict)]


def _load_seam_contract(path: Path = SEAM_CONTRACT_PATH) -> list[ContractField]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    raw_fields = payload.get("fields", [])
    if not raw_fields and payload.get("field_mappings"):
        with VOICE_CONTRACT_PATH.open("r", encoding="utf-8") as handle:
            voice_payload = yaml.safe_load(handle) or {}
        raw_fields = voice_payload.get("fields", [])

    fields: list[ContractField] = []
    for item in raw_fields:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        extraction = item.get("extraction")
        if isinstance(name, str) and isinstance(extraction, str):
            fields.append(ContractField(name=name, extraction=extraction))
    if not fields:
        raise RuntimeError(f"No seam-contract fields found in {path}")
    return fields


def _load_expected_taxonomy_tags(path: Path = TAXONOMY_PATH) -> set[str]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        raise RuntimeError(f"Malformed HVAC taxonomy file at {path}")

    payload = yaml.safe_load(parts[2]) or {}
    categories = payload.get("categories", {})
    if not isinstance(categories, dict):
        raise RuntimeError(f"Taxonomy file {path} is missing categories")

    expected: set[str] = set()
    for tags in categories.values():
        if not isinstance(tags, list):
            continue
        for tag in tags:
            if isinstance(tag, dict) and isinstance(tag.get("name"), str):
                expected.add(tag["name"])

    if not expected:
        raise RuntimeError(f"No taxonomy tags found in {path}")
    return expected


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        normalized = [_normalize(item) for item in value]
        try:
            return sorted(normalized)
        except TypeError:
            return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, dict):
        return {key: _normalize(val) for key, val in sorted(value.items())}
    if isinstance(value, (int, float)):
        return float(value)
    return value


def _has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def _stored_field_value(row: Mapping[str, Any], field_name: str) -> Any:
    extracted_fields = row.get("extracted_fields")
    if isinstance(extracted_fields, Mapping) and field_name in extracted_fields:
        return extracted_fields[field_name]

    column_name = _COLUMN_FALLBACKS.get(field_name, field_name)
    return row.get(column_name)


def _calculate_accuracy(
    rows: Iterable[Mapping[str, Any]],
    *,
    field_names: set[str],
) -> float:
    compared = 0
    matched = 0

    for row in rows:
        extracted_fields = row.get("extracted_fields")
        stored_fields = extracted_fields if isinstance(extracted_fields, Mapping) else {}
        rerun = row["rerun_extraction"]

        for field_name in field_names:
            contract_field = row["contract_fields"][field_name]
            stored_value = _stored_field_value(row, field_name)
            rerun_value = rerun.get(field_name)

            should_compare = contract_field.extraction == "required" or _has_meaningful_value(stored_value) or _has_meaningful_value(rerun_value)
            if not should_compare:
                continue

            compared += 1
            if _normalize(stored_value) == _normalize(rerun_value):
                matched += 1

        # Keep stored_fields referenced so type checking does not treat the mapping as unused.
        _ = stored_fields

    if compared == 0:
        return 1.0
    return round(matched / compared, 4)


def _has_unknown_tags(tags: Iterable[Any], expected_tags: set[str]) -> bool:
    return any(isinstance(tag, str) and tag not in expected_tags for tag in tags)


def _run_config_drift_check() -> tuple[bool, bool]:
    env = os.environ.copy()
    args = [sys.executable, str(DEPLOY_SCRIPT_PATH), "--diff-only"]

    if env.get("RETELL_LLM_ID"):
        args.extend(["--llm-id", env["RETELL_LLM_ID"]])
    elif env.get("RETELL_AGENT_ID"):
        args.extend(["--agent-id", env["RETELL_AGENT_ID"]])
    else:
        logger.warning("voice.health_check.config_id_missing")
        return True, True

    try:
        result = subprocess.run(
            args,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except OSError:
        logger.exception("voice.health_check.config_diff_failed")
        return True, True

    combined_output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode == 0:
        return False, False
    if result.returncode == 1 and not combined_output.startswith("Error:"):
        return True, False

    logger.error(
        "voice.health_check.config_diff_error",
        extra={"returncode": result.returncode, "output": combined_output},
    )
    return True, True


def _determine_status(
    *,
    calls_sampled: int,
    extraction_accuracy: float,
    classification_accuracy: float,
    zero_tag_rate: float,
    config_drift: bool,
    config_check_failed: bool,
    taxonomy_drift_detected: bool,
    scorecard_warnings: int,
) -> Literal["green", "yellow", "red"]:
    if (
        calls_sampled == 0
        or config_check_failed
        or extraction_accuracy < 0.90
        or classification_accuracy < 0.90
        or zero_tag_rate > 0.20
    ):
        return "red"

    if (
        config_drift
        or taxonomy_drift_detected
        or extraction_accuracy < EXTRACTION_TARGET
        or classification_accuracy < CLASSIFICATION_TARGET
        or zero_tag_rate > ZERO_TAG_TARGET_MAX
        or scorecard_warnings > 0
    ):
        return "yellow"

    return "green"


def run_daily_health_check(
    *,
    limit: int = CALL_SAMPLE_LIMIT,
    today: date | None = None,
    transport: httpx.BaseTransport | None = None,
) -> HealthReport:
    contract_fields = {field.name: field for field in _load_seam_contract()}
    expected_tags = _load_expected_taxonomy_tags()
    rows = list_recent_call_records(limit=limit, transport=transport)

    enriched_rows: list[dict[str, Any]] = []
    zero_tag_calls = 0
    scorecard_warning_count = 0
    taxonomy_drift_detected = False

    extraction_field_names = {
        name for name, field in contract_fields.items()
        if field.extraction != "not_applicable" and name not in _CLASSIFICATION_FIELDS
    }
    classification_field_names = {
        name for name, field in contract_fields.items()
        if field.extraction != "not_applicable" and name in _CLASSIFICATION_FIELDS
    }

    for row in rows:
        raw_payload = row.get("raw_retell_payload")
        payload_mapping = raw_payload if isinstance(raw_payload, Mapping) else {}
        transcript = row.get("transcript")
        transcript_text = transcript if isinstance(transcript, str) else str(payload_mapping.get("transcript") or "")
        rerun_extraction = run_extraction(transcript_text, payload_mapping)

        tags = rerun_extraction.get("tags")
        rerun_tags = tags if isinstance(tags, list) else []
        stored_tags = _stored_field_value(row, "tags")
        stored_tag_list = stored_tags if isinstance(stored_tags, list) else []

        if not rerun_tags:
            zero_tag_calls += 1
        scorecard_warnings = rerun_extraction.get("scorecard_warnings")
        if isinstance(scorecard_warnings, list):
            scorecard_warning_count += len(scorecard_warnings)

        if _has_unknown_tags(rerun_tags, expected_tags) or _has_unknown_tags(stored_tag_list, expected_tags):
            taxonomy_drift_detected = True

        enriched_row = dict(row)
        enriched_row["rerun_extraction"] = rerun_extraction
        enriched_row["contract_fields"] = contract_fields
        enriched_rows.append(enriched_row)

    extraction_accuracy = _calculate_accuracy(enriched_rows, field_names=extraction_field_names)
    classification_accuracy = _calculate_accuracy(enriched_rows, field_names=classification_field_names)

    calls_sampled = len(enriched_rows)
    zero_tag_rate = round((zero_tag_calls / calls_sampled), 4) if calls_sampled else 0.0
    config_drift, config_check_failed = _run_config_drift_check()
    report_date = (today or date.today()).isoformat()

    return {
        "agent": "eng-ai-voice",
        "report_type": "voice-health-check",
        "date": report_date,
        "status": _determine_status(
            calls_sampled=calls_sampled,
            extraction_accuracy=extraction_accuracy,
            classification_accuracy=classification_accuracy,
            zero_tag_rate=zero_tag_rate,
            config_drift=config_drift,
            config_check_failed=config_check_failed,
            taxonomy_drift_detected=taxonomy_drift_detected,
            scorecard_warnings=scorecard_warning_count,
        ),
        "calls_sampled": calls_sampled,
        "extraction_accuracy": extraction_accuracy,
        "classification_accuracy": classification_accuracy,
        "zero_tag_rate": zero_tag_rate,
        "config_drift": config_drift,
        "scorecard_warnings": scorecard_warning_count,
        "issues_created": 0,
        "prs_created": 0,
    }


__all__ = ["HealthReport", "list_recent_call_records", "run_daily_health_check"]
