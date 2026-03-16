alter table public.incidents
  add column if not exists workflow_status text not null default 'new',
  add column if not exists assigned_to text,
  add column if not exists operator_notes text not null default '',
  add column if not exists last_reviewed_at timestamptz,
  add column if not exists last_reviewed_by text;

alter table public.incidents
  drop constraint if exists incidents_workflow_status_check;

alter table public.incidents
  add constraint incidents_workflow_status_check
  check (workflow_status in ('new', 'acknowledged', 'investigating', 'closed'));
