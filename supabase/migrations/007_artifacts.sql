create table if not exists public.artifacts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  run_id text,
  created_by text not null,
  artifact_type text not null,
  source_job_id uuid references public.jobs(id) on delete set null,
  payload jsonb not null default '{}'::jsonb,
  lineage jsonb not null default '{}'::jsonb,
  lifecycle_state text not null default 'created' check (lifecycle_state in ('created', 'active', 'archived', 'deleted')),
  created_at timestamptz not null default now()
);

alter table public.artifacts enable row level security;
alter table public.artifacts force row level security;

create policy artifacts_isolation on public.artifacts
  using (tenant_id = public.current_tenant_id());
