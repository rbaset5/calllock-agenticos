-- ── Tenant + config (single tenant) ─────────────────────────────────────────
insert into public.tenants (id, slug, name, industry_pack_id, contact_email, service_area, status)
values
  ('00000000-0000-0000-0000-000000000001', 'tenant-alpha', 'Tenant Alpha HVAC', 'hvac', 'ops@alpha.example', 'Detroit Metro', 'active')
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
  )
on conflict (tenant_id) do nothing;

-- ── Compliance rules (3 global, unchanged) ────────────────────────────────────
insert into public.compliance_rules (tenant_id, scope, rule_type, target, effect, reason, conflicts_with, metadata)
values
  (null, 'global', 'booking', 'book_appointment', 'allow', 'Booking allowed when tenant policy permits it.', '{}', '{"industry_pack_id":"hvac"}'::jsonb),
  (null, 'global', 'alerts', 'dispatch_emergency', 'allow', 'Emergency dispatch alerts are allowed for life-safety events.', '{}', '{"industry_pack_id":"hvac"}'::jsonb),
  (null, 'global', 'claims', 'marketing_claims', 'deny', 'Do not claim guaranteed savings or guaranteed same-day repair.', '{}', '{"forbidden_claims":["guaranteed savings","guaranteed same-day repair"]}'::jsonb);

-- ── Idempotent delete guard ───────────────────────────────────────────────────
-- callback_touches rows cascade via FK on (tenant_id, call_id).
delete from public.call_records
where tenant_id = '00000000-0000-0000-0000-000000000001'
  and call_id like 'demo-call-%';

-- ── 28 call_records ──────────────────────────────────────────────────────────
-- UI sections (see assignBucket + getDisplaySection in triage.ts / mail-sections.ts):
--   ESCALATED_BY_AI  : isSafetyEmergency=true OR isUrgentEscalation=true OR urgency=LifeSafety
--   NEW_LEADS        : ACTION_QUEUE / NEW_LEAD
--   FOLLOW_UPS       : ACTION_QUEUE / FOLLOW_UP
--   BOOKINGS         : appointmentBooked=true AND bookingStatus != 'cancelled'
--   OTHER_AI_HANDLED : all other handled (resolved, non_customer, wrong_number, booked+cancelled)

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
  booking_status, booking_status_at, booking_notes,
  raw_retell_payload, created_at, updated_at
)
select * from (

  -- ── ESCALATED_BY_AI (3) ───────────────────────────────────────────────────

  -- 1. Marcus Neal — Gas leak, family evacuated (14m ago)
  select
    'aaaa0001-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-001', 'retell-demo-001', '+13135550001',
    $$Agent: Metro HVAC, how can I help?
User: There's a strong gas smell in my house. My family is outside. I think the furnace is leaking.
Agent: That's a life-safety emergency. Please stay outside and call 911. We'll dispatch a technician immediately.$$,
    jsonb_build_object(
      'customer_name', 'Marcus Neal',
      'customer_phone', '+13135550001',
      'service_address', '1842 Woodward Ave, Detroit, MI 48201',
      'problem_description', 'Strong gas smell; family evacuated. Furnace suspected.',
      'hvac_issue_type', 'Odor',
      'is_safety_emergency', true,
      'is_urgent_escalation', false,
      'equipment_type', 'Furnace',
      'equipment_brand', 'Lennox',
      'equipment_age', '12 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'LifeSafety', 'safety_emergency', false,
    null, null,
    'residential', 'service', 'major_repair', 'legitimate',
    'https://example.com/recordings/demo-call-001.mp3',
    9.4, array['escalated','safety','gas-leak']::text[], 94,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '14 minutes',
    seed_now - interval '14 minutes'
  from seed_clock

  union all

  -- 2. Dana Kowalski — No cooling, elderly parent home alone (55m ago)
  select
    'aaaa0002-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-002', 'retell-demo-002', '+13135550002',
    $$Agent: Metro HVAC.
User: My AC has been out since yesterday. My 84-year-old father is home alone and it's 94 degrees out.
Agent: This is urgent. I'm escalating to our team right now.$$,
    jsonb_build_object(
      'customer_name', 'Dana Kowalski',
      'customer_phone', '+13135550002',
      'service_address', '3120 Gratiot Ave, Detroit, MI 48207',
      'problem_description', 'No cooling for 24h. Elderly parent home alone during heat advisory.',
      'hvac_issue_type', 'No Cool',
      'is_safety_emergency', false,
      'is_urgent_escalation', true,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Carrier',
      'equipment_age', '15 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'LifeSafety', 'urgent_escalation', false,
    null, null,
    'residential', 'service', 'major_repair', 'legitimate',
    'https://example.com/recordings/demo-call-002.mp3',
    9.1, array['escalated','urgent','no-cool','vulnerable']::text[], 118,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '55 minutes',
    seed_now - interval '55 minutes'
  from seed_clock

  union all

  -- 3. James Whitfield — CO detector triggered, furnace suspected (8m ago)
  select
    'aaaa0003-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-003', 'retell-demo-003', '+13135550003',
    $$Agent: Metro HVAC.
User: Our CO detector went off in the basement. We think it's the furnace. We're outside now.
Agent: Stay outside. This is a carbon monoxide emergency. Please call 911. I'm alerting dispatch.$$,
    jsonb_build_object(
      'customer_name', 'James Whitfield',
      'customer_phone', '+13135550003',
      'service_address', '5902 Livernois Ave, Detroit, MI 48210',
      'problem_description', 'CO detector triggered. Family outside. Furnace suspected source.',
      'hvac_issue_type', 'Odor',
      'is_safety_emergency', true,
      'is_urgent_escalation', false,
      'equipment_type', 'Furnace',
      'equipment_brand', 'Rheem',
      'equipment_age', '8 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'LifeSafety', 'safety_emergency', false,
    null, null,
    'residential', 'service', 'major_repair', 'legitimate',
    'https://example.com/recordings/demo-call-003.mp3',
    9.6, array['escalated','safety','co-alarm']::text[], 82,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '8 minutes',
    seed_now - interval '8 minutes'
  from seed_clock

  union all

  -- ── NEW_LEADS (9) ─────────────────────────────────────────────────────────

  -- 4. Ariana Holt — AC warm air, 88F house (18m ago) → Call now (Urgent)
  select
    'bbbb0001-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-004', 'retell-demo-004', '+13135550004',
    $$Agent: Metro HVAC, how can I help?
User: My AC is blowing warm air and the house is already at 88 degrees.
Agent: Got it. I'll flag this as urgent and have someone call you back shortly.$$,
    jsonb_build_object(
      'customer_name', 'Ariana Holt',
      'customer_phone', '+13135550004',
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
    'complete', 'Urgent', 'customer_hangup', false,
    null, null,
    'residential', 'service', 'major_repair', 'legitimate',
    'https://example.com/recordings/demo-call-004.mp3',
    8.9, array['new-lead','urgent','no-cool']::text[], 178,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '18 minutes',
    seed_now - interval '18 minutes'
  from seed_clock

  union all

  -- 5. Miguel Price — Water dripping from air handler (35m ago) → Today
  select
    'bbbb0002-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-005', 'retell-demo-005', '+13135550005',
    $$Agent: Metro HVAC.
User: Water is dripping from my attic air handler. There's a small puddle on the floor.
Agent: That sounds like a condensate drain clog. We'll get a tech out today.$$,
    jsonb_build_object(
      'customer_name', 'Miguel Price',
      'customer_phone', '+13135550005',
      'service_address', '4701 Grand River Ave, Detroit, MI 48208',
      'problem_description', 'Water dripping from attic air handler. Puddle forming.',
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
    'complete', 'Routine', 'customer_hangup', false,
    null, null,
    'residential', 'service', 'standard_repair', 'legitimate',
    null,
    8.2, array['new-lead','leak']::text[], 152,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '35 minutes',
    seed_now - interval '35 minutes'
  from seed_clock

  union all

  -- 6. Claire Benton — Replacement estimate, 20yr system (1h10m ago) → Today
  select
    'bbbb0003-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-006', 'retell-demo-006', '+13135550006',
    $$Agent: Metro HVAC.
User: I want a replacement estimate for our 20-year-old system. It runs but barely cools.
Agent: Absolutely. I'll have our comfort advisor call you today to discuss options.$$,
    jsonb_build_object(
      'customer_name', 'Claire Benton',
      'customer_phone', '+13135550006',
      'service_address', '7830 Michigan Ave, Detroit, MI 48210',
      'problem_description', 'Requesting replacement estimate. 20-year-old system barely cooling.',
      'hvac_issue_type', 'Cooling',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC + Furnace',
      'equipment_brand', 'York',
      'equipment_age', '20 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Estimate', 'customer_hangup', false,
    null, null,
    'residential', 'estimate', 'replacement', 'legitimate',
    null,
    7.8, array['new-lead','estimate','replacement']::text[], 201,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '1 hour 10 minutes',
    seed_now - interval '1 hour 10 minutes'
  from seed_clock

  union all

  -- 7. Darnell Jones — Browsing options, no issue (2h ago) → Can wait
  select
    'bbbb0004-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-007', 'retell-demo-007', '+13135550007',
    $$Agent: Metro HVAC.
User: Just looking into maintenance plans. No current issue, just planning ahead.
Agent: Great. I'll have someone reach out with plan options.$$,
    jsonb_build_object(
      'customer_name', 'Darnell Jones',
      'customer_phone', '+13135550007',
      'service_address', '910 E Jefferson Ave, Detroit, MI 48207',
      'problem_description', 'Browsing maintenance plan options. No active issue.',
      'hvac_issue_type', 'Maintenance',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central HVAC',
      'equipment_brand', 'Lennox',
      'equipment_age', '4 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Routine', 'customer_hangup', false,
    null, null,
    'residential', 'maintenance', 'minor', 'legitimate',
    null,
    7.4, array['new-lead','maintenance','low-priority']::text[], 134,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '2 hours',
    seed_now - interval '2 hours'
  from seed_clock

  union all

  -- 8. Lena Patel — Waitlist for next tech (2h40m ago) → Today
  -- waitlist_added end reason → rule 8 → ACTION_QUEUE NEW_LEAD
  select
    'bbbb0005-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-008', 'retell-demo-008', '+13135550008',
    $$Agent: Metro HVAC.
User: I know you're busy. Can you add me to the waitlist for the next available tech for an AC check?
Agent: Of course. You're on the waitlist. We'll call when a slot opens up.$$,
    jsonb_build_object(
      'customer_name', 'Lena Patel',
      'customer_phone', '+13135550008',
      'service_address', '1506 W Grand Blvd, Detroit, MI 48208',
      'problem_description', 'Requested waitlist for next available tech. AC check needed.',
      'hvac_issue_type', 'Cooling',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Goodman',
      'equipment_age', '5 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Routine', 'waitlist_added', false,
    null, null,
    'residential', 'service', 'diagnostic', 'legitimate',
    null,
    7.6, array['new-lead','waitlist']::text[], 112,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '2 hours 40 minutes',
    seed_now - interval '2 hours 40 minutes'
  from seed_clock

  union all

  -- 9. Asha Reynolds — Multi-unit contract lead (3h15m ago) → Today
  -- sales_lead end reason → rule 8 → ACTION_QUEUE NEW_LEAD
  select
    'bbbb0006-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-009', 'retell-demo-009', '+13135550009',
    $$Agent: Metro HVAC.
User: I manage a 12-unit apartment complex on East Jefferson. Looking for a maintenance contract.
Agent: That sounds like a great fit. I'll have our commercial team call you to put together a proposal.$$,
    jsonb_build_object(
      'customer_name', 'Asha Reynolds',
      'customer_phone', '+13135550009',
      'service_address', '2900 E Jefferson Ave, Detroit, MI 48207',
      'problem_description', 'Seeking annual maintenance contract for 12-unit complex.',
      'hvac_issue_type', 'Maintenance',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Multiple Units',
      'equipment_brand', 'Mixed',
      'equipment_age', 'Various',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Routine', 'sales_lead', false,
    null, null,
    'property_manager', 'estimate', 'replacement', 'legitimate',
    null,
    8.5, array['new-lead','commercial','contract']::text[], 187,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '3 hours 15 minutes',
    seed_now - interval '3 hours 15 minutes'
  from seed_clock

  union all

  -- 10. Noah Spencer — Reconnect; pending extraction (25m ago) → Can wait
  -- extraction_status='pending', no classification → isPendingExtraction=true → NEW_LEAD
  select
    'bbbb0007-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-010', 'retell-demo-010', '+13135550010',
    $$Agent: Metro HVAC.
User: Hi, I called earlier about my AC. Just checking if someone is going to call me back.
Agent: I see your record. I'll make sure someone follows up shortly.$$,
    jsonb_build_object(
      'customer_name', 'Noah Spencer',
      'customer_phone', '+13135550010',
      'service_address', null,
      'problem_description', 'Reconnect call — checking on callback status from earlier call.',
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
    'pending', 'Routine', 'customer_hangup', false,
    null, null,
    null, null, null, null,
    null,
    null, array['new-lead','pending-extraction']::text[], 67,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '25 minutes',
    seed_now - interval '25 minutes'
  from seed_clock

  union all

  -- 11. Jamal Carter — No heat; pending extraction, urgent signals (42m ago) → Call now
  -- extraction_status='pending', no classification → isPendingExtraction=true → NEW_LEAD
  -- urgency='Urgent' (not LifeSafety), is_safety_emergency=false → does NOT escalate
  select
    'bbbb0008-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-011', 'retell-demo-011', '+13135550011',
    $$Agent: Metro HVAC.
User: My heat went out last night. It's really cold in here. I have a baby at home.
Agent: I hear you, this is urgent. Someone will call you back within 15 minutes.$$,
    jsonb_build_object(
      'customer_name', 'Jamal Carter',
      'customer_phone', '+13135550011',
      'service_address', '8341 Dexter Ave, Detroit, MI 48206',
      'problem_description', 'No heat overnight. Infant at home. Cold indoor temp.',
      'hvac_issue_type', 'No Heat',
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
    'pending', 'Urgent', 'customer_hangup', false,
    null, null,
    null, null, null, null,
    null,
    null, array['new-lead','pending-extraction','no-heat','urgent']::text[], 103,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '42 minutes',
    seed_now - interval '42 minutes'
  from seed_clock

  union all

  -- 12. Tamika Washington — Noisy outdoor unit (1h50m ago) → Today
  select
    'bbbb0009-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-012', 'retell-demo-012', '+13135550012',
    $$Agent: Metro HVAC.
User: My outdoor AC unit started making a loud rattling noise yesterday. It's still running but it sounds terrible.
Agent: That can mean a loose part or debris in the fan. We'll send someone to take a look.$$,
    jsonb_build_object(
      'customer_name', 'Tamika Washington',
      'customer_phone', '+13135550012',
      'service_address', '6120 Schaefer Rd, Dearborn, MI 48126',
      'problem_description', 'Loud rattling noise from outdoor AC unit. Still running.',
      'hvac_issue_type', 'Noisy System',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Goodman',
      'equipment_age', '7 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Routine', 'customer_hangup', false,
    null, null,
    'residential', 'service', 'diagnostic', 'legitimate',
    null,
    8.1, array['new-lead','noisy-system']::text[], 156,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '1 hour 50 minutes',
    seed_now - interval '1 hour 50 minutes'
  from seed_clock

  union all

  -- ── FOLLOW_UPS (6) ────────────────────────────────────────────────────────

  -- 13. Kevin Turner — Booking failed, expired window (3h20m ago) → rank 0
  -- booking_failed → rule 9 → FOLLOW_UP. callback_window_end in the past → expired.
  select
    'cccc0001-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-013', 'retell-demo-013', '+13135550013',
    $$Agent: Metro HVAC.
User: I tried booking online but it kept failing. Really need someone out this week.
Agent: Sorry about that. We'll get booking sorted for you and call back to confirm.$$,
    jsonb_build_object(
      'customer_name', 'Kevin Turner',
      'customer_phone', '+13135550013',
      'service_address', '3201 Rosa Parks Blvd, Detroit, MI 48208',
      'problem_description', 'Booking failed during online attempt. Needs tech this week.',
      'hvac_issue_type', 'Cooling',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Carrier',
      'equipment_age', '11 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', 'preferred',
      'callback_window_start', null,
      'callback_window_end', (now() - interval '1 hour')::text
    ),
    'complete', 'Routine', 'booking_failed', false,
    'no_answer', seed_now - interval '7 hours',
    'residential', 'service', 'standard_repair', 'legitimate',
    null,
    7.9, array['follow-up','booking-failed']::text[], 143,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '3 hours 20 minutes',
    seed_now - interval '7 hours'
  from seed_clock

  union all

  -- 14. Sonia Gupta — Complaint, No Heat persists (6h ago) → rank 1
  -- complaint primary intent → rule 10 → FOLLOW_UP
  select
    'cccc0002-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-014', 'retell-demo-014', '+13135550014',
    $$Agent: Metro HVAC.
User: A tech came out two days ago and my heat is still not working. This is unacceptable.
Agent: I sincerely apologize. I'm escalating this to our service manager immediately.$$,
    jsonb_build_object(
      'customer_name', 'Sonia Gupta',
      'customer_phone', '+13135550014',
      'service_address', '4890 Woodward Ave, Detroit, MI 48201',
      'problem_description', 'Tech visited 2 days ago. Heat still not working. Formal complaint.',
      'hvac_issue_type', 'No Heat',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Furnace',
      'equipment_brand', 'Trane',
      'equipment_age', '3 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Urgent', 'customer_hangup', false,
    'no_answer', seed_now - interval '11 hours',
    'residential', 'complaint', 'standard_repair', 'legitimate',
    null,
    6.8, array['follow-up','complaint','no-heat']::text[], 167,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '6 hours',
    seed_now - interval '11 hours'
  from seed_clock

  union all

  -- 15. Trevor Bell — Active job issue (9h ago) → rank 1
  -- active_job_issue primary intent → rule 10 → FOLLOW_UP
  -- 2 touches: no_answer -8h, no_answer -4h
  select
    'cccc0003-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-015', 'retell-demo-015', '+13135550015',
    $$Agent: Metro HVAC.
User: Your tech is at my house right now but he says he doesn't have the right part. This job should have been prepped.
Agent: I understand your frustration. Let me connect you with the dispatcher.$$,
    jsonb_build_object(
      'customer_name', 'Trevor Bell',
      'customer_phone', '+13135550015',
      'service_address', '7644 Livernois Ave, Detroit, MI 48210',
      'problem_description', 'Active job — tech on site lacks required part. Customer frustrated.',
      'hvac_issue_type', 'Heating',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Furnace',
      'equipment_brand', 'Rheem',
      'equipment_age', '6 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Urgent', 'customer_hangup', false,
    'no_answer', seed_now - interval '4 hours',
    'residential', 'active_job_issue', 'standard_repair', 'legitimate',
    null,
    7.2, array['follow-up','active-job','parts']::text[], 189,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '9 hours',
    seed_now - interval '4 hours'
  from seed_clock

  union all

  -- 16. Priya Mathur — Callback requested, valid window (1h25m ago) → rank 2
  -- callback_later end reason → rule 9 → FOLLOW_UP
  select
    'cccc0004-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-016', 'retell-demo-016', '+13135550016',
    $$Agent: Metro HVAC.
User: I'd prefer to be called back between 2 and 4 PM today. It's about my thermostat acting up.
Agent: Noted. I'll schedule a callback for that window.$$,
    jsonb_build_object(
      'customer_name', 'Priya Mathur',
      'customer_phone', '+13135550016',
      'service_address', '2240 West Grand Blvd, Detroit, MI 48208',
      'problem_description', 'Thermostat acting erratically. Requested callback 2–4 PM today.',
      'hvac_issue_type', 'Thermostat',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Smart Thermostat',
      'equipment_brand', 'Ecobee',
      'equipment_age', '2 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', 'requested',
      'callback_window_start', (now() + interval '30 minutes')::text,
      'callback_window_end', (now() + interval '2 hours 30 minutes')::text
    ),
    'complete', 'Routine', 'callback_later', true,
    'left_voicemail', seed_now - interval '6 hours',
    'residential', 'service', 'minor', 'legitimate',
    null,
    8.3, array['follow-up','callback-requested','thermostat']::text[], 121,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '1 hour 25 minutes',
    seed_now - interval '6 hours'
  from seed_clock

  union all

  -- 17. Monica Reed — Second attempt, no answer (10h ago) → rank 3
  -- left_voicemail callback outcome → RETRY_OUTCOMES → rule 11 → FOLLOW_UP
  select
    'cccc0005-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-017', 'retell-demo-017', '+13135550017',
    $$Agent: Metro HVAC.
User: I was trying to get a quote on a mini-split installation. Left a message before.
Agent: I'll make sure someone calls you back today with pricing.$$,
    jsonb_build_object(
      'customer_name', 'Monica Reed',
      'customer_phone', '+13135550017',
      'service_address', '5510 Kercheval Ave, Grosse Pointe, MI 48224',
      'problem_description', 'Quote requested for mini-split installation. Second contact attempt.',
      'hvac_issue_type', 'Cooling',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Mini-Split',
      'equipment_brand', 'Mitsubishi',
      'equipment_age', null,
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Estimate', 'customer_hangup', false,
    'left_voicemail', seed_now - interval '9 hours',
    'residential', 'estimate', 'replacement', 'legitimate',
    null,
    7.5, array['follow-up','no-answer','estimate']::text[], 98,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '10 hours',
    seed_now - interval '9 hours'
  from seed_clock

  union all

  -- 18. Hector Flores — Follow-up after diagnostic (5h ago) → rank 4
  -- followup primary intent → rule 10 → FOLLOW_UP
  select
    'cccc0006-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-018', 'retell-demo-018', '+13135550018',
    $$Agent: Metro HVAC.
User: I got the diagnostic done last week. The tech said to follow up about whether I want to proceed with the repair.
Agent: Of course, I'll pass that along and have someone call you to discuss options.$$,
    jsonb_build_object(
      'customer_name', 'Hector Flores',
      'customer_phone', '+13135550018',
      'service_address', '1388 Dix Ave, Lincoln Park, MI 48146',
      'problem_description', 'Post-diagnostic follow-up. Deciding whether to proceed with repair.',
      'hvac_issue_type', 'No Cool',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Carrier',
      'equipment_age', '14 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Routine', 'customer_hangup', false,
    'left_voicemail', seed_now - interval '10 hours',
    'residential', 'followup', 'diagnostic', 'legitimate',
    null,
    8.0, array['follow-up','post-diagnostic']::text[], 145,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '5 hours',
    seed_now - interval '10 hours'
  from seed_clock

  union all

  -- ── BOOKINGS (4 visible + 1 cancelled → OTHER) ────────────────────────────

  -- 19. Priya Sharma — AC tune-up, tomorrow 2PM (3h ago) → unconfirmed (null)
  select
    'dddd0001-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-019', 'retell-demo-019', '+13135550019',
    $$Agent: Metro HVAC.
User: I'd like to book an AC tune-up. Tomorrow afternoon works best for me.
Agent: I've booked you for an AC tune-up tomorrow at 2 PM. You'll get a confirmation text.$$,
    jsonb_build_object(
      'customer_name', 'Priya Sharma',
      'customer_phone', '+13135550019',
      'service_address', '3904 Vernor Hwy, Detroit, MI 48209',
      'problem_description', 'Annual AC tune-up requested. System running fine.',
      'hvac_issue_type', 'Maintenance',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Lennox',
      'equipment_age', '5 years',
      'appointment_booked', true,
      'appointment_datetime', (now() + interval '26 hours')::text,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Routine', 'completed', false,
    null, null,
    'residential', 'maintenance', 'minor', 'legitimate',
    null,
    8.7, array['booking','unconfirmed','tune-up']::text[], 167,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '3 hours',
    seed_now - interval '3 hours'
  from seed_clock

  union all

  -- 20. Marcus Webb — Furnace inspection, +2 days (5h ago) → unconfirmed (null)
  select
    'dddd0002-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-020', 'retell-demo-020', '+13135550020',
    $$Agent: Metro HVAC.
User: I need a furnace inspection before the heating season. Can I get something in the next few days?
Agent: I've booked you for a furnace inspection in two days. Does morning work?
User: Morning is perfect.$$,
    jsonb_build_object(
      'customer_name', 'Marcus Webb',
      'customer_phone', '+13135550020',
      'service_address', '8720 Wyoming Ave, Detroit, MI 48204',
      'problem_description', 'Pre-season furnace inspection. No current issue.',
      'hvac_issue_type', 'Heating',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Furnace',
      'equipment_brand', 'Goodman',
      'equipment_age', '9 years',
      'appointment_booked', true,
      'appointment_datetime', (now() + interval '50 hours')::text,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Routine', 'completed', false,
    null, null,
    'residential', 'maintenance', 'diagnostic', 'legitimate',
    null,
    8.4, array['booking','unconfirmed','furnace-inspection']::text[], 192,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '5 hours',
    seed_now - interval '5 hours'
  from seed_clock

  union all

  -- 21. Lisa Tran — Emergency AC repair, today +4h (8h ago) → confirmed
  select
    'dddd0003-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-021', 'retell-demo-021', '+13135550021',
    $$Agent: Metro HVAC.
User: My AC just died. I need someone today.
Agent: We have an opening in 4 hours. I've confirmed you at 3 PM today.$$,
    jsonb_build_object(
      'customer_name', 'Lisa Tran',
      'customer_phone', '+13135550021',
      'service_address', '2015 Mack Ave, Detroit, MI 48207',
      'problem_description', 'AC stopped working completely. Emergency same-day repair.',
      'hvac_issue_type', 'No Cool',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Trane',
      'equipment_age', '10 years',
      'appointment_booked', true,
      'appointment_datetime', (now() + interval '4 hours')::text,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Urgent', 'completed', false,
    null, null,
    'residential', 'service', 'major_repair', 'legitimate',
    null,
    9.0, array['booking','confirmed','emergency-repair']::text[], 143,
    'confirmed', seed_now - interval '6 hours', 'Confirmed by dispatch. Tech en route.',
    '{}'::jsonb,
    seed_now - interval '8 hours',
    seed_now - interval '6 hours'
  from seed_clock

  union all

  -- 22. Robert Kim — Thermostat replacement, +3 days (12h ago) → confirmed
  select
    'dddd0004-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-022', 'retell-demo-022', '+13135550022',
    $$Agent: Metro HVAC.
User: I need my old thermostat replaced with a smart one. Any time this week works.
Agent: We have an opening in three days. Afternoon slot confirmed.$$,
    jsonb_build_object(
      'customer_name', 'Robert Kim',
      'customer_phone', '+13135550022',
      'service_address', '5320 W Vernor Hwy, Detroit, MI 48209',
      'problem_description', 'Thermostat replacement — upgrading to smart thermostat.',
      'hvac_issue_type', 'Thermostat',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Thermostat',
      'equipment_brand', 'Honeywell',
      'equipment_age', '12 years',
      'appointment_booked', true,
      'appointment_datetime', (now() + interval '74 hours')::text,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Routine', 'completed', false,
    null, null,
    'residential', 'installation', 'minor', 'legitimate',
    null,
    8.6, array['booking','confirmed','thermostat']::text[], 158,
    'confirmed', seed_now - interval '10 hours', 'Confirmed for Thursday afternoon.',
    '{}'::jsonb,
    seed_now - interval '12 hours',
    seed_now - interval '10 hours'
  from seed_clock

  union all

  -- 23. Angela Foster — Duct cleaning, cancelled (1d ago) → OTHER_AI_HANDLED
  -- appointmentBooked=true + bookingStatus='cancelled' → getDisplaySection → OTHER_AI_HANDLED
  select
    'dddd0005-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-023', 'retell-demo-023', '+13135550023',
    $$Agent: Metro HVAC.
User: I need to cancel my duct cleaning appointment. Something came up.
Agent: Of course. Your appointment has been cancelled. Please call when you're ready to reschedule.$$,
    jsonb_build_object(
      'customer_name', 'Angela Foster',
      'customer_phone', '+13135550023',
      'service_address', '1420 Gratiot Ave, Detroit, MI 48207',
      'problem_description', 'Duct cleaning appointment cancelled by customer.',
      'hvac_issue_type', 'Maintenance',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Ductwork',
      'equipment_brand', null,
      'equipment_age', null,
      'appointment_booked', true,
      'appointment_datetime', (now() + interval '48 hours')::text,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Routine', 'completed', false,
    null, null,
    'residential', 'maintenance', 'minor', 'legitimate',
    null,
    7.3, array['booking','cancelled','duct-cleaning']::text[], 112,
    'cancelled', seed_now - interval '20 hours', 'Customer cancelled. Schedule conflict.',
    '{}'::jsonb,
    seed_now - interval '1 day',
    seed_now - interval '20 hours'
  from seed_clock

  union all

  -- ── OTHER_AI_HANDLED (5) ──────────────────────────────────────────────────

  -- 24. Gary Nolan — Callback completed, reached customer (1d ago) → resolved
  -- reached_customer is TERMINAL → handled("resolved") → OTHER_AI_HANDLED
  -- 2 historical touches before resolution: no_answer -8h, left_voicemail -5h
  select
    'eeee0001-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-024', 'retell-demo-024', '+13135550024',
    $$Agent: Metro HVAC.
User: My AC was making a clicking noise but it seems to have stopped. Maybe just a one-time thing.
Agent: Happy to hear it resolved. We'll mark this as handled. Give us a call if it comes back.$$,
    jsonb_build_object(
      'customer_name', 'Gary Nolan',
      'customer_phone', '+13135550024',
      'service_address', '9812 Fenkell Ave, Detroit, MI 48238',
      'problem_description', 'Clicking noise from AC. Resolved on its own before callback.',
      'hvac_issue_type', 'Noisy System',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Central AC',
      'equipment_brand', 'Carrier',
      'equipment_age', '8 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Routine', 'customer_hangup', false,
    'reached_customer', seed_now - interval '2 hours',
    'residential', 'service', 'diagnostic', 'legitimate',
    null,
    7.8, array['handled','resolved','reached-customer']::text[], 134,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '1 day',
    seed_now - interval '2 hours'
  from seed_clock

  union all

  -- 25. Vendor Desk — Refrigerant vendor call (7h ago) → non_customer
  -- route='vendor' → rule 2 → handled("non_customer") → OTHER_AI_HANDLED
  select
    'eeee0002-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-025', 'retell-demo-025', '+18005550025',
    $$Agent: Metro HVAC.
User: Hi, this is National Refrigerants. Calling about your R-410A order placed last week.
Agent: This looks like a vendor call. I'll pass your info to our purchasing team.$$,
    jsonb_build_object(
      'customer_name', 'Vendor Desk',
      'customer_phone', '+18005550025',
      'service_address', null,
      'problem_description', 'Vendor call — refrigerant supplier following up on parts order.',
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
    'complete', 'Routine', 'customer_hangup', false,
    null, null,
    'vendor', 'admin_billing', 'unknown', 'vendor',
    null,
    5.0, array['handled','vendor','non-customer']::text[], 78,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '7 hours',
    seed_now - interval '7 hours'
  from seed_clock

  union all

  -- 26. Unknown Caller — Wrong number, needed plumber (4h ago) → wrong_number
  -- wrong_number end reason → rule 4 → handled("wrong_number") → OTHER_AI_HANDLED
  select
    'eeee0003-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-026', 'retell-demo-026', '+13135550026',
    $$Agent: Metro HVAC.
User: Wait, this is HVAC? I need a plumber. Wrong number, sorry.
Agent: No problem! Try searching for a local plumber. Goodbye!$$,
    jsonb_build_object(
      'customer_name', 'Unknown Caller',
      'customer_phone', '+13135550026',
      'service_address', null,
      'problem_description', 'Wrong number — caller needed a plumber, not HVAC.',
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
    'complete', 'Routine', 'wrong_number', false,
    null, null,
    'unknown', 'unknown', 'unknown', 'legitimate',
    null,
    6.0, array['handled','wrong-number']::text[], 34,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '4 hours',
    seed_now - interval '4 hours'
  from seed_clock

  union all

  -- 27. Robo Dialer — Spam, extraction failed (6h ago) → non_customer
  -- route='spam' → rule 2 → handled("non_customer") → OTHER_AI_HANDLED
  select
    'eeee0004-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-027', 'retell-demo-027', '+18885550027',
    $$Agent: Metro HVAC.
User: Congratulations! You've been selected for a special—
Agent: This appears to be an automated call. Ending session.$$,
    jsonb_build_object(
      'customer_name', 'Robo Dialer',
      'customer_phone', '+18885550027',
      'service_address', null,
      'problem_description', 'Spam robocall. Extraction failed.',
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
    'failed', 'Routine', 'customer_hangup', false,
    null, null,
    'spam', 'solicitation', 'unknown', 'spam',
    null,
    1.0, array['handled','spam','extraction-failed']::text[], 18,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '6 hours',
    seed_now - interval '6 hours'
  from seed_clock

  union all

  -- 28. David Park — Resolved elsewhere (18h ago) → resolved
  -- resolved_elsewhere is TERMINAL → handled("resolved") → OTHER_AI_HANDLED
  -- 1 historical touch: no_answer -6h (before customer confirmed resolved)
  select
    'eeee0005-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-028', 'retell-demo-028', '+13135550028',
    $$Agent: Metro HVAC.
User: Actually, my neighbor ended up fixing the issue for me. I don't need a tech anymore. Thanks anyway.
Agent: Great to hear! We've noted this as resolved. Don't hesitate to call if anything comes up.$$,
    jsonb_build_object(
      'customer_name', 'David Park',
      'customer_phone', '+13135550028',
      'service_address', '4410 W Chicago Ave, Detroit, MI 48204',
      'problem_description', 'Resolved by neighbor before tech visit. Closing call.',
      'hvac_issue_type', 'No Heat',
      'is_safety_emergency', false,
      'is_urgent_escalation', false,
      'equipment_type', 'Furnace',
      'equipment_brand', 'Carrier',
      'equipment_age', '7 years',
      'appointment_booked', false,
      'appointment_datetime', null,
      'callback_type', null,
      'callback_window_start', null,
      'callback_window_end', null
    ),
    'complete', 'Routine', 'customer_hangup', false,
    'resolved_elsewhere', seed_now - interval '3 hours',
    'residential', 'service', 'minor', 'legitimate',
    null,
    7.6, array['handled','resolved-elsewhere']::text[], 89,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '18 hours',
    seed_now - interval '3 hours'
  from seed_clock

  union all

  -- 29. Ray Dunbar — Urgent but no details, customer hung up fast (20m ago) → Next up
  -- urgency='Urgent' + hasConcrete()=false → computeCommand="Next up"
  -- No booking_failed, no callback_later → stays in NEW_LEADS (not FOLLOW_UPS)
  -- Exercises the "Urgent, needs details" chip (getCallbackReason)
  select
    'bbbb0010-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'demo-call-029', 'retell-demo-029', '+13135550029',
    $$Agent: Metro HVAC, how can I help?
User: Yeah I need someone out here, this is urgent.
Agent: I understand. Can you tell me what's going on?
[call disconnected]$$,
    jsonb_build_object(
      'customer_name', 'Ray Dunbar',
      'customer_phone', '+13135550029',
      'service_address', null,
      'problem_description', null,
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
    'complete', 'Urgent', 'customer_hangup', false,
    null, null,
    'residential', null, null, 'legitimate',
    null,
    3.2, array['new-lead','urgent','no-details']::text[], 18,
    null, null, null,
    '{}'::jsonb,
    seed_now - interval '20 minutes',
    seed_now - interval '20 minutes'
  from seed_clock

) as calls;

-- ── callback_touches — 10 rows with precise timestamps ────────────────────────
-- The log_callback_touch trigger fires on call_records INSERT when callback_outcome
-- is not null, inserting one touch per call. We delete all auto-inserted touches
-- and replace them with the exact historical timeline from the plan.

delete from public.callback_touches
where tenant_id = '00000000-0000-0000-0000-000000000001'
  and call_id like 'demo-call-%';

with seed_clock as (
  select now() as seed_now
)
insert into public.callback_touches (tenant_id, call_id, outcome, created_at)
values
  -- demo-call-013 Kevin Turner: 1 touch — no answer 7h ago
  ('00000000-0000-0000-0000-000000000001', 'demo-call-013', 'no_answer',     (select seed_now - interval '7 hours'  from seed_clock)),
  -- demo-call-014 Sonia Gupta: 1 touch — no answer 11h ago
  ('00000000-0000-0000-0000-000000000001', 'demo-call-014', 'no_answer',     (select seed_now - interval '11 hours' from seed_clock)),
  -- demo-call-015 Trevor Bell: 2 touches — no answer 8h ago, then 4h ago
  ('00000000-0000-0000-0000-000000000001', 'demo-call-015', 'no_answer',     (select seed_now - interval '8 hours'  from seed_clock)),
  ('00000000-0000-0000-0000-000000000001', 'demo-call-015', 'no_answer',     (select seed_now - interval '4 hours'  from seed_clock)),
  -- demo-call-016 Priya Mathur: 1 touch — left voicemail 6h ago
  ('00000000-0000-0000-0000-000000000001', 'demo-call-016', 'left_voicemail',(select seed_now - interval '6 hours'  from seed_clock)),
  -- demo-call-017 Monica Reed: 1 touch — left voicemail 9h ago
  ('00000000-0000-0000-0000-000000000001', 'demo-call-017', 'left_voicemail',(select seed_now - interval '9 hours'  from seed_clock)),
  -- demo-call-018 Hector Flores: 1 touch — left voicemail 10h ago
  ('00000000-0000-0000-0000-000000000001', 'demo-call-018', 'left_voicemail',(select seed_now - interval '10 hours' from seed_clock)),
  -- demo-call-024 Gary Nolan: 2 touches before resolution — no answer 8h ago, voicemail 5h ago
  ('00000000-0000-0000-0000-000000000001', 'demo-call-024', 'no_answer',     (select seed_now - interval '8 hours'  from seed_clock)),
  ('00000000-0000-0000-0000-000000000001', 'demo-call-024', 'left_voicemail',(select seed_now - interval '5 hours'  from seed_clock)),
  -- demo-call-028 David Park: 1 touch — no answer 6h ago (later confirmed resolved)
  ('00000000-0000-0000-0000-000000000001', 'demo-call-028', 'no_answer',     (select seed_now - interval '6 hours'  from seed_clock));
