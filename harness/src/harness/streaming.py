"""NDJSON streaming for real-time run status.

Inspired by Antspace's NDJSON deployment status pattern:
  packaging → uploading → building → deploying → deployed

Provides a streaming endpoint that emits one JSON line per run_status
transition. Consumers (Discord projector, CEO agent, watchdog) connect
once and receive progressive updates without polling.

Protocol:
  - Content-Type: application/x-ndjson
  - Each line is a complete JSON object followed by \\n
  - Terminal statuses: completed, quarantined, failed
  - Heartbeat every 15s to keep connections alive
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncGenerator
from collections import defaultdict

# In-memory pub/sub for run status updates.
# Key: run_id, Value: list of asyncio.Queue subscribers.
_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

TERMINAL_STATUSES = frozenset(["completed", "quarantined", "failed"])
HEARTBEAT_INTERVAL_SECONDS = 15


def publish_run_status(run_id: str, status: str, *, extra: dict[str, Any] | None = None) -> None:
    """Called by the supervisor (or _instrument_node) to broadcast a status change."""
    event = {
        "run_id": run_id,
        "status": status,
        "timestamp": time.time(),
        **(extra or {}),
    }
    for queue in _subscribers.get(run_id, []):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass  # drop if consumer is too slow


async def subscribe_run(run_id: str) -> AsyncGenerator[str, None]:
    """Yield NDJSON lines for a run's status transitions."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    _subscribers[run_id].append(queue)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL_SECONDS)
                yield json.dumps(event) + "\n"
                if event.get("status") in TERMINAL_STATUSES:
                    return
            except asyncio.TimeoutError:
                yield json.dumps({"heartbeat": True, "run_id": run_id, "timestamp": time.time()}) + "\n"
    finally:
        _subscribers[run_id].remove(queue)
        if not _subscribers[run_id]:
            del _subscribers[run_id]
