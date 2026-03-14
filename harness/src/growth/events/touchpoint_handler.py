from __future__ import annotations

import logging
from typing import Any

from growth.attribution.tokens import validate_token
from growth.idempotency.keys import require_touchpoint_id
from growth.memory.models import GrowthDuplicateError, InvalidAttributionTokenError
from growth.memory import repository as growth_repository


logger = logging.getLogger(__name__)


def handle_touchpoint(payload: dict[str, Any]) -> dict[str, Any]:
    require_touchpoint_id(str(payload.get("touchpoint_id", "")))
    token = payload.get("attribution_token")
    if token:
        try:
            validate_token(str(token), str(payload["tenant_id"]))
        except InvalidAttributionTokenError as exc:
            logger.warning("attribution_invalid", extra={"reason": str(exc), "tenant_id": payload["tenant_id"]})
            return {"status": "discarded", "reason": str(exc)}

    try:
        record = growth_repository.insert_touchpoint(payload)
    except GrowthDuplicateError:
        logger.info("dedup_hit", extra={"touchpoint_id": payload["touchpoint_id"]})
        return {"status": "deduped", "touchpoint_id": payload["touchpoint_id"]}
    return {"status": "inserted", "record": record}
