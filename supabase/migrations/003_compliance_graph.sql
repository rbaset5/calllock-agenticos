create table if not exists public.compliance_rules (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references public.tenants(id) on delete cascade,
  scope text not null,
  rule_type text not null,
  target text not null,
  effect text not null check (effect in ('allow', 'deny', 'escalate')),
  reason text not null,
  conflicts_with text[] not null default '{}',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists compliance_rules_scope_idx on public.compliance_rules(scope);
create index if not exists compliance_rules_rule_type_idx on public.compliance_rules(rule_type);
create index if not exists compliance_rules_conflicts_with_gin on public.compliance_rules using gin(conflicts_with);
