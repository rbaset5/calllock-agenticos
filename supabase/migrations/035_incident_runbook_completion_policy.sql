alter table public.incidents
  add column if not exists completion_policy jsonb not null default '{"required_workflow_statuses":[]}'::jsonb;
