create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references public.tenants(id) on delete cascade,
  action_type text not null,
  actor_id text not null,
  reason text not null,
  target_type text,
  target_id text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.audit_logs enable row level security;
alter table public.audit_logs force row level security;

create policy audit_logs_isolation on public.audit_logs
  using (tenant_id is null or tenant_id = public.current_tenant_id());
