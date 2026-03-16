drop function if exists public.create_alert_and_sync_incident(jsonb, jsonb);

create or replace function public.create_alert_and_sync_incident(
  p_alert jsonb default '{}'::jsonb,
  p_incident_sync jsonb default '{}'::jsonb
)
returns setof public.alerts
language plpgsql
security definer
set search_path = public
as $$
declare
  v_alert public.alerts%rowtype;
begin
  if coalesce(p_alert ->> 'alert_type', '') = '' then
    raise exception using message = 'CLLKAS_INVALID: alert_type is required';
  end if;
  if coalesce(p_alert ->> 'severity', '') = '' then
    raise exception using message = 'CLLKAS_INVALID: severity is required';
  end if;
  if coalesce(p_alert ->> 'message', '') = '' then
    raise exception using message = 'CLLKAS_INVALID: message is required';
  end if;

  insert into public.alerts (
    id,
    tenant_id,
    alert_type,
    severity,
    status,
    message,
    metrics,
    acknowledged_at,
    acknowledged_by,
    escalated_at,
    escalated_by,
    resolved_at,
    resolved_by,
    resolution_notes,
    occurrence_count,
    last_observed_at,
    created_at
  )
  values (
    coalesce((p_alert ->> 'id')::uuid, gen_random_uuid()),
    (p_alert ->> 'tenant_id')::uuid,
    p_alert ->> 'alert_type',
    p_alert ->> 'severity',
    coalesce(p_alert ->> 'status', 'open'),
    p_alert ->> 'message',
    coalesce(p_alert -> 'metrics', '{}'::jsonb),
    (p_alert ->> 'acknowledged_at')::timestamptz,
    p_alert ->> 'acknowledged_by',
    (p_alert ->> 'escalated_at')::timestamptz,
    p_alert ->> 'escalated_by',
    (p_alert ->> 'resolved_at')::timestamptz,
    p_alert ->> 'resolved_by',
    coalesce(p_alert ->> 'resolution_notes', ''),
    coalesce((p_alert ->> 'occurrence_count')::integer, 1),
    coalesce((p_alert ->> 'last_observed_at')::timestamptz, (p_alert ->> 'created_at')::timestamptz, now()),
    coalesce((p_alert ->> 'created_at')::timestamptz, now())
  )
  returning * into v_alert;

  perform public.sync_incident_from_alert(
    p_incident_sync ->> 'incident_key',
    (p_incident_sync ->> 'tenant_id')::uuid,
    v_alert.id,
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
