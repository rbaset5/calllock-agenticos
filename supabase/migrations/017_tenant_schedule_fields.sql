alter table public.tenant_configs
  add column if not exists timezone text not null default 'UTC';

alter table public.tenant_configs
  add column if not exists retention_local_hour integer not null default 3;

alter table public.tenant_configs
  add column if not exists tenant_eval_local_hour integer not null default 4;
