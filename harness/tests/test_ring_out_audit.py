from __future__ import annotations

import csv
from io import StringIO
from zoneinfo import ZoneInfo

from db.repository import list_scheduler_backlog, list_ring_out_attempts, list_ring_out_prospects
from harness.control_plane.kill_switches import upsert_kill_switch
from ring_out_audit.provider import FakeRingOutProvider, TwilioRingOutProvider
from ring_out_audit.service import (
    export_scored_csv,
    import_prospects_csv,
    claim_due_audit_attempts,
    process_twilio_status_callback,
)


def _csv_text(rows: list[dict[str, str]]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["prospect_id", "business_name", "phone", "timezone", "source_batch"])
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def test_import_rejects_more_than_one_thousand_prospects() -> None:
    rows = [
        {
            "prospect_id": f"hvac-{index}",
            "business_name": f"HVAC {index}",
            "phone": f"+1312555{index:04d}",
            "timezone": "America/Detroit",
            "source_batch": "batch-1001",
        }
        for index in range(1001)
    ]

    try:
        import_prospects_csv(_csv_text(rows), tenant_id="tenant-alpha", now_iso="2026-06-20T12:00:00+00:00")
    except ValueError as exc:
        assert "1000" in str(exc)
    else:
        raise AssertionError("Expected import over 1000 rows to fail")


def test_import_schedules_three_late_night_attempts_per_prospect() -> None:
    import_prospects_csv(
        _csv_text(
            [
                {
                    "prospect_id": "hvac-1",
                    "business_name": "Night Owl HVAC",
                    "phone": "+13125550101",
                    "timezone": "America/Detroit",
                    "source_batch": "batch-late",
                }
            ]
        ),
        tenant_id="tenant-alpha",
        now_iso="2026-06-20T12:00:00+00:00",
        random_seed=7,
    )

    prospects = list_ring_out_prospects(source_batch="batch-late")
    attempts = list_ring_out_attempts(prospect_id="hvac-1")
    backlog = list_scheduler_backlog(job_type="ring_out_audit_attempt")

    assert len(prospects) == 1
    assert len(attempts) == 3
    assert len(backlog) == 3
    assert [attempt["attempt_number"] for attempt in attempts] == [1, 2, 3]
    for attempt in attempts:
        local_time = attempt["scheduled_for_local"]
        assert local_time.endswith("-04:00")
        local_hour = int(local_time[11:13])
        local_minute = int(local_time[14:16])
        assert (local_hour, local_minute) >= (0, 15)
        assert (local_hour, local_minute) <= (4, 45)


def test_twilio_provider_uses_twenty_second_timeout_and_hangup_answer_url() -> None:
    class Calls:
        def __init__(self) -> None:
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs
            return type("Call", (), {"sid": "CA_real_sid", "status": "queued"})()

    class Client:
        def __init__(self) -> None:
            self.calls = Calls()

    client = Client()
    provider = TwilioRingOutProvider(
        account_sid="AC_test",
        auth_token="auth",
        from_number="+13125551234",
        status_callback_url="https://example.test/webhook/twilio/ring-out-status",
        answer_url="https://example.test/webhook/twilio/ring-out-answer",
        twilio_client=client,
    )

    result = provider.place_call(
        attempt={
            "attempt_id": "attempt-1",
            "prospect_id": "hvac-1",
            "phone": "+13125550101",
        }
    )

    assert result["call_sid"] == "CA_real_sid"
    assert client.calls.kwargs["timeout"] == 20
    assert client.calls.kwargs["machine_detection"] == "Enable"
    assert client.calls.kwargs["url"] == "https://example.test/webhook/twilio/ring-out-answer"
    assert client.calls.kwargs["status_callback"] == "https://example.test/webhook/twilio/ring-out-status"
    assert "completed" in client.calls.kwargs["status_callback_event"]


def test_decisive_ring_out_stops_future_attempts_and_exports_target() -> None:
    import_prospects_csv(
        _csv_text(
            [
                {
                    "prospect_id": "hvac-ring",
                    "business_name": "Ringout Heating",
                    "phone": "+13125550102",
                    "timezone": "America/Detroit",
                    "source_batch": "batch-ring",
                }
            ]
        ),
        tenant_id="tenant-alpha",
        now_iso="2026-06-20T12:00:00+00:00",
        random_seed=11,
    )
    provider = FakeRingOutProvider()

    claimed = claim_due_audit_attempts(
        utc_iso="2026-06-27T12:00:00+00:00",
        max_attempts=10,
        claimer_id="test-worker",
        provider=provider,
    )
    assert claimed["blocked"] is False
    assert len(claimed["dialed"]) == 1
    assert len(provider.calls) == 1

    callback = process_twilio_status_callback(
        {
            "CallSid": provider.calls[0]["call_sid"],
            "CallStatus": "no-answer",
            "CallDuration": "20",
        },
        now_iso="2026-06-27T12:00:25+00:00",
    )

    assert callback["outcome"] == "ring_out_confirmed"
    attempts = list_ring_out_attempts(prospect_id="hvac-ring")
    assert [attempt["status"] for attempt in attempts] == ["completed", "skipped", "skipped"]

    second_claim = claim_due_audit_attempts(
        utc_iso="2026-06-28T12:00:00+00:00",
        max_attempts=10,
        claimer_id="test-worker",
        provider=provider,
    )
    assert second_claim["dialed"] == []

    exported = export_scored_csv(source_batch="batch-ring")
    assert "ring_out_confirmed" in exported
    assert "highest" in exported
    assert "I called after hours and it rang until nobody picked up." in exported


def test_voicemail_is_target_signal_but_stops_additional_audit_calls() -> None:
    import_prospects_csv(
        _csv_text(
            [
                {
                    "prospect_id": "hvac-vm",
                    "business_name": "Voicemail Heating",
                    "phone": "+13125550103",
                    "timezone": "America/Detroit",
                    "source_batch": "batch-vm",
                }
            ]
        ),
        tenant_id="tenant-alpha",
        now_iso="2026-06-20T12:00:00+00:00",
        random_seed=12,
    )
    provider = FakeRingOutProvider()
    claim_due_audit_attempts(
        utc_iso="2026-06-27T12:00:00+00:00",
        max_attempts=10,
        claimer_id="test-worker",
        provider=provider,
    )

    callback = process_twilio_status_callback(
        {
            "CallSid": provider.calls[0]["call_sid"],
            "CallStatus": "completed",
            "AnsweredBy": "machine_start",
            "CallDuration": "8",
        },
        now_iso="2026-06-27T12:00:10+00:00",
    )

    assert callback["outcome"] == "after_hours_voicemail"
    prospect = list_ring_out_prospects(source_batch="batch-vm")[0]
    assert prospect["target_segment"] == "strong"
    assert prospect["priority_score"] == 80
    assert all(attempt["status"] in {"completed", "skipped"} for attempt in list_ring_out_attempts("hvac-vm"))


def test_worker_kill_switch_blocks_claim_and_dial() -> None:
    import_prospects_csv(
        _csv_text(
            [
                {
                    "prospect_id": "hvac-paused",
                    "business_name": "Paused HVAC",
                    "phone": "+13125550104",
                    "timezone": "America/Detroit",
                    "source_batch": "batch-paused",
                }
            ]
        ),
        tenant_id="tenant-alpha",
        now_iso="2026-06-20T12:00:00+00:00",
    )
    upsert_kill_switch({"scope": "worker", "scope_id": "ring_out_audit", "reason": "pause audit", "active": True})
    provider = FakeRingOutProvider()

    result = claim_due_audit_attempts(
        utc_iso="2026-06-27T12:00:00+00:00",
        max_attempts=10,
        claimer_id="test-worker",
        provider=provider,
    )

    assert result["blocked"] is True
    assert result["reason"] == "pause audit"
    assert provider.calls == []
