alter table public.tenant_configs
  add column if not exists incident_skill_requirements jsonb not null default '{}'::jsonb;
