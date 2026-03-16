create table if not exists public.customer_content (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  call_id text not null,
  consent_granted boolean not null default false,
  raw_transcript text not null,
  sanitized_transcript text not null,
  structured_content jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.customer_content enable row level security;
alter table public.customer_content force row level security;

create policy customer_content_isolation on public.customer_content
  using (tenant_id = public.current_tenant_id());
