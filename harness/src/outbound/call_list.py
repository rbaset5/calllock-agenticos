from __future__ import annotations

from typing import Any

from . import store
from .constants import CALL_READY_LIMIT, OUTBOUND_TENANT_ID


def get_ranked_prospects(limit: int = CALL_READY_LIMIT) -> list[dict[str, Any]]:
    return store.list_ranked_call_ready_prospects(tenant_id=OUTBOUND_TENANT_ID, limit=limit)
