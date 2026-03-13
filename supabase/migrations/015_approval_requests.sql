create table if not exists public.approval_requests (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references public.tenants(id) on delete cascade,
  run_id text,
  worker_id text,
  status text not null check (status in ('pending', 'approved', 'rejected', 'cancelled')),
  reason text not null,
  requested_by text not null,
  request_type text not null,
  payload jsonb not null default '{}'::jsonb,
  resolved_by text,
  resolution_notes text,
  created_at timestamptz not null default now()
);

alter table public.approval_requests enable row level security;
alter table public.approval_requests force row level security;

create policy approval_requests_isolation on public.approval_requests
  using (tenant_id is null or tenant_id = public.current_tenant_id());
