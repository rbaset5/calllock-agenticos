from pathlib import Path

from observability.langsmith_tracer import prepare_trace_payload, submit_trace
from observability.pii_redactor import hash_identifier, redact_pii_recursive


def test_recursive_pii_redaction_redacts_nested_values() -> None:
    redacted = redact_pii_recursive(
        {
            "tenant_id": "tenant-alpha",
            "transcript": "Call me at 313-555-1212 and email ops@example.com at 123 Main St",
            "nested": [{"call_id": "call-1", "note": "zip 48103"}],
        }
    )
    assert redacted["tenant_id"].startswith("sha256:")
    assert "[REDACTED_PHONE]" in redacted["transcript"]
    assert "[REDACTED_EMAIL]" in redacted["transcript"]
    assert "[REDACTED_ADDRESS]" in redacted["transcript"]
    assert redacted["nested"][0]["call_id"].startswith("sha256:")


def test_prepare_trace_payload_marks_redacted_classification() -> None:
    payload = prepare_trace_payload({"tenant_id": "tenant-alpha", "inputs": {"transcript": "Call 313-555-1212"}})
    assert payload["data_classification"] == "pii-redacted"
    assert payload["tenant_id"].startswith("sha256:")


def test_submit_trace_falls_back_to_local_file(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.setenv("CALLLOCK_TRACE_ROOT", str(tmp_path))
    trace = submit_trace(
        name="process-call",
        payload={
            "tenant_id": "tenant-alpha",
            "inputs": {"transcript": "Call me at 313-555-1212"},
            "outputs": {"status": "ok"},
        },
    )
    assert trace["backend"] == "local"
    target = Path(trace["path"])
    assert target.exists()
    assert target.parent.name == "tenant-alpha"
    contents = target.read_text()
    assert "[REDACTED_PHONE]" in contents
