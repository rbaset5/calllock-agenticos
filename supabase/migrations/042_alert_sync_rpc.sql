drop function if exists public.mutate_alert_and_sync_incident(uuid, jsonb, jsonb);

create or replace function public.mutate_alert_and_sync_incident(
  p_alert_id uuid,
  p_updates jsonb default '{}'::jsonb,
  p_incident_sync jsonb default '{}'::jsonb
)
returns setof public.alerts
language plpgsql
security definer
set search_path = public
as $$
declare
  v_alert public.alerts%rowtype;
  v_updates jsonb := coalesce(p_updates, '{}'::jsonb);
  v_status text;
begin
  select *
  into v_alert
  from public.alerts
  where id = p_alert_id
  for update;

  if not found then
    raise exception using message = format('CLLKAS_NOT_FOUND: Unknown alert: %s', p_alert_id);
  end if;

  if v_updates ? 'status' then
    v_status := lower(coalesce(v_updates ->> 'status', ''));
    if (v_alert.status = 'open' and v_status not in ('acknowledged', 'escalated', 'resolved'))
      or (v_alert.status = 'acknowledged' and v_status not in ('escalated', 'resolved'))
      or (v_alert.status = 'escalated' and v_status not in ('acknowledged', 'resolved'))
      or (v_alert.status = 'resolved')
    then
      raise exception using message = format('CLLKAS_INVALID: Invalid alert transition: %s -> %s', v_alert.status, v_status);
    end if;
  end if;

  update public.alerts
  set status = coalesce(v_updates ->> 'status', status),
      message = coalesce(v_updates ->> 'message', message),
      metrics = coalesce(v_updates -> 'metrics', metrics),
      resolution_notes = coalesce(v_updates ->> 'resolution_notes', resolution_notes),
      acknowledged_at = coalesce((v_updates ->> 'acknowledged_at')::timestamptz, acknowledged_at),
      acknowledged_by = coalesce(v_updates ->> 'acknowledged_by', acknowledged_by),
      escalated_at = coalesce((v_updates ->> 'escalated_at')::timestamptz, escalated_at),
      escalated_by = coalesce(v_updates ->> 'escalated_by', escalated_by),
      resolved_at = coalesce((v_updates ->> 'resolved_at')::timestamptz, resolved_at),
      resolved_by = coalesce(v_updates ->> 'resolved_by', resolved_by),
      last_observed_at = coalesce((v_updates ->> 'last_observed_at')::timestamptz, last_observed_at),
      occurrence_count = coalesce((v_updates ->> 'occurrence_count')::integer, occurrence_count)
  where id = p_alert_id
  returning * into v_alert;

  perform public.sync_incident_from_alert(
    p_incident_sync ->> 'incident_key',
    (p_incident_sync ->> 'tenant_id')::uuid,
    (p_incident_sync ->> 'alert_id')::uuid,
    p_incident_sync ->> 'alert_type',
    p_incident_sync ->> 'severity',
    p_incident_sync ->> 'alert_status',
    (p_incident_sync ->> 'alert_created_at')::timestamptz,
    (p_incident_sync ->> 'alert_last_observed_at')::timestamptz,
    (p_incident_sync ->> 'alert_resolved_at')::timestamptz,
    coalesce((p_incident_sync ->> 'alert_occurrence_count')::integer, 1),
    p_incident_sync ->> 'incident_domain',
    p_incident_sync ->> 'incident_category',
    p_incident_sync ->> 'remediation_category',
    p_incident_sync ->> 'incident_urgency',
    p_incident_sync ->> 'runbook_id',
    p_incident_sync ->> 'runbook_title',
    coalesce(p_incident_sync -> 'runbook_steps', '[]'::jsonb),
    coalesce(p_incident_sync -> 'completion_policy', '{"required_workflow_statuses":[]}'::jsonb),
    coalesce(p_incident_sync -> 'approval_policy', '{"required_workflow_statuses":[]}'::jsonb),
    coalesce(p_incident_sync -> 'initial_runbook_progress', '[]'::jsonb),
    coalesce(p_incident_sync -> 'initial_runbook_progress_summary', '{"total_steps":0,"completed_steps":0,"pending_steps":0}'::jsonb),
    coalesce(
      p_incident_sync -> 'initial_runbook_execution_plan',
      '{"next_runnable_steps":[],"blocked_steps":[],"completed_steps":[],"parallel_groups":{}}'::jsonb
    )
  );

  return next v_alert;
  return;
end;
$$;
