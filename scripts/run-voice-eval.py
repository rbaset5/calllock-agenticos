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


def _load_extraction_runner() -> Callable[[str | None, dict[str, Any] | None], dict[str, Any]]:
    harness_src = REPO_ROOT / "harness" / "src"
    if str(harness_src) not in sys.path:
        sys.path.insert(0, str(harness_src))
    from voice.extraction.pipeline import run_extraction

    return run_extraction


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


def build_report(
    golden_set: dict[str, Any],
    *,
    extraction_runner: Callable[[str | None, dict[str, Any] | None], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], int]:
    run_extraction = extraction_runner or _load_extraction_runner()
    calls = golden_set["calls"]
    all_failures: list[dict[str, Any]] = []
    failed_call_ids: set[str] = set()

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

    total_calls = len(calls)
    passed_calls = total_calls - len(failed_call_ids)
    accuracy = (passed_calls / total_calls) if total_calls else 0.0
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_calls": total_calls,
        "pass": passed_calls,
        "fail": len(failed_call_ids),
        "accuracy": round(accuracy, 4),
        "failures": all_failures,
    }
    exit_code = 0 if accuracy >= PASS_THRESHOLD else 1
    return report, exit_code


def main() -> int:
    golden_set_path = Path(os.getenv("VOICE_GOLDEN_SET_PATH", str(DEFAULT_GOLDEN_SET_PATH)))
    golden_set = load_golden_set(golden_set_path)
    report, exit_code = build_report(golden_set)
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
