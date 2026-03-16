from __future__ import annotations

from harness.graphs.workers.base import run_worker


def deterministic_customer_analyst(task: dict[str, Any]) -> dict[str, Any]:
    transcript = str(task.get("transcript", "")).lower()
    summary = task.get("problem_description") or "Customer inquiry received."
    sentiment = "negative" if any(word in transcript for word in ["angry", "upset", "frustrated"]) else "neutral"
    lead_route = "dispatcher" if any(word in transcript for word in ["no heat", "gas", "leak", "emergency"]) else "sales"
    churn_risk = "high" if any(word in transcript for word in ["cancel", "never coming back", "refund"]) else "low"
    return {
        "summary": summary,
        "lead_route": lead_route,
        "sentiment": sentiment,
        "churn_risk": churn_risk,
    }


def run_customer_analyst(task: dict[str, Any]) -> dict[str, Any]:
    return run_worker(task, worker_id="customer-analyst", deterministic_builder=deterministic_customer_analyst)
