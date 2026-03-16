create table if not exists public.eval_runs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references public.tenants(id) on delete cascade,
  level text not null check (level in ('core', 'industry', 'tenant')),
  target text,
  overall_score numeric not null,
  dataset_results jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.eval_runs enable row level security;
alter table public.eval_runs force row level security;

create policy eval_runs_isolation on public.eval_runs
  using (tenant_id is null or tenant_id = public.current_tenant_id());
