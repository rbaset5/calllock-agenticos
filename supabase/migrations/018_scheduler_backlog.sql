create table if not exists public.scheduler_backlog (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  job_type text not null check (job_type in ('retention', 'tenant_eval')),
  scheduled_for timestamptz not null,
  status text not null check (status in ('pending', 'completed', 'expired')),
  scheduled_timezone text not null,
  scheduled_hour integer not null,
  scheduled_minute integer not null,
  payload jsonb not null default '{}'::jsonb,
  last_seen_at timestamptz not null default now(),
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, job_type, scheduled_for)
);

create index if not exists scheduler_backlog_tenant_status_idx
  on public.scheduler_backlog (tenant_id, status, scheduled_for desc);

alter table public.scheduler_backlog enable row level security;
alter table public.scheduler_backlog force row level security;

create policy scheduler_backlog_isolation on public.scheduler_backlog
  using (tenant_id = public.current_tenant_id());
