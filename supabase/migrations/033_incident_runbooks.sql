alter table public.tenant_configs
  add column if not exists incident_runbooks jsonb not null default '{}'::jsonb;

alter table public.incidents
  add column if not exists runbook_id text,
  add column if not exists runbook_title text,
  add column if not exists runbook_steps jsonb not null default '[]'::jsonb,
  add column if not exists approval_policy jsonb not null default '{"required_workflow_statuses":[]}'::jsonb;
