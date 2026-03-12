create or replace function public.resolve_compliance_conflicts()
returns table (
  target text,
  winning_effect text,
  reasons text[]
)
language sql
as $$
  with grouped as (
    select
      target,
      array_agg(effect order by effect) as effects,
      array_agg(reason order by reason) as reasons
    from public.compliance_rules
    group by target
  )
  select
    target,
    case
      when 'deny' = any(effects) then 'deny'
      when 'escalate' = any(effects) then 'escalate'
      when 'allow' = any(effects) then 'allow'
      else 'deny'
    end as winning_effect,
    reasons
  from grouped;
$$;
