alter table public.incidents
  add column if not exists runbook_progress jsonb not null default '[]'::jsonb,
  add column if not exists runbook_progress_summary jsonb not null default '{"total_steps":0,"completed_steps":0,"pending_steps":0}'::jsonb;
