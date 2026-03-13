create table if not exists public.incidents (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references public.tenants(id) on delete cascade,
  incident_key text not null unique,
  alert_type text not null,
  severity text not null,
  status text not null default 'open',
  started_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  resolved_at timestamptz,
  current_alert_id uuid references public.alerts(id) on delete set null,
  last_alert_status text not null default 'open',
  alert_ids jsonb not null default '[]'::jsonb,
  occurrence_count integer not null default 1
);

alter table public.incidents enable row level security;
alter table public.incidents force row level security;

create policy incidents_isolation on public.incidents
  using (tenant_id is null or tenant_id = public.current_tenant_id());
