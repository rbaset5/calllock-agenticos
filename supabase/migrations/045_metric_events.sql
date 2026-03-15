-- metric_events: operational metrics for alert threshold derivation
create table public.metric_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references public.tenants(id),
  run_id uuid,
  job_id uuid,
  worker_id text,
  category text not null,
  event_name text not null,
  dimensions jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index idx_metric_events_category_tenant_time
  on public.metric_events (category, tenant_id, created_at);

-- RLS
alter table public.metric_events enable row level security;
alter table public.metric_events force row level security;

-- Policy 1: tenant-scoped reads
create policy metric_events_tenant_isolation on public.metric_events
  using (tenant_id = public.current_tenant_id());

-- Policy 2: admin/platform reads (all rows including null tenant_id)
create policy metric_events_admin_access on public.metric_events
  using (current_setting('app.is_admin', true) = 'true');

-- Admin context helper (mirrors set_tenant_context from 005)
create or replace function public.set_admin_context()
returns void
language sql
as $$
  select set_config('app.is_admin', 'true', true);
$$;

-- Metric snapshot RPC: sets context and queries in one transaction
-- so that transaction-local set_config values are live for the query.
create or replace function public.get_metric_snapshot(
  p_category text,
  p_tenant_id uuid default null,
  p_cutoff timestamptz default now() - interval '1 hour',
  p_group_by text default null
)
returns jsonb
language plpgsql
as $$
declare
  result jsonb;
begin
  -- Set context in same transaction for RLS
  if p_tenant_id is not null then
    perform public.set_tenant_context(p_tenant_id);
  else
    perform public.set_admin_context();
  end if;

  -- Build aggregated result server-side
  select jsonb_build_object(
    'total_count', count(*),
    'oldest_event', min(created_at),
    'newest_event', max(created_at),
    'groups', case
      when p_group_by = 'event_name' then
        coalesce((select jsonb_agg(g) from (
          select jsonb_build_object('key', event_name, 'count', count(*)) as g
          from public.metric_events
          where category = p_category
            and created_at >= p_cutoff
            and (p_tenant_id is null or tenant_id = p_tenant_id)
          group by event_name order by count(*) desc
        ) sub), '[]'::jsonb)
      when p_group_by = 'worker_id' then
        coalesce((select jsonb_agg(g) from (
          select jsonb_build_object('key', coalesce(worker_id, 'unknown'), 'count', count(*)) as g
          from public.metric_events
          where category = p_category
            and created_at >= p_cutoff
            and (p_tenant_id is null or tenant_id = p_tenant_id)
          group by worker_id order by count(*) desc
        ) sub), '[]'::jsonb)
      when p_group_by = 'tenant_id' then
        coalesce((select jsonb_agg(g) from (
          select jsonb_build_object('key', coalesce(tenant_id::text, 'platform'), 'count', count(*)) as g
          from public.metric_events
          where category = p_category
            and created_at >= p_cutoff
            and (p_tenant_id is null or tenant_id = p_tenant_id)
          group by tenant_id order by count(*) desc
        ) sub), '[]'::jsonb)
      else '[]'::jsonb
    end
  ) into result
  from public.metric_events
  where category = p_category
    and created_at >= p_cutoff
    and (p_tenant_id is null or tenant_id = p_tenant_id);

  return result;
end;
$$;
