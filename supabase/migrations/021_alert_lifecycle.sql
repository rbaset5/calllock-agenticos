alter table public.alerts
  add column if not exists status text not null default 'open',
  add column if not exists acknowledged_at timestamptz,
  add column if not exists acknowledged_by text,
  add column if not exists escalated_at timestamptz,
  add column if not exists escalated_by text,
  add column if not exists resolved_at timestamptz,
  add column if not exists resolved_by text,
  add column if not exists resolution_notes text not null default '';

alter table public.alerts
  drop constraint if exists alerts_status_check;

alter table public.alerts
  add constraint alerts_status_check
  check (status in ('open', 'acknowledged', 'escalated', 'resolved'));
