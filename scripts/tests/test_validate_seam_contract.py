from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate-seam-contract.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_seam_contract", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_contract(tmp_path: Path) -> Path:
    contract_path = tmp_path / "seam-contract.yaml"
    contract_path.write_text(
        """
fields:
  customer_name:
    extraction: required
    app_display: shown
    supabase: stored
  caller_type:
    extraction: required
    app_display: shown
    supabase: stored
    enum:
      - customer
      - spam
      - vendor
  internal_note:
    extraction: optional
    app_display: not_shown
    supabase: not_stored
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return contract_path


def make_transport(rows: list[dict[str, object]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/rest/v1/call_records")
        assert request.headers["apikey"] == "service-role-key"
        assert request.headers["authorization"] == "Bearer service-role-key"
        assert request.url.params["select"] == "*"
        assert request.url.params["order"] == "created_at.desc"
        assert request.url.params["limit"] == "10"
        return httpx.Response(200, json=rows)

    return httpx.MockTransport(handler)


def test_build_report_flags_failures_and_warnings(tmp_path: Path) -> None:
    module = load_module()
    contract_path = write_contract(tmp_path)

    rows = []
    for index in range(10):
        extracted_fields: dict[str, object] = {"caller_type": "customer"}
        if index < 9:
            extracted_fields["customer_name"] = f"Customer {index}"
        if index == 2:
            extracted_fields["caller_type"] = "other"
        rows.append({"call_id": f"call-{index}", "extracted_fields": extracted_fields})

    report = module.build_report(
        contract_path=contract_path,
        supabase_url="https://example.supabase.co",
        supabase_key="service-role-key",
        transport=make_transport(rows),
    )

    checks = {(check["field"], check["check"]): check for check in report["checks"]}

    assert checks[("customer_name", "extraction_completeness")]["status"] == "fail"
    assert checks[("customer_name", "extraction_completeness")]["detail"] == "9/10"
    assert checks[("caller_type", "enum_coverage")]["status"] == "fail"
    assert checks[("caller_type", "enum_coverage")]["detail"] == "unknown value: 'other'"
    assert checks[("internal_note", "orphan_detection")]["status"] == "warn"
    assert report["summary"] == {"pass": 3, "fail": 2, "warn": 1}
    assert report["calls_sampled"] == 10


def test_main_prints_json_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = load_module()
    contract_path = write_contract(tmp_path)

    rows = [{"call_id": "call-1", "extracted_fields": {"customer_name": "Pat", "caller_type": "customer"}} for _ in range(10)]

    monkeypatch.setenv("SEAM_CONTRACT_PATH", str(contract_path))
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setattr(
        module,
        "fetch_recent_calls",
        lambda supabase_url, supabase_key, *, limit=10, transport=None: rows,
    )

    exit_code = module.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["summary"] == {"pass": 5, "fail": 0, "warn": 1}
    assert payload["checks"][0]["field"] == "customer_name"


def test_load_contract_requires_fields(tmp_path: Path) -> None:
    module = load_module()
    contract_path = tmp_path / "empty.yaml"
    contract_path.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit, match="No fields found"):
        module.load_contract(contract_path)
