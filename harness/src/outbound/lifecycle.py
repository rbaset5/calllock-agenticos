"""Outbound prospect lifecycle automation rules.

Runs as a reconciliation sweep (not primary path). The dialer handles
real-time stage transitions. This module catches stale leads that fell
through cracks: overdue callbacks, unreachable prospects, voicemail
re-queues, cooling interested leads, and wrong numbers.

All mutations check current stage before updating (idempotency guard).
"""

from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any

from . import store
from .constants import OUTBOUND_TENANT_ID

logger = logging.getLogger(__name__)


def classify_lead_type(prospect: dict[str, Any]) -> str:
    """Classify lead as hot, warm, or volume based on stage + next step signals."""
    stage = str(prospect.get("stage", ""))
    has_demo = bool(prospect.get("demo_scheduled", False))
    if not has_demo:
        outbound_calls = prospect.get("outbound_calls")
        if isinstance(outbound_calls, list) and outbound_calls:
            latest = max(outbound_calls, key=lambda row: str(row.get("called_at") or ""))
            has_demo = bool(latest.get("demo_scheduled", False))
        elif prospect.get("id"):
            calls = store.list_outbound_calls(prospect_id=str(prospect["id"]))
            if calls:
                latest = max(calls, key=lambda row: str(row.get("called_at") or ""))
                has_demo = bool(latest.get("demo_scheduled", False))
    next_action = str(prospect.get("next_action_type", ""))
    if stage == "interested" and (has_demo or next_action in ("close", "close_attempt")):
        return "hot"
    if stage in ("callback", "interested"):
        return "warm"
    return "volume"


def run_lifecycle_sweep(
    *,
    tenant_id: str = OUTBOUND_TENANT_ID,
    today: str | None = None,
) -> dict[str, Any]:
    """Execute all lifecycle rules and return a summary of actions taken."""
    results: dict[str, Any] = {
        "overdue_requeued": 0,
        "strikes_disqualified": 0,
        "voicemail_requeued": 0,
        "cooling_alerts": [],
        "wrong_number_disqualified": 0,
        "errors": [],
    }
    today_date = date.fromisoformat(today) if today else date.today()

    # Rule 1: Overdue callbacks (3+ days past callback_date)
    try:
        overdue = store.list_overdue_callbacks(tenant_id=tenant_id, today=today, grace_days=3)
        for prospect in overdue:
            pid = prospect["prospect_id"]
            try:
                result = store.update_outbound_prospect(pid, {
                    "stage": "call_ready",
                    "disqualification_reason": None,
                    "next_action_date": None,
                    "next_action_type": None,
                }, expected_stage="callback")
                if result:
                    results["overdue_requeued"] += 1
                    logger.info("Requeued overdue callback: %s (%s)", prospect.get("business_name"), pid)
                else:
                    logger.info("Skipped requeue (stage changed): %s (%s)", prospect.get("business_name"), pid)
            except Exception as e:
                results["errors"].append(f"Requeue {pid}: {e}")
                logger.error("Failed to requeue %s: %s", pid, e)
    except Exception as e:
        results["errors"].append(f"list_overdue_callbacks: {e}")
        logger.error("Failed to list overdue callbacks: %s", e)

    # Rule 2: 3-strike no-answer disqualification (warm-lead protected)
    # Uses expected_stage guard to prevent overwriting concurrent stage changes.
    try:
        strikes = store.list_recent_no_answer_strikes(tenant_id=tenant_id, min_strikes=3)
        for prospect in strikes:
            pid = prospect["prospect_id"]
            current_stage = prospect.get("stage")
            if current_stage not in ("call_ready", "called"):
                continue  # only disqualify from eligible stages
            try:
                result = store.update_outbound_prospect(pid, {
                    "stage": "disqualified",
                    "disqualification_reason": "unreachable_3_strikes",
                }, expected_stage=current_stage)
                if result:
                    results["strikes_disqualified"] += 1
                    logger.info("Auto-disqualified (3 strikes): %s (%s)", prospect.get("business_name"), pid)
                else:
                    logger.info("Skipped disqualify (stage changed): %s (%s)", prospect.get("business_name"), pid)
            except Exception as e:
                results["errors"].append(f"Disqualify {pid}: {e}")
                logger.error("Failed to disqualify %s: %s", pid, e)
    except Exception as e:
        results["errors"].append(f"list_recent_no_answer_strikes: {e}")
        logger.error("Failed to list no-answer strikes: %s", e)

    # Rule 3: Voicemail requeue (3+ calendar days since voicemail)
    try:
        voicemails = store.list_voicemail_requeue_candidates(tenant_id=tenant_id, min_days=3)
        for prospect in voicemails:
            pid = prospect["prospect_id"]
            try:
                result = store.update_outbound_prospect(pid, {
                    "stage": "call_ready",
                }, expected_stage="called")
                if result:
                    results["voicemail_requeued"] += 1
                    logger.info("Requeued voicemail follow-up: %s (%s)", prospect.get("business_name"), pid)
                else:
                    logger.info("Skipped voicemail requeue (stage changed): %s (%s)", prospect.get("business_name"), pid)
            except Exception as e:
                results["errors"].append(f"Voicemail requeue {pid}: {e}")
                logger.error("Failed to requeue voicemail %s: %s", pid, e)
    except Exception as e:
        results["errors"].append(f"list_voicemail_requeue_candidates: {e}")
        logger.error("Failed to list voicemail candidates: %s", e)

    # Rule 4: Cooling interested leads (5+ days, no demo scheduled) — ALERT ONLY
    try:
        cooling = store.list_cooling_leads(tenant_id=tenant_id, stale_days=5)
        for prospect in cooling:
            pid = prospect["prospect_id"]
            # Ensure warm leads have an explicit next action even if they are cooling.
            try:
                store.update_outbound_prospect(
                    pid,
                    {
                        "next_action_date": (today_date + timedelta(days=1)).isoformat(),
                        "next_action_type": "close_attempt",
                    },
                    expected_stage="interested",
                )
            except Exception:
                logger.exception("Failed to set next action for cooling lead %s", pid)
            results["cooling_alerts"].append({
                "prospect_id": pid,
                "business_name": prospect.get("business_name", "Unknown"),
                "phone": prospect.get("phone", ""),
                "metro": prospect.get("metro", ""),
                "days_since_interested": prospect.get("days_since_interested", 0),
            })
            logger.info("Cooling lead alert: %s (%d days)", prospect.get("business_name"), prospect.get("days_since_interested", 0))
    except Exception as e:
        results["errors"].append(f"list_cooling_leads: {e}")
        logger.error("Failed to list cooling leads: %s", e)

    # Rule 5: Wrong number cleanup
    try:
        wrong = store.list_wrong_numbers(tenant_id=tenant_id)
        for prospect in wrong:
            pid = prospect.get("id") or prospect.get("prospect_id")
            current_stage = prospect.get("stage")
            if current_stage == "disqualified":
                continue
            try:
                result = store.update_outbound_prospect(pid, {
                    "stage": "disqualified",
                    "disqualification_reason": "wrong_number",
                }, expected_stage=current_stage)
                if result:
                    results["wrong_number_disqualified"] += 1
                    logger.info("Disqualified wrong number: %s (%s)", prospect.get("business_name"), pid)
            except Exception as e:
                results["errors"].append(f"Wrong number {pid}: {e}")
                logger.error("Failed to disqualify wrong number %s: %s", pid, e)
    except Exception as e:
        results["errors"].append(f"list_wrong_numbers: {e}")
        logger.error("Failed to list wrong numbers: %s", e)

    total_actions = (
        results["overdue_requeued"]
        + results["strikes_disqualified"]
        + results["voicemail_requeued"]
        + results["wrong_number_disqualified"]
        + len(results["cooling_alerts"])
    )
    results["total_actions"] = total_actions
    logger.info(
        "Lifecycle sweep complete: %d actions (%d requeued, %d disqualified, %d cooling alerts, %d errors)",
        total_actions,
        results["overdue_requeued"] + results["voicemail_requeued"],
        results["strikes_disqualified"] + results["wrong_number_disqualified"],
        len(results["cooling_alerts"]),
        len(results["errors"]),
    )
    return results
