"""FastAPI router for booking management REST API (CallLock App-facing).

Three endpoints with API key auth:
  GET  /lookup?phone={phone}
  POST /cancel
  POST /reschedule

Auth: X-API-Key header, timing-safe SHA-256 hash comparison against voice_api_keys table.
Cal.com errors propagate as 503 to caller.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from voice.auth import InvalidAPIKeyError, verify_api_key
from voice.config import VoiceConfigError, resolve_calcom_config
from voice.models import CalcomConfig
from voice.services.calcom import CalcomError, cancel_booking, lookup_by_phone, reschedule_booking

logger = logging.getLogger(__name__)

booking_router = APIRouter(tags=["voice-bookings"])


class CancelRequest(BaseModel):
    booking_uid: str
    reason: str


class RescheduleRequest(BaseModel):
    booking_uid: str
    new_time: str


def _get_api_keys() -> list[dict[str, Any]]:
    """Fetch all non-revoked API keys from the repository."""
    from db import repository as db_repo
    return db_repo.get_voice_api_keys()


def _authenticate(request: Request) -> str:
    """Authenticate via X-API-Key header. Returns tenant_id."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise InvalidAPIKeyError("Missing X-API-Key header")
    stored = _get_api_keys()
    return verify_api_key(api_key, stored)


def _resolve_calcom(tenant_id: str) -> CalcomConfig:
    """Resolve CalcomConfig for a tenant."""
    return resolve_calcom_config(tenant_id)


@booking_router.get("/lookup")
async def booking_lookup(
    request: Request,
    phone: str = Query(..., description="E.164 phone number"),
) -> JSONResponse:
    """Look up upcoming bookings by phone number."""
    try:
        tenant_id = _authenticate(request)
    except InvalidAPIKeyError:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    try:
        config = _resolve_calcom(tenant_id)
    except (VoiceConfigError, NotImplementedError):
        return JSONResponse(status_code=503, content={"error": "Cal.com not configured for tenant"})

    try:
        bookings = await lookup_by_phone(phone, config)
    except CalcomError as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})

    return JSONResponse(content={"bookings": bookings, "phone": phone})


@booking_router.post("/cancel")
async def booking_cancel(request: Request, body: CancelRequest) -> JSONResponse:
    """Cancel a booking by UID."""
    try:
        tenant_id = _authenticate(request)
    except InvalidAPIKeyError:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    try:
        config = _resolve_calcom(tenant_id)
    except (VoiceConfigError, NotImplementedError):
        return JSONResponse(status_code=503, content={"error": "Cal.com not configured for tenant"})

    try:
        await cancel_booking(body.booking_uid, body.reason, config)
    except CalcomError as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})

    return JSONResponse(content={"success": True, "booking_uid": body.booking_uid})


@booking_router.post("/reschedule")
async def booking_reschedule(request: Request, body: RescheduleRequest) -> JSONResponse:
    """Reschedule a booking to a new time."""
    try:
        tenant_id = _authenticate(request)
    except InvalidAPIKeyError:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    try:
        config = _resolve_calcom(tenant_id)
    except (VoiceConfigError, NotImplementedError):
        return JSONResponse(status_code=503, content={"error": "Cal.com not configured for tenant"})

    try:
        await reschedule_booking(body.booking_uid, body.new_time, config)
    except CalcomError as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})

    return JSONResponse(content={"success": True, "booking_uid": body.booking_uid})


__all__ = ["booking_router"]
