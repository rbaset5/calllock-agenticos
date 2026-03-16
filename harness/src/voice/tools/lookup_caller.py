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
    db: Any,
) -> dict[str, Any]:
    """Look up caller history by phone number.

    Args:
        phone_number: Caller's phone (E.164 format).
        db: Database client with query_jobs_by_phone, query_calls_by_phone,
            query_bookings_by_phone methods.

    Returns:
        Dict with found, jobs, calls, bookings keys. On DB failure,
        returns {found: false} with empty lists.
    """
    logger.info("lookup_caller.start", extra={"phone": mask_phone(phone_number)})

    jobs = _safe_query(db.query_jobs_by_phone, phone_number, _JOBS_LIMIT, "jobs")
    calls = _safe_query(db.query_calls_by_phone, phone_number, _CALLS_LIMIT, "calls")
    bookings = _safe_query(db.query_bookings_by_phone, phone_number, _BOOKINGS_LIMIT, "bookings")

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


def _safe_query(
    query_fn: Any,
    phone_number: str,
    limit: int,
    table_name: str,
) -> list[dict[str, Any]]:
    """Execute a DB query with error handling. Returns empty list on failure."""
    try:
        results = query_fn(phone_number)
        return results[:limit]
    except Exception:
        logger.warning(
            "lookup_caller.query_error",
            extra={"table": table_name, "phone": mask_phone(phone_number)},
            exc_info=True,
        )
        return []


__all__ = ["lookup_caller"]
