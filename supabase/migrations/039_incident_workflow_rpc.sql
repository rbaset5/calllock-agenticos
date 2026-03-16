drop function if exists public.mutate_incident_workflow(uuid, text, text, text, text, text, jsonb, timestamptz, integer);

create or replace function public.mutate_incident_workflow(
  p_incident_id uuid,
  p_workflow_status text,
  p_actor_id text,
  p_assigned_to text default null,
  p_operator_notes text default '',
  p_last_assignment_reason text default null,
  p_assignment_history_entry jsonb default null,
  p_now timestamptz default null,
  p_expected_revision integer default null
)
returns setof public.incidents
language plpgsql
security definer
set search_path = public
as $$
declare
  v_incident public.incidents%rowtype;
  v_now timestamptz := coalesce(p_now, now());
  v_assignment_history jsonb;
  v_workflow_status text := lower(coalesce(p_workflow_status, ''));
begin
  if p_actor_id is null or btrim(p_actor_id) = '' then
    raise exception using message = 'CLLKWF_INVALID: actor_id is required';
  end if;
  if v_workflow_status not in ('new', 'acknowledged', 'investigating', 'closed') then
    raise exception using message = 'CLLKWF_INVALID: workflow_status must be one of: new, acknowledged, investigating, closed';
  end if;

  select *
  into v_incident
  from public.incidents
  where id = p_incident_id
  for update;

  if not found then
    raise exception using message = format('CLLKWF_NOT_FOUND: Unknown incident: %s', p_incident_id);
  end if;

  if p_expected_revision is not null and v_incident.incident_revision <> p_expected_revision then
    raise exception using message = format(
      'CLLKWF_CONFLICT: expected %s, found %s',
      p_expected_revision,
      v_incident.incident_revision
    );
  end if;

  v_assignment_history := coalesce(v_incident.assignment_history, '[]'::jsonb);
  if jsonb_typeof(v_assignment_history) <> 'array' then
    v_assignment_history := '[]'::jsonb;
  end if;
  if p_assignment_history_entry is not null and jsonb_typeof(p_assignment_history_entry) = 'object' then
    v_assignment_history := v_assignment_history || jsonb_build_array(p_assignment_history_entry);
  end if;

  update public.incidents
  set workflow_status = v_workflow_status,
      assigned_to = p_assigned_to,
      operator_notes = coalesce(p_operator_notes, ''),
      last_reviewed_at = v_now,
      last_reviewed_by = p_actor_id,
      last_assignment_reason = p_last_assignment_reason,
      assignment_history = v_assignment_history,
      incident_revision = v_incident.incident_revision + 1
  where id = p_incident_id
  returning * into v_incident;

  return next v_incident;
  return;
end;
$$;
