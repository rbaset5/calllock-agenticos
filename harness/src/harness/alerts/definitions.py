from __future__ import annotations


ALERT_TYPES = {
    "policy_block_rate": "High percentage of runs blocked by policy decisions.",
    "worker_metric_degradation": "Worker outputs are failing verification more often than expected.",
    "job_failure_spike": "Async jobs are failing above the configured threshold.",
    "external_service_error": "External service errors detected in recent results.",
    "scheduler_stale_claims": "Claimed scheduler entries have expired or are close to expiry.",
    "scheduler_backlog_age": "Scheduler backlog contains overdue pending work beyond the configured age threshold.",
    "voice_empty_structured_output_spike": "Voice structured post-call payloads are empty above the expected rate.",
    "voice_required_field_missing_spike": "Voice required structured output fields are missing above the expected rate.",
    "voice_warning_rate_spike": "Voice extraction warnings are occurring above the expected rate.",
    "voice_route_missing_spike": "Voice calls are missing resolved routes above the expected rate.",
    "voice_safety_emergency_mismatch_signal": "Voice safety emergency classifications appear inconsistent with call content.",
}
