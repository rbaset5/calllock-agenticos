-- 053_guardian_overrides.sql
-- Founder override audit trail.
-- When the founder overrides eng-product-qa's PR block,
-- the override is logged here for learning and governance.

create table public.guardian_overrides (
  id uuid primary key default gen_random_uuid(),
  pr_number integer not null,
  pr_url text not null,
  override_by text not null,
  override_reason text,
  original_block_reason text not null,
  agent_id text not null,
  created_at timestamptz not null default now(),
  tenant_id uuid not null references public.tenants(id) on delete cascade
);

alter table public.guardian_overrides enable row level security;
alter table public.guardian_overrides force row level security;

create policy tenant_isolation on public.guardian_overrides
  using (tenant_id = public.current_tenant_id());

create index idx_guardian_overrides_tenant
  on public.guardian_overrides (tenant_id);
