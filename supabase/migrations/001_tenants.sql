create extension if not exists pgcrypto;

create table if not exists public.tenants (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  industry_pack_id text not null,
  contact_email text,
  service_area text,
  status text not null default 'active',
  created_at timestamptz not null default now()
);
