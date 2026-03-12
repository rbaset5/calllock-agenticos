create table if not exists public.tenant_configs (
  tenant_id uuid primary key references public.tenants(id) on delete cascade,
  tone text not null default 'helpful',
  disclosures jsonb not null default '[]'::jsonb,
  pricing_rules jsonb not null default '{}'::jsonb,
  business_hours jsonb not null default '{}'::jsonb,
  promotions jsonb not null default '[]'::jsonb,
  allowed_tools jsonb not null default '[]'::jsonb,
  escalation_contacts jsonb not null default '[]'::jsonb,
  trace_namespace text,
  eval_namespace text,
  monthly_llm_budget_cents integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
