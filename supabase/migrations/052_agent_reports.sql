-- 052_agent_reports.sql
-- Agent health reports from Product Guardian agents.
-- Each agent writes a daily report; eng-product-qa reads them at 7am
-- for the cross-surface health check.

create table public.agent_reports (
  id uuid primary key default gen_random_uuid(),
  agent_id text not null,
  report_type text not null,
  report_date date not null,
  status text not null check (status in ('green', 'yellow', 'red')),
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  tenant_id uuid not null references public.tenants(id) on delete cascade
);

alter table public.agent_reports enable row level security;
alter table public.agent_reports force row level security;

create policy tenant_isolation on public.agent_reports
  using (tenant_id = public.current_tenant_id());

-- Lookup index: agent + date (used by eng-product-qa at 7am)
create index idx_agent_reports_lookup
  on public.agent_reports (agent_id, report_date);

-- Tenant index for RLS performance
create index idx_agent_reports_tenant
  on public.agent_reports (tenant_id);
