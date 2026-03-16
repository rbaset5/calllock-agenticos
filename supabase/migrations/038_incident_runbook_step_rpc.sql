create or replace function public.incident_runbook_apply_dependency_state(p_progress jsonb)
returns jsonb
language plpgsql
immutable
as $$
declare
  v_progress jsonb := coalesce(p_progress, '[]'::jsonb);
  v_item jsonb;
  v_dep text;
  v_dep_index integer;
  v_blocked_by jsonb;
  v_updated jsonb := '[]'::jsonb;
begin
  if jsonb_typeof(v_progress) <> 'array' then
    return '[]'::jsonb;
  end if;

  for v_item in select value from jsonb_array_elements(v_progress)
  loop
    v_blocked_by := '[]'::jsonb;
    for v_dep in select value from jsonb_array_elements_text(coalesce(v_item -> 'depends_on', '[]'::jsonb))
    loop
      v_dep_index := nullif(v_dep, '')::integer;
      if v_dep_index is null then
        continue;
      end if;
      if coalesce(v_progress -> (v_dep_index - 1) ->> 'status', 'pending') <> 'completed' then
        v_blocked_by := v_blocked_by || to_jsonb(v_dep_index);
      end if;
    end loop;
    v_item := jsonb_set(v_item, '{blocked_by}', v_blocked_by, true);
    v_item := jsonb_set(v_item, '{is_blocked}', to_jsonb(jsonb_array_length(v_blocked_by) > 0), true);
    v_updated := v_updated || jsonb_build_array(v_item);
  end loop;

  return v_updated;
end;
$$;


create or replace function public.incident_runbook_progress_summary(p_progress jsonb)
returns jsonb
language plpgsql
immutable
as $$
declare
  v_progress jsonb := coalesce(p_progress, '[]'::jsonb);
  v_item jsonb;
  v_total integer := 0;
  v_completed integer := 0;
  v_required integer := 0;
  v_required_completed integer := 0;
  v_optional integer := 0;
  v_optional_pending integer := 0;
  v_blocked integer := 0;
  v_required_flag boolean;
begin
  if jsonb_typeof(v_progress) <> 'array' then
    return jsonb_build_object(
      'total_steps', 0,
      'completed_steps', 0,
      'pending_steps', 0,
      'required_steps', 0,
      'required_completed_steps', 0,
      'required_pending_steps', 0,
      'optional_steps', 0,
      'optional_pending_steps', 0,
      'blocked_steps', 0
    );
  end if;

  for v_item in select value from jsonb_array_elements(v_progress)
  loop
    v_total := v_total + 1;
    v_required_flag := coalesce((v_item ->> 'required')::boolean, true);
    if v_required_flag then
      v_required := v_required + 1;
    else
      v_optional := v_optional + 1;
    end if;
    if v_item ->> 'status' = 'completed' then
      v_completed := v_completed + 1;
      if v_required_flag then
        v_required_completed := v_required_completed + 1;
      end if;
    elsif not v_required_flag then
      v_optional_pending := v_optional_pending + 1;
    end if;
    if coalesce((v_item ->> 'is_blocked')::boolean, false) then
      v_blocked := v_blocked + 1;
    end if;
  end loop;

  return jsonb_build_object(
    'total_steps', v_total,
    'completed_steps', v_completed,
    'pending_steps', greatest(v_total - v_completed, 0),
    'required_steps', v_required,
    'required_completed_steps', v_required_completed,
    'required_pending_steps', greatest(v_required - v_required_completed, 0),
    'optional_steps', v_optional,
    'optional_pending_steps', v_optional_pending,
    'blocked_steps', v_blocked
  );
end;
$$;


create or replace function public.incident_runbook_execution_plan(p_progress jsonb)
returns jsonb
language plpgsql
immutable
as $$
declare
  v_progress jsonb := coalesce(p_progress, '[]'::jsonb);
  v_item jsonb;
  v_dep text;
  v_dep_index integer;
  v_waiting_on_titles jsonb;
  v_step_view jsonb;
  v_next_runnable jsonb := '[]'::jsonb;
  v_blocked jsonb := '[]'::jsonb;
  v_completed jsonb := '[]'::jsonb;
  v_parallel_groups jsonb := '{}'::jsonb;
  v_parallel_group text;
begin
  if jsonb_typeof(v_progress) <> 'array' then
    return jsonb_build_object(
      'next_runnable_steps', '[]'::jsonb,
      'blocked_steps', '[]'::jsonb,
      'completed_steps', '[]'::jsonb,
      'parallel_groups', '{}'::jsonb
    );
  end if;

  for v_item in select value from jsonb_array_elements(v_progress)
  loop
    v_step_view := jsonb_build_object(
      'step_index', (v_item ->> 'step_index')::integer,
      'title', v_item ->> 'title',
      'required', coalesce((v_item ->> 'required')::boolean, true),
      'parallel_group', v_item ->> 'parallel_group',
      'assigned_to', v_item ->> 'assigned_to',
      'claimed_by', v_item ->> 'claimed_by',
      'claim_expires_at', v_item ->> 'claim_expires_at'
    );

    if v_item ->> 'status' = 'completed' then
      v_completed := v_completed || jsonb_build_array(v_step_view);
      continue;
    end if;

    if coalesce((v_item ->> 'is_blocked')::boolean, false) then
      v_waiting_on_titles := '[]'::jsonb;
      for v_dep in select value from jsonb_array_elements_text(coalesce(v_item -> 'blocked_by', '[]'::jsonb))
      loop
        v_dep_index := nullif(v_dep, '')::integer;
        if v_dep_index is null then
          continue;
        end if;
        if coalesce(v_progress -> (v_dep_index - 1) -> 'title', 'null'::jsonb) <> 'null'::jsonb then
          v_waiting_on_titles := v_waiting_on_titles || jsonb_build_array(v_progress -> (v_dep_index - 1) -> 'title');
        end if;
      end loop;
      v_blocked := v_blocked || jsonb_build_array(
        v_step_view || jsonb_build_object(
          'waiting_on_indexes', coalesce(v_item -> 'blocked_by', '[]'::jsonb),
          'waiting_on_titles', v_waiting_on_titles
        )
      );
      continue;
    end if;

    v_next_runnable := v_next_runnable || jsonb_build_array(v_step_view);
    v_parallel_group := nullif(v_item ->> 'parallel_group', '');
    if v_parallel_group is not null then
      v_parallel_groups := jsonb_set(
        v_parallel_groups,
        array[v_parallel_group],
        coalesce(v_parallel_groups -> v_parallel_group, '[]'::jsonb) || jsonb_build_array(v_step_view),
        true
      );
    end if;
  end loop;

  return jsonb_build_object(
    'next_runnable_steps', v_next_runnable,
    'blocked_steps', v_blocked,
    'completed_steps', v_completed,
    'parallel_groups', v_parallel_groups
  );
end;
$$;


drop function if exists public.mutate_incident_runbook_step(uuid, integer, text, text, text, text, text, text, integer, integer, integer, timestamptz);

create or replace function public.mutate_incident_runbook_step(
  p_incident_id uuid,
  p_step_index integer,
  p_actor_id text,
  p_operation text,
  p_status text default null,
  p_action text default null,
  p_assigned_to text default null,
  p_note text default '',
  p_claim_ttl_seconds integer default 600,
  p_expected_revision integer default null,
  p_expected_step_revision integer default null,
  p_now timestamptz default null
)
returns setof public.incidents
language plpgsql
security definer
set search_path = public
as $$
declare
  v_incident public.incidents%rowtype;
  v_progress jsonb;
  v_target jsonb;
  v_updated_target jsonb;
  v_now timestamptz := coalesce(p_now, now());
  v_step_revision integer;
  v_normalized_status text;
  v_normalized_action text;
  v_current_claimer text;
  v_claim_expires_at timestamptz;
  v_active_claim boolean;
begin
  if p_step_index < 1 then
    raise exception using message = 'CLLKRB_INDEX: step_index must be >= 1';
  end if;
  if p_actor_id is null or btrim(p_actor_id) = '' then
    raise exception using message = 'CLLKRB_INVALID: actor_id is required';
  end if;

  select *
  into v_incident
  from public.incidents
  where id = p_incident_id
  for update;

  if not found then
    raise exception using message = format('CLLKRB_NOT_FOUND: Unknown incident: %s', p_incident_id);
  end if;

  if p_expected_revision is not null and v_incident.incident_revision <> p_expected_revision then
    raise exception using message = format(
      'CLLKRB_INCIDENT_CONFLICT: expected %s, found %s',
      p_expected_revision,
      v_incident.incident_revision
    );
  end if;

  v_progress := coalesce(v_incident.runbook_progress, '[]'::jsonb);
  if jsonb_typeof(v_progress) <> 'array' or jsonb_array_length(v_progress) = 0 then
    raise exception using message = 'CLLKRB_STATE: Incident does not have a bound runbook';
  end if;
  if p_step_index > jsonb_array_length(v_progress) then
    raise exception using message = 'CLLKRB_INDEX: step_index is out of range';
  end if;

  v_target := v_progress -> (p_step_index - 1);
  v_step_revision := coalesce((v_target ->> 'step_revision')::integer, 1);
  if p_expected_step_revision is not null and v_step_revision <> p_expected_step_revision then
    raise exception using message = format(
      'CLLKRB_STEP_CONFLICT: expected %s, found %s',
      p_expected_step_revision,
      v_step_revision
    );
  end if;

  if p_operation = 'progress' then
    v_normalized_status := lower(coalesce(p_status, ''));
    if v_normalized_status not in ('pending', 'completed') then
      raise exception using message = 'CLLKRB_INVALID: status must be one of: pending, completed';
    end if;
    if v_normalized_status = 'completed' and coalesce((v_target ->> 'is_blocked')::boolean, false) then
      raise exception using message = format(
        'CLLKRB_STATE: step %s is blocked by dependencies: %s',
        p_step_index,
        coalesce(v_target -> 'blocked_by', '[]'::jsonb)::text
      );
    end if;

    v_updated_target := jsonb_set(v_target, '{step_revision}', to_jsonb(v_step_revision + 1), true);
    v_updated_target := jsonb_set(v_updated_target, '{status}', to_jsonb(v_normalized_status), true);
    if v_normalized_status = 'completed' then
      v_updated_target := jsonb_set(v_updated_target, '{claimed_by}', 'null'::jsonb, true);
      v_updated_target := jsonb_set(v_updated_target, '{claimed_at}', 'null'::jsonb, true);
      v_updated_target := jsonb_set(v_updated_target, '{claim_expires_at}', 'null'::jsonb, true);
      v_updated_target := jsonb_set(v_updated_target, '{completed_at}', to_jsonb(v_now), true);
      v_updated_target := jsonb_set(v_updated_target, '{completed_by}', to_jsonb(p_actor_id), true);
    else
      v_updated_target := jsonb_set(v_updated_target, '{completed_at}', 'null'::jsonb, true);
      v_updated_target := jsonb_set(v_updated_target, '{completed_by}', 'null'::jsonb, true);
    end if;
    v_updated_target := jsonb_set(v_updated_target, '{notes}', to_jsonb(coalesce(p_note, '')), true);
  elsif p_operation = 'assignment' then
    v_normalized_action := lower(coalesce(p_action, ''));
    if v_normalized_action not in ('assign', 'claim', 'heartbeat', 'release') then
      raise exception using message = 'CLLKRB_INVALID: action must be one of: assign, claim, heartbeat, release';
    end if;
    if p_claim_ttl_seconds < 1 then
      raise exception using message = 'CLLKRB_INVALID: claim_ttl_seconds must be >= 1';
    end if;

    v_current_claimer := nullif(v_target ->> 'claimed_by', '');
    v_claim_expires_at := nullif(v_target ->> 'claim_expires_at', '')::timestamptz;
    v_active_claim := v_current_claimer is not null and (v_claim_expires_at is null or v_claim_expires_at > v_now);
    v_updated_target := jsonb_set(v_target, '{step_revision}', to_jsonb(v_step_revision + 1), true);

    if v_normalized_action = 'assign' then
      v_updated_target := jsonb_set(v_updated_target, '{assigned_to}', to_jsonb(p_assigned_to), true);
      if p_assigned_to is null then
        v_updated_target := jsonb_set(v_updated_target, '{claimed_by}', 'null'::jsonb, true);
        v_updated_target := jsonb_set(v_updated_target, '{claimed_at}', 'null'::jsonb, true);
        v_updated_target := jsonb_set(v_updated_target, '{claim_expires_at}', 'null'::jsonb, true);
      end if;
    elsif v_normalized_action = 'claim' then
      if v_target ->> 'status' = 'completed' then
        raise exception using message = 'CLLKRB_STATE: cannot claim a completed step';
      end if;
      if v_active_claim and v_current_claimer <> p_actor_id then
        raise exception using message = format('CLLKRB_STATE: step %s is already claimed by %s', p_step_index, v_current_claimer);
      end if;
      v_updated_target := jsonb_set(v_updated_target, '{claimed_by}', to_jsonb(p_actor_id), true);
      v_updated_target := jsonb_set(v_updated_target, '{claimed_at}', to_jsonb(v_now), true);
      v_updated_target := jsonb_set(v_updated_target, '{claim_expires_at}', to_jsonb(v_now + make_interval(secs => p_claim_ttl_seconds)), true);
      v_updated_target := jsonb_set(
        v_updated_target,
        '{assigned_to}',
        to_jsonb(coalesce(p_assigned_to, nullif(v_target ->> 'assigned_to', ''), p_actor_id)),
        true
      );
    elsif v_normalized_action = 'heartbeat' then
      if not v_active_claim or v_current_claimer <> p_actor_id then
        raise exception using message = format('CLLKRB_STATE: step %s is not actively claimed by %s', p_step_index, p_actor_id);
      end if;
      v_updated_target := jsonb_set(v_updated_target, '{claim_expires_at}', to_jsonb(v_now + make_interval(secs => p_claim_ttl_seconds)), true);
    else
      if v_active_claim and v_current_claimer <> p_actor_id then
        raise exception using message = format('CLLKRB_STATE: step %s is actively claimed by %s', p_step_index, v_current_claimer);
      end if;
      v_updated_target := jsonb_set(v_updated_target, '{claimed_by}', 'null'::jsonb, true);
      v_updated_target := jsonb_set(v_updated_target, '{claimed_at}', 'null'::jsonb, true);
      v_updated_target := jsonb_set(v_updated_target, '{claim_expires_at}', 'null'::jsonb, true);
      if p_assigned_to is not null then
        v_updated_target := jsonb_set(v_updated_target, '{assigned_to}', to_jsonb(p_assigned_to), true);
      end if;
    end if;
  else
    raise exception using message = 'CLLKRB_INVALID: operation must be one of: progress, assignment';
  end if;

  v_progress := jsonb_set(v_progress, array[(p_step_index - 1)::text], v_updated_target, false);
  v_progress := public.incident_runbook_apply_dependency_state(v_progress);

  update public.incidents
  set runbook_progress = v_progress,
      runbook_progress_summary = public.incident_runbook_progress_summary(v_progress),
      runbook_execution_plan = public.incident_runbook_execution_plan(v_progress),
      last_reviewed_at = v_now,
      last_reviewed_by = p_actor_id,
      incident_revision = v_incident.incident_revision + 1
  where id = p_incident_id
  returning * into v_incident;

  return next v_incident;
  return;
end;
$$;
