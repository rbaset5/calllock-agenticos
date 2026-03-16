drop function if exists public.sync_incident_from_alert(
  text, uuid, uuid, text, text, text, timestamptz, timestamptz, timestamptz, integer,
  text, text, text, text, text, text, jsonb, jsonb, jsonb, jsonb, jsonb, jsonb
);

create or replace function public.sync_incident_from_alert(
  p_incident_key text,
  p_tenant_id uuid,
  p_alert_id uuid,
  p_alert_type text,
  p_severity text,
  p_alert_status text,
  p_alert_created_at timestamptz,
  p_alert_last_observed_at timestamptz,
  p_alert_resolved_at timestamptz,
  p_alert_occurrence_count integer default 1,
  p_incident_domain text default 'general',
  p_incident_category text default null,
  p_remediation_category text default 'manual_review',
  p_incident_urgency text default null,
  p_runbook_id text default null,
  p_runbook_title text default null,
  p_runbook_steps jsonb default '[]'::jsonb,
  p_completion_policy jsonb default '{"required_workflow_statuses":[]}'::jsonb,
  p_approval_policy jsonb default '{"required_workflow_statuses":[]}'::jsonb,
  p_initial_runbook_progress jsonb default '[]'::jsonb,
  p_initial_runbook_progress_summary jsonb default '{"total_steps":0,"completed_steps":0,"pending_steps":0}'::jsonb,
  p_initial_runbook_execution_plan jsonb default '{"next_runnable_steps":[],"blocked_steps":[],"completed_steps":[],"parallel_groups":{}}'::jsonb
)
returns setof public.incidents
language plpgsql
security definer
set search_path = public
as $$
declare
  v_incident public.incidents%rowtype;
  v_exists boolean := false;
  v_status text;
  v_episode_count integer := 1;
  v_episode_history jsonb := '[]'::jsonb;
  v_started_at timestamptz;
  v_alert_ids jsonb := '[]'::jsonb;
  v_occurrence_count integer := greatest(coalesce(p_alert_occurrence_count, 1), 1);
  v_reset_runbook_progress boolean := false;
  v_runbook_changed boolean := false;
  v_runbook_progress jsonb;
  v_runbook_progress_summary jsonb;
  v_runbook_execution_plan jsonb;
begin
  if p_incident_key is null or btrim(p_incident_key) = '' then
    raise exception using message = 'CLLKIS_INVALID: incident_key is required';
  end if;
  if p_alert_type is null or btrim(p_alert_type) = '' then
    raise exception using message = 'CLLKIS_INVALID: alert_type is required';
  end if;

  v_status := case when lower(coalesce(p_alert_status, 'open')) = 'resolved' then 'resolved' else 'open' end;

  select *
  into v_incident
  from public.incidents
  where incident_key = p_incident_key
  for update;

  v_exists := found;

  if v_exists then
    v_episode_count := greatest(coalesce(v_incident.episode_count, 1), 1);
    v_episode_history := coalesce(v_incident.episode_history, '[]'::jsonb);
    if jsonb_typeof(v_episode_history) <> 'array' then
      v_episode_history := '[]'::jsonb;
    end if;
    v_started_at := coalesce(v_incident.started_at, p_alert_created_at, p_alert_last_observed_at, now());

    if v_incident.status = 'resolved' and v_status = 'open' then
      v_episode_history := v_episode_history || jsonb_build_array(
        jsonb_build_object(
          'episode', greatest(coalesce(v_incident.current_episode, v_episode_count), 1),
          'started_at', v_incident.started_at,
          'resolved_at', v_incident.resolved_at,
          'last_seen_at', v_incident.last_seen_at,
          'occurrence_count', coalesce(v_incident.occurrence_count, 1)
        )
      );
      v_episode_count := v_episode_count + 1;
      v_started_at := coalesce(p_alert_created_at, p_alert_last_observed_at, v_started_at);
      v_reset_runbook_progress := true;
    end if;

    v_alert_ids := coalesce(v_incident.alert_ids, '[]'::jsonb);
    if jsonb_typeof(v_alert_ids) <> 'array' then
      v_alert_ids := '[]'::jsonb;
    end if;
    if p_alert_id is not null and not (v_alert_ids @> to_jsonb(array[p_alert_id::text])) then
      v_alert_ids := v_alert_ids || jsonb_build_array(p_alert_id::text);
    end if;

    v_occurrence_count := greatest(v_occurrence_count, coalesce(v_incident.occurrence_count, 0));
    v_runbook_changed := coalesce(v_incident.runbook_id, '') is distinct from coalesce(p_runbook_id, '')
      or coalesce(v_incident.runbook_steps, '[]'::jsonb) is distinct from coalesce(p_runbook_steps, '[]'::jsonb)
      or coalesce(v_incident.completion_policy, '{"required_workflow_statuses":[]}'::jsonb) is distinct from coalesce(p_completion_policy, '{"required_workflow_statuses":[]}'::jsonb)
      or coalesce(v_incident.approval_policy, '{"required_workflow_statuses":[]}'::jsonb) is distinct from coalesce(p_approval_policy, '{"required_workflow_statuses":[]}'::jsonb);

    if v_reset_runbook_progress or v_runbook_changed then
      v_runbook_progress := coalesce(p_initial_runbook_progress, '[]'::jsonb);
      v_runbook_progress_summary := coalesce(p_initial_runbook_progress_summary, '{"total_steps":0,"completed_steps":0,"pending_steps":0}'::jsonb);
      v_runbook_execution_plan := coalesce(
        p_initial_runbook_execution_plan,
        '{"next_runnable_steps":[],"blocked_steps":[],"completed_steps":[],"parallel_groups":{}}'::jsonb
      );
    else
      v_runbook_progress := coalesce(v_incident.runbook_progress, '[]'::jsonb);
      v_runbook_progress_summary := coalesce(v_incident.runbook_progress_summary, '{"total_steps":0,"completed_steps":0,"pending_steps":0}'::jsonb);
      v_runbook_execution_plan := coalesce(
        v_incident.runbook_execution_plan,
        '{"next_runnable_steps":[],"blocked_steps":[],"completed_steps":[],"parallel_groups":{}}'::jsonb
      );
    end if;

    update public.incidents
    set tenant_id = p_tenant_id,
        alert_type = p_alert_type,
        severity = coalesce(p_severity, v_incident.severity),
        incident_domain = coalesce(p_incident_domain, v_incident.incident_domain),
        incident_category = coalesce(p_incident_category, p_alert_type, v_incident.incident_category),
        remediation_category = coalesce(p_remediation_category, v_incident.remediation_category),
        incident_urgency = coalesce(p_incident_urgency, p_severity, v_incident.incident_urgency),
        runbook_id = p_runbook_id,
        runbook_title = p_runbook_title,
        runbook_steps = coalesce(p_runbook_steps, '[]'::jsonb),
        runbook_progress = v_runbook_progress,
        runbook_progress_summary = v_runbook_progress_summary,
        runbook_execution_plan = v_runbook_execution_plan,
        completion_policy = coalesce(p_completion_policy, '{"required_workflow_statuses":[]}'::jsonb),
        approval_policy = coalesce(p_approval_policy, '{"required_workflow_statuses":[]}'::jsonb),
        status = v_status,
        started_at = v_started_at,
        last_seen_at = coalesce(p_alert_last_observed_at, p_alert_resolved_at, p_alert_created_at, v_incident.last_seen_at),
        resolved_at = case when v_status = 'resolved' then p_alert_resolved_at else null end,
        current_episode = v_episode_count,
        episode_count = v_episode_count,
        episode_history = v_episode_history,
        current_alert_id = p_alert_id,
        last_alert_status = coalesce(p_alert_status, 'open'),
        alert_ids = v_alert_ids,
        occurrence_count = v_occurrence_count,
        incident_revision = coalesce(v_incident.incident_revision, 1) + 1
    where id = v_incident.id
    returning * into v_incident;

    return next v_incident;
    return;
  end if;

  if p_alert_id is not null then
    v_alert_ids := jsonb_build_array(p_alert_id::text);
  end if;

  insert into public.incidents (
    tenant_id,
    incident_key,
    alert_type,
    severity,
    incident_domain,
    incident_category,
    remediation_category,
    incident_urgency,
    runbook_id,
    runbook_title,
    runbook_steps,
    runbook_progress,
    runbook_progress_summary,
    runbook_execution_plan,
    completion_policy,
    approval_policy,
    status,
    workflow_status,
    assigned_to,
    operator_notes,
    last_reviewed_at,
    last_reviewed_by,
    last_reminded_at,
    reminder_count,
    assignment_history,
    last_assignment_reason,
    started_at,
    last_seen_at,
    resolved_at,
    current_episode,
    episode_count,
    episode_history,
    current_alert_id,
    last_alert_status,
    alert_ids,
    occurrence_count,
    incident_revision
  )
  values (
    p_tenant_id,
    p_incident_key,
    p_alert_type,
    coalesce(p_severity, 'medium'),
    coalesce(p_incident_domain, 'general'),
    coalesce(p_incident_category, p_alert_type),
    coalesce(p_remediation_category, 'manual_review'),
    coalesce(p_incident_urgency, p_severity, 'medium'),
    p_runbook_id,
    p_runbook_title,
    coalesce(p_runbook_steps, '[]'::jsonb),
    coalesce(p_initial_runbook_progress, '[]'::jsonb),
    coalesce(p_initial_runbook_progress_summary, '{"total_steps":0,"completed_steps":0,"pending_steps":0}'::jsonb),
    coalesce(p_initial_runbook_execution_plan, '{"next_runnable_steps":[],"blocked_steps":[],"completed_steps":[],"parallel_groups":{}}'::jsonb),
    coalesce(p_completion_policy, '{"required_workflow_statuses":[]}'::jsonb),
    coalesce(p_approval_policy, '{"required_workflow_statuses":[]}'::jsonb),
    v_status,
    'new',
    null,
    '',
    null,
    null,
    null,
    0,
    '[]'::jsonb,
    null,
    coalesce(p_alert_created_at, p_alert_last_observed_at, now()),
    coalesce(p_alert_last_observed_at, p_alert_resolved_at, p_alert_created_at, now()),
    case when v_status = 'resolved' then p_alert_resolved_at else null end,
    1,
    1,
    '[]'::jsonb,
    p_alert_id,
    coalesce(p_alert_status, 'open'),
    v_alert_ids,
    v_occurrence_count,
    1
  )
  returning * into v_incident;

  return next v_incident;
  return;
end;
$$;
