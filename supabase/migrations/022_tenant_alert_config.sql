alter table public.tenant_configs
  add column if not exists alert_thresholds jsonb not null default '{}'::jsonb,
  add column if not exists alert_channels jsonb not null default '["dashboard"]'::jsonb,
  add column if not exists alert_webhook_url text,
  add column if not exists alert_escalation_policy jsonb not null default '{}'::jsonb;
