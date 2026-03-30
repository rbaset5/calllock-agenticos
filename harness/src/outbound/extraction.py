"""Post-call AI extraction for outbound sales calls.

Takes a call transcript and extracts structured discovery data:
objection type, pain signals, buying temperature, status quo details.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

try:
    from litellm import completion
except Exception:  # pragma: no cover
    completion = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

MIN_TRANSCRIPT_LENGTH = 50

EXTRACTION_FIELDS = [
    "reached_decision_maker",
    "current_call_handling",
    "missed_call_pain",
    "after_hours_workflow",
    "objection_type",
    "objection_verbatim",
    "buying_temperature",
    "follow_up_action",
    "follow_up_date",
    "status_quo_details",
]

SYSTEM_PROMPT = """You are analyzing a transcript of an outbound sales call where the caller (Rashid) is pitching an AI receptionist service to an HVAC business. Extract the following fields from the prospect's responses. Return strict JSON only.

Fields:
- reached_decision_maker (boolean): Did Rashid speak with the business owner or someone who makes purchasing decisions?
- current_call_handling (string): How does this business currently handle incoming calls? Options: answering service (name it), wife/partner, office staff, voicemail only, dispatch service, none/unknown.
- missed_call_pain (string): How much pain does the prospect express about missing calls? Options: none, mild, moderate, severe.
- after_hours_workflow (string): What happens when customers call after business hours? Describe briefly.
- objection_type (string): The primary objection raised. Options: price, timing, skepticism, already_solved, not_decision_maker, no_need, none.
- objection_verbatim (string): Exact quote of the objection if one was raised. Empty string if none.
- buying_temperature (string): How interested was the prospect? Options: cold, warm, hot.
- follow_up_action (string): What was agreed as next step? Options: none, callback_scheduled, send_info, demo_booked, trial_started.
- follow_up_date (string or null): If a follow-up was scheduled, the date. Null otherwise.
- status_quo_details (string): Freeform summary of how they handle calls today, in 1-2 sentences."""


def extract_from_transcript(
    transcript: str,
    prospect_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract structured discovery data from a call transcript.

    Returns dict with keys: extraction, raw_response, status.
    Status is one of: complete, failed, skipped.
    """
    if not transcript or len(transcript.strip()) < MIN_TRANSCRIPT_LENGTH:
        return {"extraction": None, "raw_response": None, "status": "skipped"}

    if completion is None:
        logger.error("litellm is not installed, cannot run extraction")
        return {"extraction": None, "raw_response": None, "status": "failed"}

    context_line = ""
    if prospect_context:
        name = prospect_context.get("business_name", "")
        metro = prospect_context.get("metro", "")
        reviews = prospect_context.get("reviews", "")
        if name:
            context_line = f"\nBusiness: {name}, Metro: {metro}, Reviews: {reviews}"

    user_message = f"Transcript:{context_line}\n\n{transcript}"

    model = os.getenv("LITELLM_MODEL", "claude-sonnet-4-6")
    max_retries = 2
    raw_response = None

    for attempt in range(max_retries):
        try:
            response = completion(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0,
            )
            raw_response = response.choices[0].message.content
            parsed = json.loads(raw_response)
            extraction = {field: parsed.get(field) for field in EXTRACTION_FIELDS}
            return {
                "extraction": extraction,
                "raw_response": raw_response,
                "status": "complete",
            }
        except json.JSONDecodeError:
            logger.warning(
                "Extraction JSON parse failed (attempt %d/%d)",
                attempt + 1,
                max_retries,
            )
            if attempt < max_retries - 1:
                continue
            return {
                "extraction": None,
                "raw_response": raw_response,
                "status": "failed",
            }
        except Exception:
            logger.exception("Extraction LLM call failed (attempt %d/%d)", attempt + 1, max_retries)
            if attempt < max_retries - 1:
                continue
            return {
                "extraction": None,
                "raw_response": str(raw_response) if raw_response else None,
                "status": "failed",
            }
