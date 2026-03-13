create table if not exists public.kill_switches (
  id uuid primary key default gen_random_uuid(),
  scope text not null check (scope in ('global', 'worker', 'tenant')),
  scope_id text,
  active boolean not null default true,
  reason text not null,
  created_by text not null,
  created_at timestamptz not null default now()
);
