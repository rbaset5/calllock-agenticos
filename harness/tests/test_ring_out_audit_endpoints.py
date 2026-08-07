from __future__ import annotations

import csv
from io import StringIO

from fastapi.testclient import TestClient

from harness.server import app


def _csv_text() -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["prospect_id", "business_name", "phone", "timezone", "source_batch"])
    writer.writeheader()
    writer.writerow(
        {
            "prospect_id": "hvac-api",
            "business_name": "API Heating",
            "phone": "+13125550105",
            "timezone": "America/Detroit",
            "source_batch": "batch-api",
        }
    )
    return buffer.getvalue()


def test_ring_out_audit_end_to_end_api_flow() -> None:
    client = TestClient(app)

    imported = client.post(
        "/ring-out-audits/import",
        json={
            "tenant_id": "tenant-alpha",
            "csv_text": _csv_text(),
            "now_iso": "2026-06-20T12:00:00+00:00",
            "random_seed": 31,
        },
    )
    assert imported.status_code == 200
    assert imported.json()["prospects_imported"] == 1
    assert imported.json()["attempts_scheduled"] == 3

    claimed = client.post(
        "/ring-out-audits/claim-due",
        json={
            "utc_iso": "2026-06-27T12:00:00+00:00",
            "max_attempts": 10,
            "claimer_id": "api-test",
            "provider": "fake",
        },
    )
    assert claimed.status_code == 200
    call_sid = claimed.json()["dialed"][0]["call_sid"]

    callback = client.post(
        "/webhook/twilio/ring-out-status",
        data={"CallSid": call_sid, "CallStatus": "no-answer", "CallDuration": "20"},
    )
    assert callback.status_code == 200
    assert callback.json()["outcome"] == "ring_out_confirmed"

    answer = client.post("/webhook/twilio/ring-out-answer")
    assert answer.status_code == 200
    assert "<Hangup/>" in answer.text

    exported = client.post("/ring-out-audits/export", json={"source_batch": "batch-api"})
    assert exported.status_code == 200
    assert "ring_out_confirmed" in exported.json()["csv_text"]


def test_ring_out_answer_webhook_records_amd_voicemail_before_hangup() -> None:
    client = TestClient(app)

    imported = client.post(
        "/ring-out-audits/import",
        json={
            "tenant_id": "tenant-alpha",
            "csv_text": _csv_text(),
            "now_iso": "2026-06-20T12:00:00+00:00",
            "random_seed": 41,
        },
    )
    assert imported.status_code == 200

    claimed = client.post(
        "/ring-out-audits/claim-due",
        json={
            "utc_iso": "2026-06-27T12:00:00+00:00",
            "max_attempts": 10,
            "claimer_id": "api-test",
            "provider": "fake",
        },
    )
    assert claimed.status_code == 200
    call_sid = claimed.json()["dialed"][0]["call_sid"]

    answer = client.post(
        "/webhook/twilio/ring-out-answer",
        data={"CallSid": call_sid, "CallStatus": "in-progress", "AnsweredBy": "machine_start", "CallDuration": "5"},
    )
    assert answer.status_code == 200
    assert "<Hangup/>" in answer.text

    completed = client.post(
        "/webhook/twilio/ring-out-status",
        data={"CallSid": call_sid, "CallStatus": "completed", "CallDuration": "5"},
    )
    assert completed.status_code == 200
    assert completed.json()["outcome"] == "after_hours_voicemail"
    assert completed.json()["target_segment"] == "strong"
    assert completed.json()["priority_score"] == 80

    exported = client.post("/ring-out-audits/export", json={"source_batch": "batch-api"})
    assert exported.status_code == 200
    assert "after_hours_voicemail" in exported.json()["csv_text"]
