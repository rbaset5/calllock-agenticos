create or replace function public.resolve_compliance_conflicts()
returns table (
  target text,
  conflict_key text,
  winning_effect text,
  blocked boolean,
  matched_rule_ids text[],
  reasons text[]
)
language sql
as $$
  with normalized as (
    select
      target,
      coalesce(metadata->>'conflict_key', metadata->>'disclosure_key', target) as conflict_key,
      effect,
      reason,
      id::text as rule_id
    from public.compliance_rules
  ),
  grouped as (
    select
      target,
      conflict_key,
      array_agg(effect order by effect) as effects,
      array_agg(reason order by reason) as reasons,
      array_agg(rule_id order by rule_id) as matched_rule_ids
    from normalized
    group by target, conflict_key
  )
  select
    target,
    conflict_key,
    case
      when array_length(array(select distinct unnest(effects)), 1) > 1 then 'escalate'
      when 'deny' = any(effects) then 'deny'
      when 'escalate' = any(effects) then 'escalate'
      when 'allow' = any(effects) then 'allow'
      else 'deny'
    end as winning_effect,
    case
      when array_length(array(select distinct unnest(effects)), 1) > 1 then true
      when 'deny' = any(effects) then true
      when 'escalate' = any(effects) then true
      else false
    end as blocked,
    matched_rule_ids,
    case
      when array_length(array(select distinct unnest(effects)), 1) > 1
        then array_prepend(
          format(
            'Conflict for %s/%s: matched effects %s; blocked pending review.',
            target,
            conflict_key,
            array_to_string(array(select distinct unnest(effects) order by 1), ', ')
          ),
          reasons
        )
      else reasons
    end as reasons
  from grouped;
$$;
