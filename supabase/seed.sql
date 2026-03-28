insert into public.tenants (id, slug, name, industry_pack_id, contact_email, service_area, status)
values
  ('00000000-0000-0000-0000-000000000001', 'tenant-alpha', 'Tenant Alpha HVAC', 'hvac', 'ops@alpha.example', 'Detroit Metro', 'active'),
  ('00000000-0000-0000-0000-000000000002', 'tenant-beta', 'Tenant Beta HVAC', 'hvac', 'ops@beta.example', 'Ann Arbor', 'active')
on conflict (id) do nothing;

insert into public.tenant_configs (
  tenant_id,
  tone,
  disclosures,
  allowed_tools,
  trace_namespace,
  eval_namespace,
  monthly_llm_budget_cents
)
values
  (
    '00000000-0000-0000-0000-000000000001',
    'helpful',
    '["Callback windows depend on dispatcher confirmation."]'::jsonb,
    '["read_knowledge", "notify_dispatch"]'::jsonb,
    'tenant-alpha',
    'tenant-alpha',
    50000
  ),
  (
    '00000000-0000-0000-0000-000000000002',
    'direct',
    '["Emergency callbacks are promised within 15 minutes."]'::jsonb,
    '["read_knowledge"]'::jsonb,
    'tenant-beta',
    'tenant-beta',
    40000
  )
on conflict (tenant_id) do nothing;

insert into public.compliance_rules (tenant_id, scope, rule_type, target, effect, reason, conflicts_with, metadata)
values
  (null, 'global', 'booking', 'book_appointment', 'allow', 'Booking allowed when tenant policy permits it.', '{}', '{"industry_pack_id":"hvac"}'::jsonb),
  (null, 'global', 'alerts', 'dispatch_emergency', 'allow', 'Emergency dispatch alerts are allowed for life-safety events.', '{}', '{"industry_pack_id":"hvac"}'::jsonb),
  (null, 'global', 'claims', 'marketing_claims', 'deny', 'Do not claim guaranteed savings or guaranteed same-day repair.', '{}', '{"forbidden_claims":["guaranteed savings","guaranteed same-day repair"]}'::jsonb);

-- Remove realistic seed rows so this script is idempotent.
-- callback_touches rows cascade via FK on (tenant_id, call_id).
delete from public.call_records
where tenant_id in (
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000002'
)
and (call_id like 'seed-call-%' or call_id like 'demo-call-%');

-- ── Realistic CallLock App seed (tenant-alpha) ───────────────────────────
-- Purpose: day-to-day app realism, not deterministic CI fixtures.
-- Scenario matrix:
--   New Leads: 8
--   Follow-ups: 6
--   AI Handled: 6
-- Notes:
--   - Uses one clock anchor (seed_now) so relative urgency stays coherent.
--   - call_id namespace is demo-call-*.
--   - Includes recording URLs + pending extraction samples.
with seed_clock as (
  select now() as seed_now
)
insert into public.call_records (
  id, tenant_id, call_id, retell_call_id, phone_number,
  transcript, extracted_fields, extraction_status,
  urgency_tier, end_call_reason, callback_scheduled,
  callback_outcome, callback_outcome_at,
  caller_type, primary_intent, revenue_tier, route,
  call_recording_url, quality_score, tags, call_duration_seconds,
  raw_retell_payload, created_at, updated_at
)
select * from (
  -- NEW LEADS (8)
  select
    'bbbb0001-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-001', 'retell-demo-001', '+13135551001',
    $$Agent: Metro HVAC, how can I help?\nUser: My AC is blowing warm air and the house is at 88.$$,
    jsonb_build_object(
      'customer_name', 'Ariana Holt',
      'customer_phone', '+13135551001',
      'service_address', '2154 Cass Ave, Detroit, MI 48201',
      'problem_description', 'AC blowing warm air; indoor temp 88F.',
      'hvac_issue_type', 'No Cool',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Carrier',
      'equipment_age', '9 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'urgent', 'customer_hangup', false,
    null, null,
    'residential', 'service', 'major_repair', 'legitimate',
    'https://example.com/recordings/demo-call-001.mp3',
    8.9, array['new-lead','urgent','no-cool']::text[], 178,
    '{}'::jsonb,
    seed_now - interval '18 minutes',
    seed_now - interval '18 minutes'
  from seed_clock

  union all

  select
    'bbbb0002-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-002', 'retell-demo-002', '+13135551002',
    $$Agent: Metro HVAC.\nUser: Water is dripping from my attic air handler.$$,
    jsonb_build_object(
      'customer_name', 'Miguel Price',
      'customer_phone', '+13135551002',
      'service_address', '4701 Grand River Ave, Detroit, MI 48208',
      'problem_description', 'Water dripping from attic air handler.',
      'hvac_issue_type', 'Leaking',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Air Handler',
      'equipment_brand', 'Trane',
      'equipment_age', '6 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'routine', 'customer_hangup', false,
    null, null,
    'residential', 'service', 'standard_repair', 'legitimate',
    null,
    8.2, array['new-lead','routine','leak']::text[], 152,
    '{}'::jsonb,
    seed_now - interval '35 minutes',
    seed_now - interval '35 minutes'
  from seed_clock

  union all

  select
    'bbbb0003-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-003', 'retell-demo-003', '+13135551003',
    $$User: I want a replacement estimate for our 20-year-old system.$$,
    jsonb_build_object(
      'customer_name', 'Claire Benton',
      'customer_phone', '+13135551003',
      'service_address', '1127 Livernois St, Ferndale, MI 48220',
      'problem_description', 'Requesting replacement estimate for aging system.',
      'hvac_issue_type', 'Cooling',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC + Furnace',
      'equipment_brand', 'Unknown',
      'equipment_age', '20 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'estimate', 'customer_hangup', false,
    null, null,
    'residential', 'estimate', 'replacement', 'legitimate',
    'https://example.com/recordings/demo-call-003.mp3',
    8.8, array['new-lead','estimate','replacement']::text[], 164,
    '{}'::jsonb,
    seed_now - interval '1 hour 10 minutes',
    seed_now - interval '1 hour 10 minutes'
  from seed_clock

  union all

  select
    'bbbb0004-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-004', 'retell-demo-004', '+13135551004',
    $$User: Just checking options, no urgent issue right now.$$,
    jsonb_build_object(
      'customer_name', 'Darnell Jones',
      'customer_phone', '+13135551004',
      'service_address', '8010 Wyoming Ave, Detroit, MI 48204',
      'problem_description', '',
      'hvac_issue_type', null,
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', null,
      'equipment_brand', null,
      'equipment_age', null,
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'routine', 'customer_hangup', false,
    null, null,
    'residential', 'new_lead', 'diagnostic', 'legitimate',
    null,
    6.8, array['new-lead','can-wait']::text[], 96,
    '{}'::jsonb,
    seed_now - interval '2 hours',
    seed_now - interval '2 hours'
  from seed_clock

  union all

  select
    'bbbb0005-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-005', 'retell-demo-005', '+13135551005',
    $$User: Add me to your waitlist for next available technician.$$,
    jsonb_build_object(
      'customer_name', 'Lena Patel',
      'customer_phone', '+13135551005',
      'service_address', '22801 Woodward Ave, Ferndale, MI 48220',
      'problem_description', 'Requested waitlist placement for next available slot.',
      'hvac_issue_type', 'Cooling',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Lennox',
      'equipment_age', '11 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'routine', 'waitlist_added', false,
    null, null,
    'residential', 'service', 'standard_repair', 'legitimate',
    null,
    7.3, array['new-lead','waitlist']::text[], 118,
    '{}'::jsonb,
    seed_now - interval '2 hours 40 minutes',
    seed_now - interval '2 hours 40 minutes'
  from seed_clock

  union all

  select
    'bbbb0006-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-006', 'retell-demo-006', '+13135551006',
    $$User: We have three rental units and need a maintenance contract quote.$$,
    jsonb_build_object(
      'customer_name', 'Asha Reynolds',
      'customer_phone', '+13135551006',
      'service_address', '1432 Washington Blvd, Detroit, MI 48226',
      'problem_description', 'Multi-unit maintenance contract lead.',
      'hvac_issue_type', 'Maintenance',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Mixed Equipment',
      'equipment_brand', 'Mixed',
      'equipment_age', 'Various',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'routine', 'sales_lead', false,
    null, null,
    'property_manager', 'sales', 'replacement', 'legitimate',
    null,
    8.0, array['new-lead','sales-lead','property-manager']::text[], 141,
    '{}'::jsonb,
    seed_now - interval '3 hours 15 minutes',
    seed_now - interval '3 hours 15 minutes'
  from seed_clock

  union all

  select
    'bbbb0007-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-007', 'retell-demo-007', '+13135551007',
    $$User: I missed your callback and need to reconnect.$$,
    jsonb_build_object(
      'customer_name', 'Noah Spencer',
      'customer_phone', '+13135551007',
      'service_address', '9150 Gratiot Ave, Detroit, MI 48213',
      'problem_description', 'Need to reconnect after missed callback.',
      'appointment_booked', false,
      'callback_type', null,
      'appointment_datetime', null
    ),
    'pending', 'routine', 'customer_hangup', false,
    null, null,
    null, null, null, null,
    null,
    6.1, array['new-lead','pending-extraction']::text[], 73,
    '{}'::jsonb,
    seed_now - interval '25 minutes',
    seed_now - interval '25 minutes'
  from seed_clock

  union all

  select
    'bbbb0008-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-008', 'retell-demo-008', '+13135551008',
    $$User: Furnace shut off overnight; no heat this morning.$$,
    jsonb_build_object(
      'customer_name', 'Jamal Carter',
      'customer_phone', '+13135551008',
      'service_address', '6734 E Jefferson Ave, Detroit, MI 48207',
      'problem_description', 'No heat this morning; pending extraction.',
      'appointment_booked', false,
      'callback_type', null,
      'appointment_datetime', null
    ),
    'pending', 'urgent', 'customer_hangup', false,
    null, null,
    null, null, null, null,
    null,
    6.4, array['new-lead','pending-extraction','urgent']::text[], 84,
    '{}'::jsonb,
    seed_now - interval '42 minutes',
    seed_now - interval '42 minutes'
  from seed_clock

  -- FOLLOW-UPS (6)
  union all

  select
    'bbbb0009-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-009', 'retell-demo-009', '+13135551009',
    $$User: Call me back this afternoon between 3 and 5.$$,
    jsonb_build_object(
      'customer_name', 'Priya Mathur',
      'customer_phone', '+13135551009',
      'service_address', '4400 Russell St, Detroit, MI 48207',
      'problem_description', 'Requested callback this afternoon.',
      'hvac_issue_type', 'Cooling',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Rheem',
      'equipment_age', '7 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', 'callback_requested',
      'callback_window_start', to_char(seed_now - interval '10 minutes', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
      'callback_window_end', to_char(seed_now + interval '1 hour 50 minutes', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
    ),
    'complete', 'urgent', 'callback_later', true,
    null, null,
    'residential', 'service', 'standard_repair', 'legitimate',
    'https://example.com/recordings/demo-call-009.mp3',
    8.1, array['follow-up','callback-later','window-valid']::text[], 167,
    '{}'::jsonb,
    seed_now - interval '1 hour 25 minutes',
    seed_now - interval '1 hour 25 minutes'
  from seed_clock

  union all

  select
    'bbbb0010-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-010', 'retell-demo-010', '+13135551010',
    $$Agent: Booking system failed; we will call you back directly.$$,
    jsonb_build_object(
      'customer_name', 'Kevin Turner',
      'customer_phone', '+13135551010',
      'service_address', '3550 Trumbull Ave, Detroit, MI 48216',
      'problem_description', 'Booking failed and customer needs callback.',
      'hvac_issue_type', 'No Cool',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'York',
      'equipment_age', '10 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', 'callback_requested',
      'callback_window_start', to_char(seed_now - interval '4 hours', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
      'callback_window_end', to_char(seed_now - interval '2 hours', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
    ),
    'complete', 'urgent', 'booking_failed', false,
    null, null,
    'residential', 'service', 'major_repair', 'legitimate',
    'https://example.com/recordings/demo-call-010.mp3',
    7.5, array['follow-up','booking-failed','window-expired']::text[], 211,
    '{}'::jsonb,
    seed_now - interval '3 hours 20 minutes',
    seed_now - interval '3 hours 20 minutes'
  from seed_clock

  union all

  select
    'bbbb0011-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-011', 'retell-demo-011', '+13135551011',
    $$User: Following up on yesterday's diagnosis visit.$$,
    jsonb_build_object(
      'customer_name', 'Hector Flores',
      'customer_phone', '+13135551011',
      'service_address', '18221 Livernois Ave, Detroit, MI 48221',
      'problem_description', 'Follow-up requested after prior diagnostic.',
      'hvac_issue_type', 'Heating',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Gas Furnace',
      'equipment_brand', 'Goodman',
      'equipment_age', '8 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'routine', 'customer_hangup', false,
    null, null,
    'residential', 'followup', 'diagnostic', 'legitimate',
    null,
    7.6, array['follow-up','intent-followup']::text[], 127,
    '{}'::jsonb,
    seed_now - interval '5 hours',
    seed_now - interval '5 hours'
  from seed_clock

  union all

  select
    'bbbb0012-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-012', 'retell-demo-012', '+13135551012',
    $$User: I still have the same issue after your last visit.$$,
    jsonb_build_object(
      'customer_name', 'Sonia Gupta',
      'customer_phone', '+13135551012',
      'service_address', '5056 Vernor Hwy, Detroit, MI 48209',
      'problem_description', 'Complaint after prior service visit.',
      'hvac_issue_type', 'No Heat',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Gas Furnace',
      'equipment_brand', 'Lennox',
      'equipment_age', '12 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'routine', 'customer_hangup', false,
    null, null,
    'residential', 'complaint', 'standard_repair', 'legitimate',
    null,
    7.9, array['follow-up','complaint']::text[], 138,
    '{}'::jsonb,
    seed_now - interval '6 hours',
    seed_now - interval '6 hours'
  from seed_clock

  union all

  select
    'bbbb0013-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-013', 'retell-demo-013', '+13135551013',
    $$Agent: We tried calling back and left a voicemail.$$,
    jsonb_build_object(
      'customer_name', 'Trevor Bell',
      'customer_phone', '+13135551013',
      'service_address', '9212 Joseph Campau Ave, Hamtramck, MI 48212',
      'problem_description', 'No answer; voicemail left on callback.',
      'hvac_issue_type', 'Cooling',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Trane',
      'equipment_age', '9 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', 'callback_requested',
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'urgent', 'callback_later', true,
    'left_voicemail', seed_now - interval '35 minutes',
    'residential', 'active_job_issue', 'standard_repair', 'legitimate',
    'https://example.com/recordings/demo-call-013.mp3',
    8.0, array['follow-up','retry','left-voicemail']::text[], 119,
    '{}'::jsonb,
    seed_now - interval '9 hours',
    seed_now - interval '35 minutes'
  from seed_clock

  union all

  select
    'bbbb0014-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-014', 'retell-demo-014', '+13135551014',
    $$Agent: We attempted callback and got no answer.$$,
    jsonb_build_object(
      'customer_name', 'Monica Reed',
      'customer_phone', '+13135551014',
      'service_address', '300 River Place Dr, Detroit, MI 48207',
      'problem_description', 'Second callback attempt had no answer.',
      'hvac_issue_type', 'Heating',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Heat Pump',
      'equipment_brand', 'Amana',
      'equipment_age', '5 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', 'callback_requested',
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'routine', 'callback_later', true,
    'no_answer', seed_now - interval '1 hour 20 minutes',
    'residential', 'followup', 'diagnostic', 'legitimate',
    null,
    7.4, array['follow-up','retry','no-answer']::text[], 113,
    '{}'::jsonb,
    seed_now - interval '10 hours',
    seed_now - interval '1 hour 20 minutes'
  from seed_clock

  -- AI HANDLED (6)
  union all

  select
    'bbbb0015-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-015', 'retell-demo-015', '+13135551015',
    $$User: I smell gas near the furnace and everyone is outside.$$,
    jsonb_build_object(
      'customer_name', 'Marcus Neal',
      'customer_phone', '+13135551015',
      'service_address', '2544 E Grand Blvd, Detroit, MI 48211',
      'problem_description', 'Gas smell near furnace; evacuated.',
      'hvac_issue_type', 'Heating',
      'is_safety_emergency', true,
      'is_urgent_escalation', false,
      'equipment_type', 'Gas Furnace',
      'equipment_brand', 'Carrier',
      'equipment_age', '14 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'emergency', 'safety_emergency', false,
    null, null,
    'residential', 'service', 'major_repair', 'legitimate',
    null,
    9.4, array['ai-handled','escalated','safety']::text[], 204,
    '{}'::jsonb,
    seed_now - interval '14 minutes',
    seed_now - interval '14 minutes'
  from seed_clock

  union all

  select
    'bbbb0016-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-016', 'retell-demo-016', '+13135551016',
    $$User: AC failed and we have an elderly parent at home.$$,
    jsonb_build_object(
      'customer_name', 'Dana Kowalski',
      'customer_phone', '+13135551016',
      'service_address', '1044 Gratiot Ave, Detroit, MI 48207',
      'problem_description', 'No cooling with high-risk resident at home.',
      'hvac_issue_type', 'No Cool',
      'is_safety_emergency', false,
      'is_urgent_escalation', true,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Lennox',
      'equipment_age', '11 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'urgent', 'urgent_escalation', false,
    null, null,
    'residential', 'service', 'standard_repair', 'legitimate',
    null,
    9.1, array['ai-handled','escalated','urgent']::text[], 184,
    '{}'::jsonb,
    seed_now - interval '55 minutes',
    seed_now - interval '55 minutes'
  from seed_clock

  union all

  select
    'bbbb0017-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-017', 'retell-demo-017', '+13135551017',
    $$Agent: Appointment booked for tomorrow at 10:00 AM.$$,
    jsonb_build_object(
      'customer_name', 'Rina Shah',
      'customer_phone', '+13135551017',
      'service_address', '1870 Bagley St, Detroit, MI 48216',
      'problem_description', 'Scheduled annual tune-up appointment.',
      'hvac_issue_type', 'Maintenance',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Rheem',
      'equipment_age', '4 years',
      'appointment_booked', true,
      'appointment_datetime', to_char(seed_now + interval '1 day', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'routine', 'completed', false,
    null, null,
    'residential', 'maintenance', 'minor', 'legitimate',
    'https://example.com/recordings/demo-call-017.mp3',
    9.3, array['ai-handled','booked']::text[], 143,
    '{}'::jsonb,
    seed_now - interval '12 hours',
    seed_now - interval '12 hours'
  from seed_clock

  union all

  select
    'bbbb0018-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-018', 'retell-demo-018', '+13135551018',
    $$User: This is a vendor call for refrigerant supply pricing.$$,
    jsonb_build_object(
      'customer_name', 'Vendor Desk',
      'customer_phone', '+13135551018',
      'service_address', '',
      'problem_description', 'Vendor pricing solicitation.',
      'hvac_issue_type', null,
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', null,
      'equipment_brand', null,
      'equipment_age', null,
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'routine', 'customer_hangup', false,
    null, null,
    'vendor', 'solicitation', 'unknown', 'vendor',
    null,
    6.2, array['ai-handled','non-customer','vendor']::text[], 61,
    '{}'::jsonb,
    seed_now - interval '7 hours',
    seed_now - interval '7 hours'
  from seed_clock

  union all

  select
    'bbbb0019-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-019', 'retell-demo-019', '+13135551019',
    $$User: Sorry, wrong number — I needed a plumber.$$,
    jsonb_build_object(
      'customer_name', 'Wrong Number Caller',
      'customer_phone', '+13135551019',
      'service_address', '',
      'problem_description', 'Wrong number call.',
      'hvac_issue_type', null,
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', null,
      'equipment_brand', null,
      'equipment_age', null,
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'routine', 'wrong_number', false,
    null, null,
    'unknown', 'unknown', 'unknown', 'legitimate',
    null,
    9.7, array['ai-handled','wrong-number']::text[], 48,
    '{}'::jsonb,
    seed_now - interval '4 hours',
    seed_now - interval '4 hours'
  from seed_clock

  union all

  select
    'bbbb0020-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-020', 'retell-demo-020', '+13135551020',
    $$Agent: Follow-up completed; customer reached successfully.$$,
    jsonb_build_object(
      'customer_name', 'Gary Nolan',
      'customer_phone', '+13135551020',
      'service_address', '5400 Michigan Ave, Detroit, MI 48210',
      'problem_description', 'Follow-up completed and issue resolved.',
      'hvac_issue_type', 'Cooling',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Trane',
      'equipment_age', '10 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', 'callback_requested',
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'urgent', 'callback_later', false,
    'reached_customer', seed_now - interval '2 hours 10 minutes',
    'residential', 'service', 'standard_repair', 'legitimate',
    null,
    8.4, array['ai-handled','resolved','terminal-outcome']::text[], 102,
    '{}'::jsonb,
    seed_now - interval '1 day',
    seed_now - interval '2 hours 10 minutes'
  from seed_clock
) seeded_calls
on conflict (id) do nothing;

-- Seed historical callback touches for follow-up timeline UX.
-- For calls with non-null callback_outcome in call_records (demo-call-013/014/020),
-- we only seed older touches and let the trigger write the latest one.
with seed_clock as (
  select now() as seed_now
)
insert into public.callback_touches (id, tenant_id, call_id, outcome, created_at)
select * from (
  select 'dddd0001-0000-0000-0000-000000000001'::uuid, '00000000-0000-0000-0000-000000000001'::uuid, 'demo-call-009', 'left_voicemail', seed_now - interval '6 hours' from seed_clock
  union all
  select 'dddd0002-0000-0000-0000-000000000001'::uuid, '00000000-0000-0000-0000-000000000001'::uuid, 'demo-call-010', 'no_answer', seed_now - interval '7 hours' from seed_clock
  union all
  select 'dddd0003-0000-0000-0000-000000000001'::uuid, '00000000-0000-0000-0000-000000000001'::uuid, 'demo-call-011', 'left_voicemail', seed_now - interval '10 hours' from seed_clock
  union all
  select 'dddd0004-0000-0000-0000-000000000001'::uuid, '00000000-0000-0000-0000-000000000001'::uuid, 'demo-call-012', 'no_answer', seed_now - interval '11 hours' from seed_clock
  union all
  select 'dddd0005-0000-0000-0000-000000000001'::uuid, '00000000-0000-0000-0000-000000000001'::uuid, 'demo-call-013', 'no_answer', seed_now - interval '4 hours' from seed_clock
  union all
  select 'dddd0006-0000-0000-0000-000000000001'::uuid, '00000000-0000-0000-0000-000000000001'::uuid, 'demo-call-014', 'left_voicemail', seed_now - interval '9 hours' from seed_clock
) seeded_touches
on conflict (id) do nothing;
