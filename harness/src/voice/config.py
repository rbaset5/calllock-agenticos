"""Tenant-scoped voice configuration resolution with Redis caching."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from cache.keys import tenant_key
from voice.models import CalcomConfig, VoiceConfig

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300
_ModelT = TypeVar("_ModelT", bound=BaseModel)


class VoiceConfigError(Exception):
    """Voice configuration is missing or invalid for this tenant."""


def resolve_voice_config(
    tenant_id: str,
    *,
    redis_client: Any = None,
    db_fetch: Callable[[str], Any] | None = None,
) -> VoiceConfig:
    """Resolve VoiceConfig for a tenant, using Redis cache when available."""

    fetch_fn = db_fetch or _fetch_voice_config_from_db
    return _resolve_config(
        tenant_id,
        model_cls=VoiceConfig,
        cache_key=tenant_key(tenant_id, "voice", "config"),
        redis_client=redis_client,
        db_fetch=fetch_fn,
        config_name="voice_config",
    )


def resolve_calcom_config(
    tenant_id: str,
    *,
    redis_client: Any = None,
    db_fetch: Callable[[str], Any] | None = None,
) -> CalcomConfig:
    """Resolve CalcomConfig for a tenant, using Redis cache when available."""

    fetch_fn = db_fetch or _fetch_calcom_config_from_db
    return _resolve_config(
        tenant_id,
        model_cls=CalcomConfig,
        cache_key=tenant_key(tenant_id, "calcom", "config"),
        redis_client=redis_client,
        db_fetch=fetch_fn,
        config_name="calcom_config",
    )


def _resolve_config(
    tenant_id: str,
    *,
    model_cls: type[_ModelT],
    cache_key: str,
    redis_client: Any,
    db_fetch: Callable[[str], Any],
    config_name: str,
) -> _ModelT:
    if redis_client is not None:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return _validate_model(model_cls, _load_cached_json(cached), tenant_id, config_name)
        except Exception:
            logger.warning("voice.config_cache.error", extra={"tenant_id": tenant_id, "cache_key": cache_key})

    raw_config = db_fetch(tenant_id)
    model = _validate_model(model_cls, raw_config, tenant_id, config_name)

    if redis_client is not None:
        try:
            redis_client.setex(cache_key, _CACHE_TTL_SECONDS, model.model_dump_json())
        except Exception:
            logger.warning("voice.config_cache.set_error", extra={"tenant_id": tenant_id, "cache_key": cache_key})

    return model


def _validate_model(
    model_cls: type[_ModelT],
    raw_config: Any,
    tenant_id: str,
    config_name: str,
) -> _ModelT:
    if not raw_config:
        raise VoiceConfigError(f"Tenant {tenant_id}: {config_name} is empty or missing required fields")

    try:
        return model_cls.model_validate(raw_config)
    except ValidationError as exc:
        raise VoiceConfigError(
            f"Tenant {tenant_id}: {config_name} missing required fields: {exc}"
        ) from exc


def _load_cached_json(cached: Any) -> dict[str, Any]:
    if isinstance(cached, bytes):
        cached = cached.decode()
    return json.loads(cached)


def _fetch_voice_config_from_db(tenant_id: str) -> dict[str, Any]:
    raise NotImplementedError(f"Voice config DB fetch not implemented for tenant {tenant_id}")


def _fetch_calcom_config_from_db(tenant_id: str) -> dict[str, Any]:
    raise NotImplementedError(f"Cal.com config DB fetch not implemented for tenant {tenant_id}")


__all__ = [
    "VoiceConfigError",
    "resolve_calcom_config",
    "resolve_voice_config",
]
