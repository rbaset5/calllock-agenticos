#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLDEN_SET_PATH = REPO_ROOT / "knowledge" / "voice-pipeline" / "eval" / "golden-set.yaml"
PASS_THRESHOLD = 0.95
VOICE_EVAL_MIN_CASES = 50


def _ensure_harness_src() -> None:
    harness_src = REPO_ROOT / "harness" / "src"
    if str(harness_src) not in sys.path:
        sys.path.insert(0, str(harness_src))


def _load_extraction_runner() -> Callable[[str | None, dict[str, Any] | None], dict[str, Any]]:
    _ensure_harness_src()
    from voice.extraction.pipeline import run_extraction

    return run_extraction


def _load_safety_runner() -> Callable[..., list[dict[str, Any]]]:
    _ensure_harness_src()
    from voice.production.safety_monitor import evaluate_call_safety

    return evaluate_call_safety


def load_golden_set(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Golden set not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    calls = payload.get("calls")
    if not isinstance(calls, list) or not calls:
        raise SystemExit(f"No calls found in golden set: {path}")
    return payload


def _transcript_snippet(transcript: str, limit: int = 140) -> str:
    flattened = " ".join(transcript.split())
    if len(flattened) <= limit:
        return flattened
    return f"{flattened[:limit - 3]}..."


def _compare_scalar(
    *,
    call_id: str,
    field: str,
    expected: Any,
    actual: Any,
    transcript: str,
) -> list[dict[str, Any]]:
    if actual == expected:
        return []
    return [
        {
            "call_id": call_id,
            "field": field,
            "expected": expected,
            "actual": actual,
            "transcript_snippet": _transcript_snippet(transcript),
        }
    ]


def compare_call(
    call: dict[str, Any],
    extraction_output: dict[str, Any],
) -> list[dict[str, Any]]:
    call_id = str(call.get("id", "unknown"))
    transcript = str(call.get("transcript", ""))
    expected_fields = call.get("expected_fields") or {}
    if not isinstance(expected_fields, dict):
        raise SystemExit(f"expected_fields must be a mapping for call {call_id}")

    failures: list[dict[str, Any]] = []
    for field, expected in expected_fields.items():
        actual = extraction_output.get(field)
        if field == "tags":
            expected_tags = expected if isinstance(expected, list) else []
            actual_tags = actual if isinstance(actual, list) else []
            missing_tags = [tag for tag in expected_tags if tag not in actual_tags]
            for tag in missing_tags:
                failures.append(
                    {
                        "call_id": call_id,
                        "field": "tags",
                        "expected": tag,
                        "actual": actual_tags,
                        "transcript_snippet": _transcript_snippet(transcript),
                    }
                )
            continue
        failures.extend(
            _compare_scalar(
                call_id=call_id,
                field=field,
                expected=expected,
                actual=actual,
                transcript=transcript,
            )
        )

    expected_revenue_tier = call.get("expected_revenue_tier")
    if expected_revenue_tier is not None:
        failures.extend(
            _compare_scalar(
                call_id=call_id,
                field="revenue_tier",
                expected=expected_revenue_tier,
                actual=extraction_output.get("revenue_tier"),
                transcript=transcript,
            )
        )

    return failures


def _expected_safety_items(call: dict[str, Any]) -> list[dict[str, Any]] | None:
    expected = call.get("expected_safety_findings")
    if expected is None:
        return None
    if not isinstance(expected, list):
        raise SystemExit(f"expected_safety_findings must be a list for call {call.get('id', 'unknown')}")
    normalized: list[dict[str, Any]] = []
    for item in expected:
        if not isinstance(item, dict):
            raise SystemExit(f"expected_safety_findings entries must be mappings for call {call.get('id', 'unknown')}")
        normalized.append(
            {
                "finding_type": item.get("finding_type"),
                "severity": item.get("severity"),
            }
        )
    return normalized


def _actual_safety_items(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "finding_type": finding.get("finding_type"),
            "severity": finding.get("severity"),
        }
        for finding in findings
    ]


def _build_safety_call_record(
    *,
    call: dict[str, Any],
    transcript: str,
    raw_payload: dict[str, Any],
    extraction_output: dict[str, Any],
) -> dict[str, Any]:
    custom_metadata = raw_payload.get("custom_metadata")
    metadata = custom_metadata if isinstance(custom_metadata, dict) else {}
    return {
        "tenant_id": metadata.get("tenant_id") or raw_payload.get("tenant_id") or "eval-tenant",
        "call_id": str(call.get("id", "unknown")),
        "retell_call_id": str(raw_payload.get("call_id") or call.get("id", "unknown")),
        "transcript": transcript,
        "raw_retell_payload": raw_payload,
        "booking_id": raw_payload.get("booking_id") or extraction_output.get("booking_id"),
        "callback_scheduled": bool(raw_payload.get("callback_scheduled") or extraction_output.get("callback_scheduled")),
        "end_call_reason": raw_payload.get("end_call_reason") or extraction_output.get("end_call_reason"),
        "extraction_status": extraction_output.get("extraction_status", "complete"),
        "extracted_fields": extraction_output,
    }


def compare_safety(
    call: dict[str, Any],
    *,
    transcript: str,
    raw_payload: dict[str, Any],
    extraction_output: dict[str, Any],
    safety_runner: Callable[..., list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    expected = _expected_safety_items(call)
    if expected is None:
        return []

    tool_calls = raw_payload.get("voice_tool_calls") or raw_payload.get("tool_calls") or []
    if not isinstance(tool_calls, list):
        raise SystemExit(f"tool calls must be a list for call {call.get('id', 'unknown')}")
    findings = safety_runner(
        call_record=_build_safety_call_record(
            call=call,
            transcript=transcript,
            raw_payload=raw_payload,
            extraction_output=extraction_output,
        ),
        tool_calls=tool_calls,
        events=[],
    )
    actual = _actual_safety_items(findings)
    if sorted(actual, key=lambda item: (str(item.get("finding_type")), str(item.get("severity")))) == sorted(
        expected,
        key=lambda item: (str(item.get("finding_type")), str(item.get("severity"))),
    ):
        return []
    return [
        {
            "call_id": str(call.get("id", "unknown")),
            "field": "expected_safety_findings",
            "expected": expected,
            "actual": actual,
            "transcript_snippet": _transcript_snippet(transcript),
        }
    ]


def build_report(
    golden_set: dict[str, Any],
    *,
    extraction_runner: Callable[[str | None, dict[str, Any] | None], dict[str, Any]] | None = None,
    safety_runner: Callable[..., list[dict[str, Any]]] | None = None,
    min_cases: int | None = None,
) -> tuple[dict[str, Any], int]:
    run_extraction = extraction_runner or _load_extraction_runner()
    run_safety = safety_runner or _load_safety_runner()
    calls = golden_set["calls"]
    all_failures: list[dict[str, Any]] = []
    failed_call_ids: set[str] = set()
    safety_failures: list[dict[str, Any]] = []
    safety_failed_call_ids: set[str] = set()
    safety_checked_call_ids: set[str] = set()
    minimum_cases = VOICE_EVAL_MIN_CASES if min_cases is None else min_cases
    coverage_failures: list[dict[str, Any]] = []
    if len(calls) < minimum_cases:
        coverage_failures.append(
            {
                "reason": "minimum_case_count",
                "expected_minimum": minimum_cases,
                "actual": len(calls),
            }
        )

    for call in calls:
        if not isinstance(call, dict):
            raise SystemExit("Each golden set call must be a mapping")
        transcript = str(call.get("transcript", ""))
        raw_payload = call.get("raw_payload")
        if raw_payload is not None and not isinstance(raw_payload, dict):
            raise SystemExit(f"raw_payload must be a mapping for call {call.get('id', 'unknown')}")
        extraction_output = run_extraction(transcript, raw_payload or {})
        call_failures = compare_call(call, extraction_output)
        if call_failures:
            failed_call_ids.add(str(call.get("id", "unknown")))
            all_failures.extend(call_failures)
        call_safety_failures = compare_safety(
            call,
            transcript=transcript,
            raw_payload=raw_payload or {},
            extraction_output=extraction_output,
            safety_runner=run_safety,
        )
        if call.get("expected_safety_findings") is not None:
            safety_checked_call_ids.add(str(call.get("id", "unknown")))
        if call_safety_failures:
            safety_failed_call_ids.add(str(call.get("id", "unknown")))
            safety_failures.extend(call_safety_failures)

    total_calls = len(calls)
    passed_calls = total_calls - len(failed_call_ids)
    accuracy = (passed_calls / total_calls) if total_calls else 0.0
    safety_passed = len(safety_checked_call_ids) - len(safety_failed_call_ids)
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_calls": total_calls,
        "min_cases": minimum_cases,
        "pass": passed_calls,
        "fail": len(failed_call_ids),
        "accuracy": round(accuracy, 4),
        "failures": all_failures,
        "coverage_failures": coverage_failures,
        "safety_checked": len(safety_checked_call_ids),
        "safety_pass": safety_passed,
        "safety_fail": len(safety_failed_call_ids),
        "safety_failures": safety_failures,
    }
    exit_code = 0 if accuracy >= PASS_THRESHOLD and not coverage_failures and not safety_failures else 1
    return report, exit_code


def main() -> int:
    golden_set_path = Path(os.getenv("VOICE_GOLDEN_SET_PATH", str(DEFAULT_GOLDEN_SET_PATH)))
    golden_set = load_golden_set(golden_set_path)
    min_cases = int(os.getenv("VOICE_EVAL_MIN_CASES", str(VOICE_EVAL_MIN_CASES)))
    report, exit_code = build_report(golden_set, min_cases=min_cases)
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
