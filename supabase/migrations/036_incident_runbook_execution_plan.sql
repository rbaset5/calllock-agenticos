alter table public.incidents
  add column if not exists runbook_execution_plan jsonb not null default '{"next_runnable_steps":[],"blocked_steps":[],"completed_steps":[],"parallel_groups":{}}'::jsonb;
