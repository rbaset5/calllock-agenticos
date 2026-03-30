"""CEO Agent tools for the outbound pipeline.

Five query tools giving the founder conversational access to outbound
pipeline data via the Hermes CEO agent. Plus one tool to manage metros.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import store


def outbound_funnel_summary(*, days: int = 7) -> dict[str, Any]:
    """Weekly/daily funnel metrics for the outbound pipeline.

    Example: "How did outbound do this week?"
    """
    prospects = store.list_outbound_prospects()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()
    calls = store.list_outbound_calls(start_date=cutoff.date().isoformat())

    recent_calls = [c for c in calls if (c.get("called_at") or "") >= cutoff_iso]
    recent_prospects = [p for p in prospects if (p.get("discovered_at") or "") >= cutoff_iso]

    outcomes = {}
    for call in recent_calls:
        outcome = call.get("outcome", "unknown")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    stages = {}
    for prospect in prospects:
        stage = prospect.get("stage", "unknown")
        stages[stage] = stages.get(stage, 0) + 1

    return {
        "period_days": days,
        "total_prospects": len(prospects),
        "new_prospects_this_period": len(recent_prospects),
        "pipeline_by_stage": stages,
        "calls_this_period": len(recent_calls),
        "outcomes_this_period": outcomes,
        "demos_scheduled": sum(1 for c in recent_calls if c.get("demo_scheduled")),
        "callbacks_pending": stages.get("callback", 0),
    }


def outbound_prospect_lookup(*, business_name: str = "", phone: str = "") -> dict[str, Any]:
    """Look up a specific prospect's full history.

    Example: "Why did we disqualify Johnson HVAC?"
    """
    prospects = store.list_outbound_prospects()

    match = None
    search = (business_name or phone).lower()
    for p in prospects:
        if business_name and business_name.lower() in (p.get("business_name") or "").lower():
            match = p
            break
        if phone and phone in (p.get("phone_normalized") or ""):
            match = p
            break

    if not match:
        return {"found": False, "search": search}

    prospect_id = match["id"]
    signals = store.list_prospect_signals(prospect_id=prospect_id)
    calls = store.list_outbound_calls(prospect_id=prospect_id)
    tests = store.list_call_tests(prospect_id=prospect_id)

    return {
        "found": True,
        "prospect": {
            "business_name": match.get("business_name"),
            "phone": match.get("phone"),
            "metro": match.get("metro"),
            "trade": match.get("trade"),
            "stage": match.get("stage"),
            "score": match.get("total_score"),
            "tier": match.get("score_tier"),
            "disqualification_reason": match.get("disqualification_reason"),
            "twenty_company_id": match.get("twenty_company_id"),
        },
        "signals": [
            {"type": s.get("signal_type"), "score": s.get("score"), "tier": s.get("signal_tier")}
            for s in signals
        ],
        "call_tests": [
            {"result": t.get("result"), "local_time": t.get("local_time"), "day": t.get("day_of_week")}
            for t in tests
        ],
        "calls": [
            {
                "outcome": c.get("outcome"),
                "notes": c.get("notes"),
                "called_at": c.get("called_at"),
                "hook_used": c.get("call_hook_used"),
                "demo": c.get("demo_scheduled"),
            }
            for c in calls
        ],
    }


def outbound_signal_effectiveness() -> dict[str, Any]:
    """Which signals predict interested outcomes.

    Example: "Which signals are actually converting?"
    """
    calls = store.list_outbound_calls()
    prospects = store.list_outbound_prospects()

    prospect_map = {p["id"]: p for p in prospects}

    signal_outcomes: dict[str, dict[str, int]] = {}

    for call in calls:
        prospect = prospect_map.get(call.get("prospect_id", ""))
        if not prospect:
            continue

        signals = store.list_prospect_signals(prospect_id=prospect["id"])
        outcome = call.get("outcome", "unknown")
        is_positive = outcome in ("answered_interested", "answered_callback")

        for signal in signals:
            sig_type = signal.get("signal_type", "unknown")
            if sig_type not in signal_outcomes:
                signal_outcomes[sig_type] = {"total": 0, "positive": 0}
            signal_outcomes[sig_type]["total"] += 1
            if is_positive:
                signal_outcomes[sig_type]["positive"] += 1

    effectiveness = []
    for sig_type, counts in signal_outcomes.items():
        rate = counts["positive"] / counts["total"] if counts["total"] > 0 else 0
        effectiveness.append({
            "signal": sig_type,
            "total_calls": counts["total"],
            "positive_outcomes": counts["positive"],
            "conversion_rate": round(rate * 100, 1),
        })

    effectiveness.sort(key=lambda x: x["conversion_rate"], reverse=True)
    return {"signal_effectiveness": effectiveness}


def outbound_metro_performance() -> dict[str, Any]:
    """Compare metros by answer rate and interest rate.

    Example: "Which metros should I focus on?"
    """
    calls = store.list_outbound_calls()
    prospects = store.list_outbound_prospects()

    prospect_map = {p["id"]: p for p in prospects}

    metro_stats: dict[str, dict[str, int]] = {}

    for call in calls:
        prospect = prospect_map.get(call.get("prospect_id", ""))
        if not prospect:
            continue
        metro = prospect.get("metro") or "unknown"
        if metro not in metro_stats:
            metro_stats[metro] = {"calls": 0, "answered": 0, "interested": 0, "prospects": 0}
        metro_stats[metro]["calls"] += 1
        if call.get("outcome", "").startswith("answered"):
            metro_stats[metro]["answered"] += 1
        if call.get("outcome") in ("answered_interested", "answered_callback"):
            metro_stats[metro]["interested"] += 1

    for prospect in prospects:
        metro = prospect.get("metro") or "unknown"
        if metro not in metro_stats:
            metro_stats[metro] = {"calls": 0, "answered": 0, "interested": 0, "prospects": 0}
        metro_stats[metro]["prospects"] += 1

    performance = []
    for metro, stats in metro_stats.items():
        answer_rate = stats["answered"] / stats["calls"] if stats["calls"] > 0 else 0
        interest_rate = stats["interested"] / stats["calls"] if stats["calls"] > 0 else 0
        performance.append({
            "metro": metro,
            "total_prospects": stats["prospects"],
            "total_calls": stats["calls"],
            "answer_rate": round(answer_rate * 100, 1),
            "interest_rate": round(interest_rate * 100, 1),
        })

    performance.sort(key=lambda x: x["interest_rate"], reverse=True)
    return {"metro_performance": performance}


def outbound_manage_metros(*, action: str, metro: str) -> dict[str, Any]:
    """Add or remove a target metro.

    Example: "Add Tucson to outbound"

    Args:
        action: "add" or "remove"
        metro: metro name (e.g., "Tucson")
    """
    from pathlib import Path

    metros_path = Path(__file__).resolve().parents[3] / "knowledge" / "outbound" / "metros.md"
    if not metros_path.exists():
        return {"error": "metros.md not found"}

    content = metros_path.read_text()

    if action == "add":
        if metro.lower() in content.lower():
            return {"action": "add", "metro": metro, "result": "already_exists"}
        content = content.rstrip() + f"\n- {metro}\n"
        metros_path.write_text(content)
        return {"action": "add", "metro": metro, "result": "added"}

    elif action == "remove":
        lines = content.split("\n")
        new_lines = [line for line in lines if metro.lower() not in line.lower()]
        if len(new_lines) == len(lines):
            return {"action": "remove", "metro": metro, "result": "not_found"}
        metros_path.write_text("\n".join(new_lines))
        return {"action": "remove", "metro": metro, "result": "removed"}

    return {"error": f"Unknown action: {action}"}
