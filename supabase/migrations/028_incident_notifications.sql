alter table public.tenant_configs
  add column if not exists incident_notification_channels jsonb not null default '["dashboard"]'::jsonb,
  add column if not exists incident_assignees jsonb not null default '{}'::jsonb,
  add column if not exists incident_reminder_minutes integer not null default 60;

alter table public.incidents
  add column if not exists last_reminded_at timestamptz,
  add column if not exists reminder_count integer not null default 0;
