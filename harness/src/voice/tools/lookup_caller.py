"""lookup_caller tool handler — queries Supabase for caller history.

Returns caller's recent jobs, calls, and bookings. On any DB error,
returns {found: false} for graceful degradation — agent proceeds as new caller.

Limits per table prevent latency blowup (spec finding #20):
- Last 10 jobs
- Last 5 calls
- Last 5 bookings
"""

from __future__ import annotations

import logging
from typing import Any

from voice.services.twilio_sms import mask_phone

logger = logging.getLogger(__name__)

_JOBS_LIMIT = 10
_CALLS_LIMIT = 5
_BOOKINGS_LIMIT = 5


def lookup_caller(
    *,
    phone_number: str,
    tenant_id: str,
    db: Any,
) -> dict[str, Any]:
    """Look up caller history by phone number, scoped to tenant.

    Args:
        phone_number: Caller's phone (E.164 format).
        tenant_id: Tenant UUID — required for data isolation.
        db: Database client with get_caller_history(tenant_id, phone) method.

    Returns:
        Dict with found, jobs, calls, bookings keys. On DB failure,
        returns {found: false} with empty lists.
    """
    logger.info("lookup_caller.start", extra={"phone": mask_phone(phone_number), "tenant_id": tenant_id})

    try:
        history = db.get_caller_history(tenant_id, phone_number)
        jobs = history.get("jobs", [])[:_JOBS_LIMIT]
        calls = history.get("calls", [])[:_CALLS_LIMIT]
        bookings = history.get("bookings", [])[:_BOOKINGS_LIMIT]
    except Exception:
        logger.warning(
            "lookup_caller.query_error",
            extra={"phone": mask_phone(phone_number), "tenant_id": tenant_id},
            exc_info=True,
        )
        jobs, calls, bookings = [], [], []

    found = bool(jobs or calls or bookings)

    logger.info(
        "lookup_caller.complete",
        extra={
            "phone": mask_phone(phone_number),
            "found": found,
            "job_count": len(jobs),
            "call_count": len(calls),
            "booking_count": len(bookings),
        },
    )

    return {
        "found": found,
        "jobs": jobs,
        "calls": calls,
        "bookings": bookings,
    }


__all__ = ["lookup_caller"]
