"""FastAPI router for Retell call-ended webhook (post-call pipeline).

Synchronous pipeline (<2s):
1. Verify HMAC
2. Extract tenant_id from custom_metadata
3. Generate call_id (uuid4), persist raw Retell payload to call_records
4. Run extraction pipeline (pure functions, no external calls)
5. Update call_records with extracted fields
6. Fire Inngest event calllock/call.ended
7. Return 200 to Retell
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from voice.auth import HMACVerificationError, verify_retell_hmac
from voice.extraction.pipeline import run_extraction
from voice.models import RetellCallEndedPayload

logger = logging.getLogger(__name__)

post_call_router = APIRouter(tags=["voice-post-call"])


def _fire_inngest_event(event_name: str, payload: dict[str, Any]) -> None:
    """Fire an Inngest event. Placeholder — real implementation connects to Inngest SDK."""
    logger.info("inngest.event.fired", extra={"event": event_name, "call_id": payload.get("call_id")})


def _parse_booking_id(tool_call_results: list[dict[str, Any]]) -> str | None:
    """Parse booking_id from Retell's tool_call_results (book_service result).

    Per spec finding #16: booking_id is parsed from tool_call_results, NOT transcript.
    """
    for result in tool_call_results:
        tool_name = result.get("tool_name") or result.get("name", "")
        if tool_name == "book_service":
            content = result.get("content") or result.get("result", {})
            if isinstance(content, dict):
                return content.get("booking_id") or content.get("bookingId") or content.get("uid")
            if isinstance(content, str):
                try:
                    import json
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        return parsed.get("booking_id") or parsed.get("bookingId") or parsed.get("uid")
                except Exception:
                    pass
    return None


@post_call_router.post("/call-ended")
async def handle_call_ended(request: Request) -> JSONResponse:
    """Handle Retell call-ended webhook."""

    # 1. Verify HMAC
    body = await request.body()
    signature = request.headers.get("x-retell-signature", "")
    timestamp = request.headers.get("x-retell-timestamp", "")
    try:
        verify_retell_hmac(body, signature, timestamp)
    except HMACVerificationError:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    # 2. Parse payload and extract tenant_id
    payload = RetellCallEndedPayload.model_validate_json(body)
    tenant_id = payload.custom_metadata.get("tenant_id", "")
    retell_call_id = payload.call_id

    if not tenant_id:
        logger.error("post_call.missing_tenant_id", extra={"retell_call_id": retell_call_id})
        return JSONResponse(status_code=400, content={"error": "Missing tenant_id in custom_metadata"})

    # 3. Generate call_id (use retell_call_id for dedup) and persist raw payload
    call_id = retell_call_id
    raw_payload = payload.model_dump(by_alias=True)

    from db import repository as db_repo

    try:
        record = db_repo.insert_call_record(
            tenant_id=tenant_id,
            call_id=call_id,
            retell_call_id=retell_call_id,
            raw_payload=raw_payload,
        )
    except Exception:
        logger.error("post_call.persist_failed", extra={"call_id": call_id}, exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Failed to persist call record"})

    if record is None:
        logger.info("post_call.duplicate", extra={"retell_call_id": retell_call_id})
        return JSONResponse(content={"status": "duplicate", "retell_call_id": retell_call_id})

    # 4. Run extraction pipeline
    extraction = run_extraction(payload.transcript, raw_payload)

    # 5. Update call_records with extracted fields
    try:
        db_repo.update_call_record_extraction(
            tenant_id=tenant_id,
            call_id=call_id,
            extracted_fields=extraction,
        )
    except Exception:
        logger.error("post_call.update_extraction_failed", extra={"call_id": call_id}, exc_info=True)

    # Parse booking_id from tool_call_results
    booking_id = _parse_booking_id(payload.tool_call_results)

    # Determine callback_scheduled
    callback_scheduled = extraction.get("end_call_reason") == "callback_scheduled"

    # 6. Fire Inngest event
    duration_ms = payload.duration_ms or 0
    event_payload = {
        "tenant_id": tenant_id,
        "call_id": call_id,
        "call_source": "retell",
        "phone_number": payload.from_number or "",
        "transcript": payload.transcript,
        "customer_name": extraction.get("customer_name"),
        "service_address": extraction.get("service_address"),
        "problem_description": extraction.get("problem_description"),
        "urgency_tier": extraction.get("urgency_tier", "routine"),
        "caller_type": extraction.get("caller_type", "unknown"),
        "primary_intent": extraction.get("primary_intent", "unknown"),
        "revenue_tier": extraction.get("revenue_tier", "diagnostic"),
        "tags": extraction.get("tags", []),
        "quality_score": extraction.get("quality_score", 0),
        "scorecard_warnings": extraction.get("scorecard_warnings", []),
        "route": extraction.get("route", "legitimate"),
        "booking_id": booking_id,
        "callback_scheduled": callback_scheduled,
        "extraction_status": extraction.get("extraction_status", "complete"),
        "retell_call_id": retell_call_id,
        "call_duration_seconds": duration_ms // 1000,
        "end_call_reason": extraction.get("end_call_reason", "agent_hangup"),
        "call_recording_url": payload.recording_url,
    }

    try:
        _fire_inngest_event("calllock/call.ended", event_payload)
    except Exception:
        logger.error("post_call.inngest_failed", extra={"call_id": call_id}, exc_info=True)

    # 7. Return 200 to Retell
    return JSONResponse(content={
        "status": "ok",
        "call_id": call_id,
        "extraction_status": extraction.get("extraction_status", "complete"),
    })


__all__ = ["post_call_router"]
