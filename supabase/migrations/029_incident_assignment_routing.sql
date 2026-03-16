alter table public.tenant_configs
  add column if not exists incident_default_assignee text,
  add column if not exists incident_reassign_after_reminders integer not null default 2;

alter table public.incidents
  add column if not exists assignment_history jsonb not null default '[]'::jsonb,
  add column if not exists last_assignment_reason text;
