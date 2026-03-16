alter table public.tenant_configs
  add column if not exists incident_classification_rules jsonb not null default '[]'::jsonb;

alter table public.incidents
  add column if not exists incident_domain text not null default 'general',
  add column if not exists incident_category text not null default 'general',
  add column if not exists remediation_category text not null default 'manual_review',
  add column if not exists incident_urgency text not null default 'medium';
