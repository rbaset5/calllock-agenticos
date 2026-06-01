"""FastAPI router for Retell tool call webhooks.

Each tool has a dedicated endpoint (per-tool URLs, not a dispatcher).
Auth: Retell HMAC-SHA256 verification via dependency.
Retell v10 sends each tool call to its own URL.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from voice.auth import HMACVerificationError, verify_retell_hmac
from voice.config import VoiceConfigError, resolve_calcom_config, resolve_voice_config
from voice.fallback_router import FallbackContext, FallbackPolicy, route_call_fallback
from voice.models import RetellToolCallRequest
from voice.tools.book_service import book_service
from voice.tools.create_callback import create_callback
from voice.tools.lookup_caller import lookup_caller
from voice.tools.sales_lead_alert import send_sales_lead_alert

logger = logging.getLogger(__name__)

_GRACEFUL_ERROR = "We're experiencing technical difficulties. Please call back or leave a message."

voice_router = APIRouter(tags=["voice"])


@voice_router.post("/inbound")
async def handle_inbound_webhook(request: Request) -> JSONResponse:
    """Retell inbound webhook — called when a new call arrives, before the agent picks up.

    Returns metadata (including tenant_id) that Retell attaches to the call.
    All subsequent tool calls and the post-call webhook will include this metadata.
    This is how multi-tenant routing works with Retell.
    """
    try:
        body = await request.body()
        signature = request.headers.get("x-retell-signature", "")
        timestamp = request.headers.get("x-retell-timestamp", "")
        verify_retell_hmac(body, signature, timestamp)
    except HMACVerificationError:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    import json
    payload = json.loads(body) if body else {}
    agent_id = payload.get("agent_id", "")
    to_number = payload.get("to_number", "")

    # Resolve tenant_id from the phone number → tenant mapping
    tenant_id = _resolve_tenant_from_call(agent_id, to_number)

    logger.info("voice.inbound", extra={
        "agent_id": agent_id,
        "to_number": to_number,
        "tenant_id": tenant_id or "unknown",
    })

    if not tenant_id:
        # Still accept the call — tools will degrade gracefully without tenant_id
        return JSONResponse(content={})

    return JSONResponse(content={
        "metadata": {"tenant_id": tenant_id},
    })


def _resolve_tenant_from_call(agent_id: str, to_number: str) -> str | None:
    """Map a Retell agent_id or phone number to a tenant_id.

    Uses a simple DB lookup: phone numbers and agent IDs are registered
    per-tenant during onboarding. Falls back to None if no match.
    """
    # For now: hardcoded mapping until we have a proper agent_id → tenant table.
    # This is the single phone number registered in Retell.
    _PHONE_TO_TENANT = {
        "+13126463816": "e51d9ae7-9cde-4dca-a49c-4744c39240bc",
    }
    return _PHONE_TO_TENANT.get(to_number)


async def require_retell_hmac(request: Request) -> None:
    """FastAPI dependency that verifies Retell HMAC-SHA256 signatures."""
    body = await request.body()
    signature = request.headers.get("x-retell-signature", "")
    timestamp = request.headers.get("x-retell-timestamp", "")
    try:
        verify_retell_hmac(body, signature, timestamp)
    except HMACVerificationError as exc:
        logger.warning("voice.hmac.failed", extra={"error": str(exc)})
        raise HMACVerificationError(str(exc)) from exc


def _extract_tenant_id(payload: RetellToolCallRequest) -> str | None:
    """Extract tenant_id from Retell metadata."""
    return payload.metadata.get("tenant_id")


def _resolve_config(tenant_id: str | None) -> Any:
    """Resolve VoiceConfig, returning None on failure."""
    if not tenant_id:
        return None
    try:
        return resolve_voice_config(tenant_id)
    except (VoiceConfigError, NotImplementedError):
        logger.error("voice.config.resolve_failed", extra={"tenant_id": tenant_id})
        return None


def _resolve_calcom_config(tenant_id: str | None) -> Any:
    """Resolve CalcomConfig, returning None on failure."""
    if not tenant_id:
        return None
    try:
        return resolve_calcom_config(tenant_id)
    except (VoiceConfigError, NotImplementedError):
        logger.error("voice.calcom_config.resolve_failed", extra={"tenant_id": tenant_id})
        return None


def _as_bool(value: Any, default: bool = False) -> bool:
    """Parse Retell JSON args that may arrive as booleans or strings."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    return bool(value)


@voice_router.post("/lookup_caller")
async def handle_lookup_caller(request: Request) -> JSONResponse:
    """Handle lookup_caller tool call from Retell."""
    try:
        body = await request.body()
        signature = request.headers.get("x-retell-signature", "")
        timestamp = request.headers.get("x-retell-timestamp", "")
        verify_retell_hmac(body, signature, timestamp)
    except HMACVerificationError:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    payload = RetellToolCallRequest.model_validate_json(body)
    tenant_id = _extract_tenant_id(payload)
    phone = payload.args.get("phone_number", payload.args.get("phone", ""))

    if not phone:
        return JSONResponse(content={"found": False, "message": "No caller ID available."})

    if not tenant_id:
        logger.error("voice.lookup_caller.no_tenant_id")
        return JSONResponse(content={"found": False, "message": "Configuration error."})

    from db import repository as _db_repo
    result = lookup_caller(phone_number=phone, tenant_id=tenant_id, db=_db_repo)
    return JSONResponse(content=result)


@voice_router.post("/create_callback")
async def handle_create_callback(request: Request) -> JSONResponse:
    """Handle create_callback_request tool call from Retell."""
    try:
        body = await request.body()
        signature = request.headers.get("x-retell-signature", "")
        timestamp = request.headers.get("x-retell-timestamp", "")
        verify_retell_hmac(body, signature, timestamp)
    except HMACVerificationError:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    payload = RetellToolCallRequest.model_validate_json(body)
    tenant_id = _extract_tenant_id(payload)
    config = _resolve_config(tenant_id)

    result = create_callback(
        caller_phone=payload.args.get("caller_phone", payload.args.get("phone", "")),
        reason=payload.args.get("reason", ""),
        callback_minutes=int(payload.args.get("callback_minutes", 30)),
        voice_config=config,
    )
    return JSONResponse(content=result)


@voice_router.post("/send_sales_lead_alert")
async def handle_sales_lead_alert(request: Request) -> JSONResponse:
    """Handle send_sales_lead_alert tool call from Retell."""
    try:
        body = await request.body()
        signature = request.headers.get("x-retell-signature", "")
        timestamp = request.headers.get("x-retell-timestamp", "")
        verify_retell_hmac(body, signature, timestamp)
    except HMACVerificationError:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    payload = RetellToolCallRequest.model_validate_json(body)
    tenant_id = _extract_tenant_id(payload)
    config = _resolve_config(tenant_id)

    result = send_sales_lead_alert(
        equipment=payload.args.get("equipment", ""),
        customer_name=payload.args.get("customer_name", ""),
        customer_phone=payload.args.get("customer_phone", payload.args.get("phone", "")),
        address=payload.args.get("address", ""),
        voice_config=config,
    )
    return JSONResponse(content=result)


@voice_router.post("/book_service")
async def handle_book_service(request: Request) -> JSONResponse:
    """Handle book_service tool call from Retell.

    The harness owns this write path so policy, service-area validation, booking,
    fallback routing, and audit can live in one backend.
    """
    try:
        body = await request.body()
        signature = request.headers.get("x-retell-signature", "")
        timestamp = request.headers.get("x-retell-timestamp", "")
        verify_retell_hmac(body, signature, timestamp)
    except HMACVerificationError:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    payload = RetellToolCallRequest.model_validate_json(body)
    tenant_id = _extract_tenant_id(payload)
    voice_config = _resolve_config(tenant_id)
    calcom_config = _resolve_calcom_config(tenant_id)
    args = payload.args

    result = await book_service(
        customer_name=args.get("customer_name", ""),
        customer_phone=args.get("customer_phone", args.get("phone", "")),
        service_address=args.get("service_address", args.get("address", "")),
        preferred_time=args.get("preferred_time", ""),
        issue_description=args.get("issue_description", args.get("problem_description", "")),
        urgency_tier=args.get("urgency_tier", "routine"),
        voice_config=voice_config,
        calcom_config=calcom_config,
        zip_code=args.get("zip_code", ""),
    )
    return JSONResponse(content=result)


@voice_router.post("/route_call_fallback")
async def handle_route_call_fallback(request: Request) -> JSONResponse:
    """Return the deterministic fallback decision Retell should follow."""
    try:
        body = await request.body()
        signature = request.headers.get("x-retell-signature", "")
        timestamp = request.headers.get("x-retell-timestamp", "")
        verify_retell_hmac(body, signature, timestamp)
    except HMACVerificationError:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    payload = RetellToolCallRequest.model_validate_json(body)
    args = payload.args
    decision = route_call_fallback(
        FallbackContext(
            urgency_tier=args.get("urgency_tier", "routine"),
            route=args.get("route", "legitimate"),
            business_open=_as_bool(args.get("business_open"), False),
            caller_requested_human=_as_bool(args.get("caller_requested_human"), False),
            booking_failed=_as_bool(args.get("booking_failed"), False),
            confidence=float(args.get("confidence", 1.0)),
        ),
        FallbackPolicy(
            live_transfer_enabled=_as_bool(args.get("live_transfer_enabled"), False),
            callback_tasks_enabled=_as_bool(args.get("callback_tasks_enabled"), True),
            voicemail_enabled=_as_bool(args.get("voicemail_enabled"), False),
            default_transfer_number=args.get("default_transfer_number"),
            emergency_transfer_number=args.get("emergency_transfer_number"),
            voicemail_number=args.get("voicemail_number"),
        ),
    )
    return JSONResponse(content=asdict(decision))


@voice_router.post("/validate_service_area")
async def handle_validate_service_area(request: Request) -> JSONResponse:
    """Validate service area from tenant voice config before booking."""
    try:
        body = await request.body()
        signature = request.headers.get("x-retell-signature", "")
        timestamp = request.headers.get("x-retell-timestamp", "")
        verify_retell_hmac(body, signature, timestamp)
    except HMACVerificationError:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    payload = RetellToolCallRequest.model_validate_json(body)
    tenant_id = _extract_tenant_id(payload)
    config = _resolve_config(tenant_id)
    zip_code = _extract_zip(payload.args.get("zip_code", ""))
    if not zip_code:
        zip_code = _extract_zip(payload.args.get("service_address", ""))
    allowed_zips = set(getattr(config, "service_area_zips", []) or [])
    return JSONResponse(
        content={
            "in_service_area": bool(zip_code and zip_code in allowed_zips),
            "zip_code": zip_code,
        }
    )


def _extract_zip(value: str) -> str | None:
    match = re.search(r"\b(\d{5})\b", value or "")
    if not match:
        return None
    return match.group(1)


__all__ = ["voice_router"]
