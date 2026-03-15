create or replace function public.set_tenant_context(tenant_uuid uuid)
returns void
language sql
as $$
  select set_config('app.current_tenant', tenant_uuid::text, true);
$$;

create or replace function public.current_tenant_id()
returns uuid
language sql
stable
as $$
  select nullif(current_setting('app.current_tenant', true), '')::uuid;
$$;

alter table public.tenants enable row level security;
alter table public.tenants force row level security;
alter table public.tenant_configs enable row level security;
alter table public.tenant_configs force row level security;
alter table public.jobs enable row level security;
alter table public.jobs force row level security;
alter table public.compliance_rules enable row level security;
alter table public.compliance_rules force row level security;

create policy tenants_isolation on public.tenants
  using (id = public.current_tenant_id());

create policy tenant_configs_isolation on public.tenant_configs
  using (tenant_id = public.current_tenant_id());

create policy jobs_isolation on public.jobs
  using (tenant_id = public.current_tenant_id());

create policy compliance_rules_isolation on public.compliance_rules
  using (tenant_id is null or tenant_id = public.current_tenant_id());
