alter table public.tenant_configs
  add column if not exists incident_oncall_rotation jsonb not null default '[]'::jsonb,
  add column if not exists incident_rotation_interval_hours integer not null default 24;
