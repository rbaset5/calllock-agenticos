drop function if exists public.mutate_incident_reminder(uuid, text, integer, timestamptz, text, text, jsonb, integer);

create or replace function public.mutate_incident_reminder(
  p_incident_id uuid,
  p_actor_id text,
  p_reminder_count integer,
  p_last_reminded_at timestamptz,
  p_assigned_to text default null,
  p_last_assignment_reason text default null,
  p_assignment_history_entry jsonb default null,
  p_expected_revision integer default null
)
returns setof public.incidents
language plpgsql
security definer
set search_path = public
as $$
declare
  v_incident public.incidents%rowtype;
  v_assignment_history jsonb;
begin
  if p_actor_id is null or btrim(p_actor_id) = '' then
    raise exception using message = 'CLLKRM_INVALID: actor_id is required';
  end if;
  if p_reminder_count < 0 then
    raise exception using message = 'CLLKRM_INVALID: reminder_count must be >= 0';
  end if;

  select *
  into v_incident
  from public.incidents
  where id = p_incident_id
  for update;

  if not found then
    raise exception using message = format('CLLKRM_NOT_FOUND: Unknown incident: %s', p_incident_id);
  end if;

  if p_expected_revision is not null and v_incident.incident_revision <> p_expected_revision then
    raise exception using message = format(
      'CLLKRM_CONFLICT: expected %s, found %s',
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
  set last_reminded_at = p_last_reminded_at,
      reminder_count = p_reminder_count,
      assigned_to = coalesce(p_assigned_to, assigned_to),
      last_assignment_reason = coalesce(p_last_assignment_reason, last_assignment_reason),
      assignment_history = v_assignment_history,
      incident_revision = v_incident.incident_revision + 1
  where id = p_incident_id
  returning * into v_incident;

  return next v_incident;
  return;
end;
$$;
