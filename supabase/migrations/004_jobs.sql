create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  origin_worker_id text not null,
  origin_run_id text not null,
  job_type text not null,
  status text not null default 'queued',
  supersedes_job_id uuid references public.jobs(id),
  source_call_id text,
  idempotency_key text not null unique,
  payload jsonb not null default '{}'::jsonb,
  result jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
