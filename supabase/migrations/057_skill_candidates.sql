-- Skill candidate records from verification node.
-- Flagged when a worker run shows signals of reusable procedures.
-- Founder reviews and promotes or dismisses via CEO agent.

create table skill_candidates (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id),
    worker_id text not null,
    task_type text not null,
    run_id text not null,
    signals text[] not null,
    summary text,
    status text not null default 'pending'
        check (status in ('pending', 'promoted', 'dismissed')),
    promoted_by text,
    dismiss_reason text,
    created_at timestamptz not null default now(),
    reviewed_at timestamptz
);

alter table skill_candidates enable row level security;
alter table skill_candidates force row level security;
create policy skill_candidates_tenant on skill_candidates
    using (tenant_id = current_setting('app.current_tenant')::uuid);

create index idx_skill_candidates_status on skill_candidates (status, created_at desc);
create index idx_skill_candidates_worker on skill_candidates (worker_id, created_at desc);

comment on table skill_candidates is
    'Skill candidate records flagged by verification node for founder review';
