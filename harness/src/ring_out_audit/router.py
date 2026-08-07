from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from ring_out_audit.provider import FakeRingOutProvider, TwilioRingOutProvider
from ring_out_audit.service import (
    claim_due_audit_attempts,
    export_scored_csv,
    import_prospects_csv,
    process_twilio_status_callback,
)


router = APIRouter()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImportRequest(StrictModel):
    tenant_id: str
    csv_text: str
    now_iso: str | None = None
    random_seed: int | None = None


class ClaimDueRequest(StrictModel):
    utc_iso: str | None = None
    max_attempts: int = Field(default=25, ge=1, le=100)
    claimer_id: str = "ring-out-worker"
    provider: str | None = None


class ExportRequest(StrictModel):
    source_batch: str | None = None
    tenant_id: str | None = None


def _provider_from_request(provider_name: str | None):
    if provider_name is None:
        return None
    normalized = provider_name.strip().lower()
    if normalized == "fake":
        return FakeRingOutProvider()
    if normalized == "twilio":
        return TwilioRingOutProvider.from_env()
    raise HTTPException(status_code=400, detail=f"Unsupported ring-out provider: {provider_name}")


async def _twilio_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        payload = await request.json()
        return dict(payload)
    body = (await request.body()).decode()
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


@router.post("/ring-out-audits/import")
def import_ring_out_audits(request: ImportRequest) -> dict[str, Any]:
    try:
        return import_prospects_csv(
            request.csv_text,
            tenant_id=request.tenant_id,
            now_iso=request.now_iso,
            random_seed=request.random_seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ring-out-audits/claim-due")
def claim_due_ring_out_audits(request: ClaimDueRequest) -> dict[str, Any]:
    provider = _provider_from_request(request.provider)
    return claim_due_audit_attempts(
        utc_iso=request.utc_iso,
        max_attempts=request.max_attempts,
        claimer_id=request.claimer_id,
        provider=provider,
    )


@router.post("/webhook/twilio/ring-out-status")
async def twilio_ring_out_status(request: Request) -> dict[str, Any]:
    payload = await _twilio_payload(request)
    try:
        return process_twilio_status_callback(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/webhook/twilio/ring-out-answer")
async def twilio_ring_out_answer(request: Request) -> Response:
    payload = await _twilio_payload(request)
    if payload.get("CallSid") and payload.get("AnsweredBy"):
        try:
            process_twilio_status_callback(payload)
        except (KeyError, ValueError):
            pass
    return Response(content="<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Hangup/></Response>", media_type="text/xml")


@router.post("/ring-out-audits/export")
def export_ring_out_audits(request: ExportRequest) -> dict[str, str]:
    return {"csv_text": export_scored_csv(source_batch=request.source_batch, tenant_id=request.tenant_id)}
