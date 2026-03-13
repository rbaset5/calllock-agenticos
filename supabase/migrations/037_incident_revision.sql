alter table public.incidents
  add column if not exists incident_revision integer not null default 1;
