"""FastAPI router for Retell tool call webhooks.

Each tool has a dedicated endpoint (per-tool URLs, not a dispatcher).
Auth: Retell HMAC-SHA256 verification via dependency.
Retell v10 sends each tool call to its own URL.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from voice.auth import HMACVerificationError, verify_retell_hmac
from voice.config import VoiceConfigError, resolve_voice_config
from voice.models import RetellToolCallRequest
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
    except (HMACVerificationError, RuntimeError) as exc:
        logger.warning("voice.hmac.failed", extra={"error": str(exc)})
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
        "+13126463826": "e51d9ae7-9cde-4dca-a49c-4744c39240bc",
    }
    return _PHONE_TO_TENANT.get(to_number)


async def require_retell_hmac(request: Request) -> None:
    """FastAPI dependency that verifies Retell HMAC-SHA256 signatures."""
    body = await request.body()
    signature = request.headers.get("x-retell-signature", "")
    timestamp = request.headers.get("x-retell-timestamp", "")
    try:
        verify_retell_hmac(body, signature, timestamp)
    except (HMACVerificationError, RuntimeError) as exc:
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


@voice_router.post("/lookup_caller")
async def handle_lookup_caller(request: Request) -> JSONResponse:
    """Handle lookup_caller tool call from Retell."""
    try:
        body = await request.body()
        signature = request.headers.get("x-retell-signature", "")
        timestamp = request.headers.get("x-retell-timestamp", "")
        verify_retell_hmac(body, signature, timestamp)
    except (HMACVerificationError, RuntimeError) as exc:
        logger.warning("voice.hmac.failed", extra={"error": str(exc)})
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
    except (HMACVerificationError, RuntimeError) as exc:
        logger.warning("voice.hmac.failed", extra={"error": str(exc)})
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
    except (HMACVerificationError, RuntimeError) as exc:
        logger.warning("voice.hmac.failed", extra={"error": str(exc)})
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


__all__ = ["voice_router"]
