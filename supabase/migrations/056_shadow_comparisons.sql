-- Shadow mode comparison results for Hermes rollout.
-- Each row records a field-by-field comparison between
-- call_llm() baseline and run_hermes_worker() for a single run.

create table shadow_comparisons (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id),
    worker_id text not null,
    run_id text not null,
    task_type text,

    -- Baseline (call_llm) result
    baseline_output jsonb not null,

    -- Hermes result
    hermes_output jsonb,
    hermes_error text,

    -- Comparison metrics
    field_match_count integer,
    field_total integer,
    field_match_rate numeric(5,4),

    -- Performance
    baseline_latency_ms integer,
    hermes_latency_ms integer,
    hermes_iterations integer,

    created_at timestamptz not null default now()
);

alter table shadow_comparisons enable row level security;
alter table shadow_comparisons force row level security;
create policy shadow_comparisons_tenant on shadow_comparisons
    using (tenant_id = current_setting('app.current_tenant')::uuid);

create index idx_shadow_comparisons_worker_created
    on shadow_comparisons (worker_id, created_at desc);

comment on table shadow_comparisons is
    'Shadow mode comparison results between call_llm baseline and Hermes worker runs';
