create table if not exists public.alerts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references public.tenants(id) on delete cascade,
  alert_type text not null,
  severity text not null,
  message text not null,
  metrics jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.alerts enable row level security;
alter table public.alerts force row level security;

create policy alerts_isolation on public.alerts
  using (tenant_id is null or tenant_id = public.current_tenant_id());
