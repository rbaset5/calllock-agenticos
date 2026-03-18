from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run-voice-eval.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_voice_eval", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_golden_set(tmp_path: Path) -> Path:
    golden_set_path = tmp_path / "golden-set.yaml"
    golden_set_path.write_text(
        """
version: "1.0"
description: "Test golden set"
calls:
  - id: "eval-001"
    description: "First call"
    transcript: |
      User: First test transcript.
    expected_fields:
      customer_name: "Pat Lee"
      tags:
        - "REPAIR_AC"
    expected_revenue_tier: "standard_repair"
  - id: "eval-002"
    description: "Second call"
    transcript: |
      User: Second test transcript.
    expected_fields:
      urgency_tier: "urgent"
      route: "legitimate"
    expected_revenue_tier: "diagnostic"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return golden_set_path


def test_eval_all_pass(tmp_path: Path) -> None:
    module = load_module()
    golden_set = module.load_golden_set(write_golden_set(tmp_path))

    outputs = [
        {
            "customer_name": "Pat Lee",
            "tags": ["REPAIR_AC", "PEAK_SUMMER"],
            "revenue_tier": "standard_repair",
        },
        {
            "urgency_tier": "urgent",
            "route": "legitimate",
            "revenue_tier": "diagnostic",
        },
    ]

    report, exit_code = module.build_report(
        golden_set,
        extraction_runner=lambda transcript, raw_payload: outputs.pop(0),
    )

    assert exit_code == 0
    assert report["pass"] == 2
    assert report["fail"] == 0
    assert report["accuracy"] == 1.0
    assert report["failures"] == []


def test_eval_partial_fail(tmp_path: Path) -> None:
    module = load_module()
    golden_set = module.load_golden_set(write_golden_set(tmp_path))

    outputs = [
        {
            "customer_name": "Pat Lee",
            "tags": ["REPAIR_AC"],
            "revenue_tier": "standard_repair",
        },
        {
            "urgency_tier": "routine",
            "route": "legitimate",
            "revenue_tier": "diagnostic",
        },
    ]

    report, exit_code = module.build_report(
        golden_set,
        extraction_runner=lambda transcript, raw_payload: outputs.pop(0),
    )

    assert exit_code == 1
    assert report["pass"] == 1
    assert report["fail"] == 1
    assert report["failures"][0]["field"] == "urgency_tier"
    assert report["failures"][0]["expected"] == "urgent"
    assert report["failures"][0]["actual"] == "routine"


def test_eval_missing_field(tmp_path: Path) -> None:
    module = load_module()
    golden_set = module.load_golden_set(write_golden_set(tmp_path))

    outputs = [
        {
            "customer_name": None,
            "tags": ["REPAIR_AC"],
            "revenue_tier": "standard_repair",
        },
        {
            "urgency_tier": "urgent",
            "route": "legitimate",
            "revenue_tier": "diagnostic",
        },
    ]

    report, _ = module.build_report(
        golden_set,
        extraction_runner=lambda transcript, raw_payload: outputs.pop(0),
    )

    assert report["fail"] == 1
    assert report["failures"][0]["field"] == "customer_name"
    assert report["failures"][0]["actual"] is None


def test_eval_tag_subset(tmp_path: Path) -> None:
    module = load_module()
    golden_set = module.load_golden_set(write_golden_set(tmp_path))

    outputs = [
        {
            "customer_name": "Pat Lee",
            "tags": ["REPAIR_AC", "DURATION_ACUTE", "PEAK_SUMMER"],
            "revenue_tier": "standard_repair",
        },
        {
            "urgency_tier": "urgent",
            "route": "legitimate",
            "revenue_tier": "diagnostic",
        },
    ]

    report, exit_code = module.build_report(
        golden_set,
        extraction_runner=lambda transcript, raw_payload: outputs.pop(0),
    )

    assert exit_code == 0
    assert report["failures"] == []


def test_eval_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = load_module()
    golden_set_path = write_golden_set(tmp_path)
    outputs = [
        {"customer_name": "Wrong", "tags": [], "revenue_tier": "minor"},
        {"urgency_tier": "routine", "route": "vendor", "revenue_tier": "minor"},
    ]

    monkeypatch.setenv("VOICE_GOLDEN_SET_PATH", str(golden_set_path))
    monkeypatch.setattr(
        module,
        "_load_extraction_runner",
        lambda: (lambda transcript, raw_payload: outputs.pop(0)),
    )

    exit_code = module.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["accuracy"] == 0.0
    assert payload["fail"] == 2
