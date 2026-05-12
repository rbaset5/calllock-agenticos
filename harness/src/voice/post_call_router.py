"""FastAPI router for Retell call-ended webhook (post-call pipeline).

Synchronous path:
1. Verify HMAC
2. Parse payload and extract tenant_id
3. Persist the raw Retell payload to call_records
4. Queue background extraction + supervisor processing
5. Return 200 to Retell immediately
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from voice.auth import HMACVerificationError, verify_retell_hmac
from voice.extraction.pipeline import run_extraction
from voice.models import RetellCallEndedPayload

logger = logging.getLogger(__name__)

post_call_router = APIRouter(tags=["voice-post-call"])
_PHONE_TO_TENANT = {
    "+13126463816": "e51d9ae7-9cde-4dca-a49c-4744c39240bc",
    "+13126463826": "e51d9ae7-9cde-4dca-a49c-4744c39240bc",
}

VOICE_WORKER_SPEC_PATH = Path(__file__).resolve().parents[3] / "knowledge" / "worker-specs" / "eng-ai-voice.yaml"
VOICE_WORKER_SPEC_FALLBACK = {
    "id": "eng-ai-voice",
    "title": "Voice Pipeline Worker",
    "department": "engineering",
    "role": "worker",
    "tools_allowed": [],
}


def _validate_voice_worker_spec() -> None:
    try:
        with open(VOICE_WORKER_SPEC_PATH, encoding="utf-8") as handle:
            spec = yaml.safe_load(handle)
        if not isinstance(spec, dict):
            raise ValueError("voice worker spec must deserialize to a mapping")
    except FileNotFoundError:
        logger.warning(
            "voice.worker_spec_missing",
            extra={"path": str(VOICE_WORKER_SPEC_PATH)},
        )
    except yaml.YAMLError:
        logger.warning(
            "voice.worker_spec_invalid_yaml",
            extra={"path": str(VOICE_WORKER_SPEC_PATH)},
            exc_info=True,
        )
    except Exception:
        logger.warning(
            "voice.worker_spec_validation_failed",
            extra={"path": str(VOICE_WORKER_SPEC_PATH)},
            exc_info=True,
        )


def _load_voice_worker_spec() -> dict[str, Any]:
    """Load the eng-ai-voice worker spec from knowledge/worker-specs/."""
    try:
        with open(VOICE_WORKER_SPEC_PATH, encoding="utf-8") as handle:
            spec = yaml.safe_load(handle)
        if not isinstance(spec, dict):
            raise ValueError("voice worker spec must deserialize to a mapping")
        return spec
    except FileNotFoundError:
        logger.warning(
            "voice.worker_spec_missing",
            extra={"path": str(VOICE_WORKER_SPEC_PATH)},
        )
    except yaml.YAMLError:
        logger.warning(
            "voice.worker_spec_invalid_yaml",
            extra={"path": str(VOICE_WORKER_SPEC_PATH)},
            exc_info=True,
        )
    except Exception:
        logger.warning(
            "voice.worker_spec_fallback",
            extra={"path": str(VOICE_WORKER_SPEC_PATH)},
            exc_info=True,
        )
    return dict(VOICE_WORKER_SPEC_FALLBACK)


_validate_voice_worker_spec()


def _run_voice_supervisor(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the supervisor directly instead of going through Inngest."""
    from harness.graphs.supervisor import run_supervisor

    logger.info(
        "supervisor.direct_invoke",
        extra={"call_id": payload.get("call_id")},
    )

    state = {
        "tenant_id": payload["tenant_id"],
        "run_id": payload.get("call_id", ""),
        "worker_id": "eng-ai-voice",
        "task": {
            "worker_spec": _load_voice_worker_spec(),
            "tenant_config": {},
            "problem_description": payload.get("problem_description", ""),
            "transcript": payload.get("transcript", ""),
            "task_context": {"call_payload": payload},
            "call_payload": payload,
            "feature_flags": {"llm_workers_enabled": False},
        },
    }
    result = run_supervisor(state)
    guardian_gate = result.get("guardian_gate", {})
    gate_result = "quarantined" if guardian_gate.get("quarantine") else "passed"
    logger.info(
        "supervisor.direct_invoke_success",
        extra={
            "call_id": payload.get("call_id"),
            "guardian_gate_result": gate_result,
        },
    )
    return result


def _parse_booking_id(tool_call_results: list[dict[str, Any]]) -> str | None:
    """Parse booking_id from Retell's tool_call_results (book_service result)."""
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


def _build_supervisor_payload(
    *,
    raw_payload: dict[str, Any],
    tenant_id: str,
    call_id: str,
    extraction: dict[str, Any],
    booking_id: str | None,
    callback_scheduled: bool,
    duration_seconds: int,
) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "call_id": call_id,
        "call_source": "retell",
        "phone_number": raw_payload.get("from_number") or "",
        "transcript": raw_payload.get("transcript", ""),
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
        "retell_call_id": raw_payload.get("call_id"),
        "call_duration_seconds": duration_seconds,
        "end_call_reason": extraction.get("end_call_reason") or "agent_hangup",
        "call_recording_url": raw_payload.get("recording_url"),
    }


def _merge_quarantine_fields(
    extracted_fields: dict[str, Any],
    gate_failures: list[str],
) -> dict[str, Any]:
    merged = dict(extracted_fields)
    merged.update(
        {
            "quarantine": True,
            "gate_failures": gate_failures,
            "extraction_status": "quarantined",
        }
    )
    return merged


async def _process_call_ended(raw_payload: dict[str, Any]) -> None:
    from db import repository as db_repo

    call_id = str(raw_payload.get("call_id") or "")
    tenant_id = str((raw_payload.get("custom_metadata") or {}).get("tenant_id") or "")
    extraction: dict[str, Any] = {}

    try:
        extraction = run_extraction(raw_payload.get("transcript"), raw_payload)
    except Exception:
        logger.error(
            "post_call.extraction_failed",
            extra={"call_id": call_id},
            exc_info=True,
        )
        extraction = {"extraction_status": "partial"}

    booking_id = _parse_booking_id(raw_payload.get("tool_call_results") or [])
    callback_scheduled = extraction.get("end_call_reason") == "callback_scheduled"
    duration_seconds = int(raw_payload.get("duration_ms") or 0) // 1000
    end_call_reason = extraction.get("end_call_reason") or "agent_hangup"
    final_extraction = dict(extraction)

    supervisor_payload = _build_supervisor_payload(
        raw_payload=raw_payload,
        tenant_id=tenant_id,
        call_id=call_id,
        extraction=extraction,
        booking_id=booking_id,
        callback_scheduled=callback_scheduled,
        duration_seconds=duration_seconds,
    )

    try:
        supervisor_result = _run_voice_supervisor(supervisor_payload)
        guardian_gate = supervisor_result.get("guardian_gate", {})
        if guardian_gate.get("quarantine"):
            final_extraction = _merge_quarantine_fields(
                extraction,
                list(guardian_gate.get("gate_failures", [])),
            )
        else:
            final_extraction["extraction_status"] = extraction.get(
                "extraction_status",
                "complete",
            )
    except Exception:
        logger.error(
            "supervisor.direct_invoke_failed",
            extra={"call_id": call_id},
            exc_info=True,
        )
        final_extraction = _merge_quarantine_fields(extraction, ["supervisor_failed"])

    try:
        db_repo.update_call_record_extraction(
            tenant_id=tenant_id,
            call_id=call_id,
            extracted_fields=final_extraction,
            end_call_reason=end_call_reason,
            booking_id=booking_id,
            callback_scheduled=callback_scheduled,
            call_duration_seconds=duration_seconds,
            call_recording_url=raw_payload.get("recording_url"),
        )
    except Exception:
        logger.error(
            "post_call.update_extraction_failed",
            extra={"call_id": call_id},
            exc_info=True,
        )


@post_call_router.post("/call-ended")
async def handle_call_ended(
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """Handle Retell call-ended webhook."""

    body = await request.body()
    signature = request.headers.get("x-retell-signature", "")
    timestamp = request.headers.get("x-retell-timestamp", "")
    try:
        verify_retell_hmac(body, signature, timestamp)
    except (HMACVerificationError, RuntimeError) as exc:
        logger.warning("post_call.hmac.failed", extra={"error": str(exc)})
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    try:
        raw = json.loads(body)
    except (TypeError, ValueError, json.JSONDecodeError):
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid payload", "details": "Malformed JSON"},
        )

    try:
        payload = RetellCallEndedPayload.model_validate(raw)
    except ValidationError as exc:
        raw_summary = raw if isinstance(raw, dict) else {"payload_type": type(raw).__name__}
        logger.error(
            "post_call.validation_error",
            extra={
                "raw_payload_summary": {
                    "event": raw_summary.get("event"),
                    "has_call": isinstance(raw_summary.get("call"), dict),
                    "call_id": (
                        raw_summary.get("call_id")
                        or (
                            raw_summary.get("call", {}).get("call_id")
                            if isinstance(raw_summary.get("call"), dict)
                            else None
                        )
                    ),
                    "to_number": (
                        raw_summary.get("to_number")
                        or (
                            raw_summary.get("call", {}).get("to_number")
                            if isinstance(raw_summary.get("call"), dict)
                            else None
                        )
                    ),
                },
                "errors": exc.errors(include_input=False),
            },
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "skipped",
                "reason": "invalid_payload",
            },
        )

    if payload.event and payload.event != "call_ended":
        return JSONResponse(
            status_code=400,
            content={"error": f"Unexpected event type: {payload.event}"},
        )

    tenant_id = payload.custom_metadata.get("tenant_id", "")
    retell_call_id = payload.call_id

    if not tenant_id:
        tenant_id = _PHONE_TO_TENANT.get(payload.to_number or "", "")
        if tenant_id:
            logger.warning(
                "post_call.tenant_fallback",
                extra={
                    "call_id": retell_call_id,
                    "to_number": payload.to_number,
                    "tenant_id": tenant_id,
                },
            )

    if not tenant_id:
        logger.error(
            "post_call.tenant_missing",
            extra={"call_id": retell_call_id, "to_number": payload.to_number},
        )
        return JSONResponse(
            status_code=200,
            content={"status": "skipped", "reason": "no_tenant_id"},
        )

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
        logger.error(
            "post_call.persist_failed",
            extra={"call_id": call_id},
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to persist call record"},
        )

    if record is None:
        logger.info("post_call.duplicate", extra={"retell_call_id": retell_call_id})
        return JSONResponse(
            content={"status": "duplicate", "retell_call_id": retell_call_id}
        )

    background_tasks.add_task(_process_call_ended, raw_payload)

    return JSONResponse(
        content={
            "status": "ok",
            "call_id": call_id,
            "extraction_status": "pending",
        }
    )


__all__ = ["post_call_router"]
