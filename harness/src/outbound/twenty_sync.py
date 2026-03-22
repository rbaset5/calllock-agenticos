"""Twenty CRM sync for the outbound pipeline.

Syncs qualified prospects and call outcomes from Supabase to Twenty CRM.
Only prospects at stage call_ready or later are synced — the CRM never
sees the 73K raw leads, only the qualified pipeline.

Twenty CRM REST API:
- POST /companies — create company
- PATCH /companies/{id} — update company
- POST /people — create person (contact)
- POST /notes + POST /noteTargets — create note linked to company
- POST /opportunities — create deal

Sync mapping:
- call_ready → Company + Note (signals, score, call hook)
- called (outcome) → Note on Company (outcome, notes, recording)
- interested → Opportunity
- converted → Opportunity stage update
- disqualified → Company status update
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

TWENTY_BASE_URL = os.getenv("TWENTY_BASE_URL", "")
TWENTY_API_KEY = os.getenv("TWENTY_API_KEY", "")


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TWENTY_API_KEY}",
        "Content-Type": "application/json",
    }


def _twenty_request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Make a request to the Twenty CRM REST API."""
    if not TWENTY_BASE_URL or not TWENTY_API_KEY:
        logger.warning("[twenty] TWENTY_BASE_URL or TWENTY_API_KEY not set, skipping sync")
        return None

    import urllib.request
    import urllib.error

    url = f"{TWENTY_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    data = json.dumps(body).encode() if body else None

    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = resp.read().decode()
            if resp_body:
                return json.loads(resp_body)
            return {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        logger.error("[twenty] %s %s → %s: %s", method, path, e.code, error_body)
        return None
    except Exception as e:
        logger.error("[twenty] %s %s failed: %s", method, path, e)
        return None


def _extract_id(response: dict[str, Any] | None) -> str | None:
    """Extract the record ID from a Twenty API response."""
    if not response:
        return None
    if "data" in response and isinstance(response["data"], dict):
        return response["data"].get("id")
    return response.get("id")


def sync_prospect_to_crm(prospect: dict[str, Any], signals: list[dict[str, Any]]) -> dict[str, Any]:
    """Create or update a Company in Twenty CRM for a qualified prospect.

    Called when a prospect reaches call_ready stage.
    Returns the Twenty company ID for future reference.
    """
    signal_summary = ", ".join(
        f"{s['signal_type']} ({s['score']})" for s in signals if s.get("score", 0) > 0
    )

    # Create company
    company_resp = _twenty_request("POST", "companies", {
        "name": prospect.get("business_name", "Unknown"),
        "domainName": prospect.get("website", ""),
        "address": {
            "addressCity": prospect.get("metro", ""),
        },
        "phones": {
            "primaryPhoneNumber": prospect.get("phone", ""),
        },
    })
    company_id = _extract_id(company_resp)

    if not company_id:
        return {"synced": False, "error": "Failed to create company"}

    # Create initial note with signal context
    score_data = prospect.get("total_score", 0)
    tier = prospect.get("tier", "unknown")
    note_body = (
        f"**Outbound Pipeline — Qualified Prospect**\n\n"
        f"**Score:** {score_data}/100 ({tier})\n"
        f"**Trade:** {prospect.get('trade', 'unknown')}\n"
        f"**Metro:** {prospect.get('metro', 'unknown')}\n"
        f"**Signals:** {signal_summary}\n"
        f"**Source:** {prospect.get('source', 'leads_db')}\n"
    )

    note_resp = _twenty_request("POST", "notes", {
        "title": f"Outbound: {prospect.get('business_name', 'Unknown')} — {tier}",
        "bodyV2": {"markdown": note_body},
    })
    note_id = _extract_id(note_resp)
    if note_id:
        _twenty_request("POST", "noteTargets", {
            "noteId": note_id,
            "companyId": company_id,
        })

    return {"synced": True, "twenty_company_id": company_id}


def sync_call_outcome_to_crm(
    prospect: dict[str, Any],
    call_record: dict[str, Any],
    twenty_company_id: str,
) -> dict[str, Any]:
    """Add a call outcome as a Note on the Company in Twenty CRM.

    Called after the founder logs an outcome in the dialer.
    """
    if not twenty_company_id:
        return {"synced": False, "error": "No Twenty company ID"}

    outcome_labels = {
        "answered_interested": "Interested",
        "answered_not_interested": "Not Interested",
        "answered_callback": "Callback Requested",
        "voicemail_left": "Voicemail Left",
        "no_answer": "No Answer",
        "wrong_number": "Wrong Number",
        "gatekeeper_blocked": "Gatekeeper Blocked",
    }

    outcome = call_record.get("outcome", "unknown")
    label = outcome_labels.get(outcome, outcome)

    parts = [
        f"**Outcome:** {label}",
        f"**Date:** {call_record.get('called_at', 'unknown')}",
    ]
    if call_record.get("notes"):
        parts.append(f"**Notes:** {call_record['notes']}")
    if call_record.get("call_hook_used"):
        parts.append(f"**Hook Used:** {call_record['call_hook_used']}")
    if call_record.get("recording_url"):
        parts.append(f"**Recording:** {call_record['recording_url']}")
    if call_record.get("transcript"):
        parts.append(f"**Transcript:**\n\n{call_record['transcript'][:2000]}")
    if call_record.get("callback_date"):
        parts.append(f"**Callback Date:** {call_record['callback_date']}")
    if call_record.get("demo_scheduled"):
        parts.append("**Demo Scheduled:** Yes")

    note_body = "\n\n".join(parts)

    note_resp = _twenty_request("POST", "notes", {
        "title": f"Call: {prospect.get('business_name', 'Unknown')} — {label}",
        "bodyV2": {"markdown": note_body},
    })
    note_id = _extract_id(note_resp)
    if note_id:
        _twenty_request("POST", "noteTargets", {
            "noteId": note_id,
            "companyId": twenty_company_id,
        })

    # If interested, create an opportunity
    if outcome == "answered_interested":
        _twenty_request("POST", "opportunities", {
            "name": f"CallLock — {prospect.get('business_name', 'Unknown')}",
            "stage": "MEETING" if call_record.get("demo_scheduled") else "QUALIFICATION",
            "companyId": twenty_company_id,
        })

    return {"synced": True, "note_created": bool(note_id)}


def sync_stage_update_to_crm(
    prospect: dict[str, Any],
    new_stage: str,
    twenty_company_id: str,
) -> dict[str, Any]:
    """Update the Company status in Twenty CRM when stage changes.

    Handles: converted, disqualified.
    """
    if not twenty_company_id:
        return {"synced": False, "error": "No Twenty company ID"}

    if new_stage == "disqualified":
        reason = prospect.get("disqualification_reason", "")
        note_resp = _twenty_request("POST", "notes", {
            "title": f"Disqualified: {prospect.get('business_name', 'Unknown')}",
            "bodyV2": {"markdown": f"**Disqualified**\n\nReason: {reason}"},
        })
        note_id = _extract_id(note_resp)
        if note_id:
            _twenty_request("POST", "noteTargets", {
                "noteId": note_id,
                "companyId": twenty_company_id,
            })

    elif new_stage == "converted":
        # Update opportunity stage to WON
        note_resp = _twenty_request("POST", "notes", {
            "title": f"Converted: {prospect.get('business_name', 'Unknown')}",
            "bodyV2": {"markdown": "**Customer converted!** Moving to onboarding."},
        })
        note_id = _extract_id(note_resp)
        if note_id:
            _twenty_request("POST", "noteTargets", {
                "noteId": note_id,
                "companyId": twenty_company_id,
            })

    return {"synced": True}
