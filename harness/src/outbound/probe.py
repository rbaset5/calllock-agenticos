from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any
from zoneinfo import ZoneInfo

from twilio.rest import Client

from . import store
from .constants import OUTBOUND_TENANT_ID, PROBE_ELIGIBLE_TIERS


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_probe_window(timezone_name: str, now: datetime | None = None) -> bool:
    runtime = now or _utc_now()
    local = runtime.astimezone(ZoneInfo(timezone_name))
    return 19 <= local.hour < 21


def map_amd_result(answered_by: str | None, call_status: str | None) -> str:
    status = (call_status or "").lower()
    amd = (answered_by or "").lower()
    if amd == "human":
        return "answered_human"
    if amd in {"machine_start", "machine_end_beep", "machine_end_silence", "fax"}:
        return "voicemail"
    if status in {"busy"}:
        return "busy"
    if status in {"failed", "canceled", "cancelled"}:
        return "failed"
    if status in {"no-answer", "no_answer", "queued", "ringing"}:
        return "no_answer"
    return "uncertain"


def _twilio_client() -> Client:
    return Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])


def place_probe_call(prospect: dict[str, Any], client: Client | None = None) -> dict[str, Any]:
    twilio_client = client or _twilio_client()
    call = twilio_client.calls.create(
        to=prospect["phone_normalized"],
        from_=os.environ["TWILIO_PROBE_PHONE_NUMBER"],
        machine_detection="Enable",
        async_amd="false",
        twiml="<Response><Hangup/></Response>",
    )
    call_sid = getattr(call, "sid", "")
    answered_by = getattr(call, "answered_by", None)
    status = getattr(call, "status", None)
    duration = getattr(call, "duration", None)
    return {
        "twilio_call_sid": call_sid,
        "amd_status": answered_by,
        "status": status,
        "ring_duration_ms": int(duration) * 1000 if duration not in (None, "") else None,
        "result": map_amd_result(answered_by, status),
    }


def run_probe_batch(max_probes: int = 50, *, now: datetime | None = None) -> dict[str, int]:
    runtime = now or _utc_now()
    prospects = [
        prospect
        for prospect in store.list_probe_candidates(tenant_id=OUTBOUND_TENANT_ID)
        if prospect.get("timezone") and prospect.get("score_tier") in PROBE_ELIGIBLE_TIERS
        and is_probe_window(str(prospect["timezone"]), runtime)
    ][:max_probes]

    summary = {"tested": 0, "confirmed_weak": 0, "answered": 0, "uncertain": 0, "failed": 0}
    for prospect in prospects:
        local_now = runtime.astimezone(ZoneInfo(str(prospect["timezone"])))
        try:
            result = place_probe_call(prospect)
        except Exception:
            result = {
                "twilio_call_sid": f"failed-{prospect['id']}",
                "amd_status": None,
                "status": "failed",
                "ring_duration_ms": None,
                "result": "failed",
            }

        store.insert_call_test(
            {
                "tenant_id": OUTBOUND_TENANT_ID,
                "prospect_id": prospect["id"],
                "twilio_call_sid": result["twilio_call_sid"],
                "called_at": runtime.isoformat(),
                "day_of_week": local_now.strftime("%A"),
                "local_time": local_now.strftime("%H:%M"),
                "result": result["result"],
                "amd_status": result["amd_status"],
                "ring_duration_ms": result["ring_duration_ms"],
            }
        )

        summary["tested"] += 1
        if result["result"] in {"no_answer", "voicemail"}:
            store.update_outbound_prospect(prospect["id"], {"stage": "tested"})
            store.update_outbound_prospect(prospect["id"], {"stage": "call_ready"})
            summary["confirmed_weak"] += 1
        elif result["result"] == "answered_human":
            summary["answered"] += 1
        elif result["result"] == "failed":
            summary["failed"] += 1
        else:
            summary["uncertain"] += 1

    return summary
