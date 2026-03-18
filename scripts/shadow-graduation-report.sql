-- Shadow Mode Graduation Report
-- Run this query to check if a worker is ready to switch from
-- call_llm() baseline to Hermes primary.
--
-- Graduation criteria:
--   field_match_rate >= 0.95 across 50+ runs
--   hermes_error rate < 5%
--   p95 hermes_latency_ms <= 30000
--   hermes cost <= 5x baseline (estimated from iterations)

select
    worker_id,
    count(*) as total_runs,
    count(*) filter (where hermes_error is null) as hermes_successes,
    count(*) filter (where hermes_error is not null) as hermes_failures,
    round(100.0 * count(*) filter (where hermes_error is null) / count(*), 1) as success_rate_pct,
    round(avg(field_match_rate)::numeric, 4) as avg_match_rate,
    round(min(field_match_rate)::numeric, 4) as min_match_rate,
    percentile_cont(0.5) within group (order by field_match_rate) as median_match_rate,
    round(avg(baseline_latency_ms)::numeric, 0) as avg_baseline_ms,
    round(avg(hermes_latency_ms)::numeric, 0) as avg_hermes_ms,
    percentile_cont(0.95) within group (order by hermes_latency_ms) as p95_hermes_ms,
    round(avg(hermes_iterations)::numeric, 1) as avg_iterations,
    case
        when count(*) >= 50
            and avg(field_match_rate) >= 0.95
            and 100.0 * count(*) filter (where hermes_error is null) / count(*) >= 95
            and percentile_cont(0.95) within group (order by hermes_latency_ms) <= 30000
        then 'READY'
        else 'NOT READY'
    end as graduation_status
from shadow_comparisons
where created_at > now() - interval '30 days'
group by worker_id
order by worker_id;
