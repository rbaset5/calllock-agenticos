create table if not exists public.experiments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references public.tenants(id) on delete cascade,
  mutation_surface text not null,
  proposal text not null,
  baseline_score numeric not null,
  candidate_score numeric not null,
  outcome text not null check (outcome in ('keep', 'discard')),
  lock_id uuid,
  created_at timestamptz not null default now()
);

create table if not exists public.experiment_locks (
  id uuid primary key default gen_random_uuid(),
  mutation_surface text not null unique,
  ttl_seconds integer not null default 900,
  heartbeat_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
