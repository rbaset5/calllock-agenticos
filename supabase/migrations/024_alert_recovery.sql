alter table public.tenant_configs
  add column if not exists alert_recovery_cooldown_minutes integer not null default 15;
