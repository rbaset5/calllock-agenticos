from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from db.repository import get_tenant, get_tenant_config
from growth.memory.models import AttributionTokenPayload, InvalidAttributionTokenError


TOKEN_EXPIRY_SECONDS = 90 * 24 * 60 * 60


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _normalize_keys(keys: dict[str, Any]) -> dict[str, Any]:
    current = keys.get("current") or {}
    previous = keys.get("previous")
    if not current:
        raise InvalidAttributionTokenError("missing_current_key")
    return {"current": current, "previous": previous}


def _tenant_keys(tenant_id: str) -> dict[str, Any]:
    config = get_tenant_config(tenant_id)
    raw = config.get("attribution_keys") or {}
    return _normalize_keys(raw)


def _canonical_tenant_id(tenant_id: str) -> str:
    try:
        return str(get_tenant(tenant_id)["id"])
    except Exception:
        return tenant_id


def _sign(secret_b64: str, payload_b64: str) -> str:
    secret = _base64url_decode(secret_b64)
    digest = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return _base64url_encode(digest)


def mint_token(
    tenant_id: str,
    prospect_id: str,
    *,
    experiment_id: str | None = None,
    arm_id: str | None = None,
    issued_at: int | None = None,
) -> str:
    canonical_tenant_id = _canonical_tenant_id(tenant_id)
    keys = _tenant_keys(tenant_id)
    current = keys["current"]
    iat = issued_at or int(time.time())
    payload = {
        "v": 1,
        "tid": canonical_tenant_id,
        "pid": prospect_id,
        "eid": experiment_id,
        "aid": arm_id,
        "iat": iat,
        "kid": current["kid"],
    }
    payload_b64 = _base64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _sign(current["secret"], payload_b64)
    return f"{payload_b64}.{signature}"


def validate_token(token: str, expected_tenant_id: str, *, now: int | None = None) -> AttributionTokenPayload:
    try:
        payload_b64, signature_b64 = token.rsplit(".", 1)
    except ValueError as exc:
        raise InvalidAttributionTokenError("malformed") from exc

    try:
        payload = json.loads(_base64url_decode(payload_b64))
    except Exception as exc:  # pragma: no cover - exercised in tests
        raise InvalidAttributionTokenError("decode_error") from exc

    canonical_tenant_id = _canonical_tenant_id(expected_tenant_id)
    if payload.get("tid") != canonical_tenant_id:
        raise InvalidAttributionTokenError("tenant_mismatch")

    keys = _tenant_keys(expected_tenant_id)
    kid = payload.get("kid")
    candidates = [entry for entry in (keys["current"], keys.get("previous")) if entry]
    key_entry = next((entry for entry in candidates if entry["kid"] == kid), None)
    if key_entry is None:
        raise InvalidAttributionTokenError("unknown_key")

    expected_signature = _sign(key_entry["secret"], payload_b64)
    if not hmac.compare_digest(signature_b64, expected_signature):
        raise InvalidAttributionTokenError("signature_invalid")

    current_time = now or int(time.time())
    if current_time - int(payload["iat"]) > TOKEN_EXPIRY_SECONDS:
        raise InvalidAttributionTokenError("expired")

    return AttributionTokenPayload(
        version=int(payload["v"]),
        tenant_id=str(payload["tid"]),
        prospect_id=str(payload["pid"]),
        experiment_id=payload.get("eid"),
        arm_id=payload.get("aid"),
        issued_at=int(payload["iat"]),
        key_id=str(payload["kid"]),
    )


def rotate_keys(keys: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    normalized = _normalize_keys(keys)
    current = normalized["current"]
    key_id = current.get("kid", "k1")
    suffix = int(key_id[1:]) + 1 if key_id.startswith("k") and key_id[1:].isdigit() else 2
    created_at = (now or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")
    return {
        "current": {
            "kid": f"k{suffix}",
            "secret": _base64url_encode(secrets.token_bytes(32)),
            "created_at": created_at,
        },
        "previous": current,
    }
