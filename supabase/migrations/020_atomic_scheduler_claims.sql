create or replace function public.claim_scheduler_backlog_entries(
  p_job_type text,
  p_claimed_before timestamptz,
  p_max_entries integer,
  p_claimer_id text,
  p_claim_ttl_seconds integer
)
returns setof public.scheduler_backlog
language sql
security definer
as $$
  with candidates as (
    select sb.id
    from public.scheduler_backlog sb
    where sb.job_type = p_job_type
      and sb.status = 'pending'
      and sb.scheduled_for <= p_claimed_before
    order by
      coalesce((sb.payload->>'lateness_minutes')::integer, 0) desc,
      (
        coalesce((sb.payload->>'active_job_count')::numeric, 0)
        / greatest(coalesce((sb.payload->>'max_active_jobs')::numeric, 1), 1)
      ) asc,
      sb.scheduled_minute asc,
      coalesce(sb.payload->>'tenant_slug', sb.tenant_id::text) asc
    limit greatest(p_max_entries, 0)
    for update skip locked
  ),
  claimed as (
    update public.scheduler_backlog sb
    set
      status = 'claimed',
      claimed_by = p_claimer_id,
      claimed_at = p_claimed_before,
      claim_expires_at = p_claimed_before + make_interval(secs => p_claim_ttl_seconds),
      updated_at = now()
    from candidates
    where sb.id = candidates.id
    returning sb.*
  )
  select * from claimed;
$$;
