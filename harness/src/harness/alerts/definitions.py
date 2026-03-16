from __future__ import annotations


ALERT_TYPES = {
    "policy_block_rate": "High percentage of runs blocked by policy decisions.",
    "worker_metric_degradation": "Worker outputs are failing verification more often than expected.",
    "job_failure_spike": "Async jobs are failing above the configured threshold.",
    "external_service_error": "External service errors detected in recent results.",
    "scheduler_stale_claims": "Claimed scheduler entries have expired or are close to expiry.",
    "scheduler_backlog_age": "Scheduler backlog contains overdue pending work beyond the configured age threshold.",
}
