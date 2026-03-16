from __future__ import annotations

import logging
from typing import Any

from growth.memory.models import GrowthDuplicateError
from growth.memory import repository as growth_repository


logger = logging.getLogger(__name__)


def handle_belief_event(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        record = growth_repository.insert_belief_event(payload)
    except GrowthDuplicateError:
        logger.info("dedup_hit", extra={"source_touchpoint_id": payload["source_touchpoint_id"]})
        return {"status": "deduped", "source_touchpoint_id": payload["source_touchpoint_id"]}
    return {"status": "inserted", "record": record}
