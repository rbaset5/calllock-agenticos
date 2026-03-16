alter table public.alerts
  add column if not exists occurrence_count integer not null default 1,
  add column if not exists last_observed_at timestamptz not null default now();

alter table public.tenant_configs
  add column if not exists alert_suppression_window_minutes integer not null default 60;
