alter table public.tenant_configs
  add column if not exists retention_policy jsonb not null default '{}'::jsonb;
