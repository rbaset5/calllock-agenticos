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

-- ── Realistic HVAC call records for tenant-alpha ──────────────────────────
-- 20 calls covering all triage states: LifeSafety, Urgent, Routine, Estimate,
-- resolved, and terminal. Idempotent: ON CONFLICT (id) DO NOTHING.
--
-- Field notes:
--   urgency_tier:  emergency → LifeSafety | urgent → Urgent | routine → Routine | estimate → Estimate
--   is_safety_emergency / is_urgent_escalation: read from extracted_fields by transforms.ts
--   appointment_booked in extracted_fields drives the UPCOMING section
--   callback_window_start/end: call 06 uses jsonb_build_object for dynamic timestamps

insert into public.call_records (
  id, tenant_id, call_id, retell_call_id, phone_number,
  transcript, extracted_fields, extraction_status,
  urgency_tier, end_call_reason, callback_scheduled,
  callback_outcome, callback_outcome_at,
  caller_type, primary_intent, revenue_tier, route,
  quality_score, tags, call_duration_seconds,
  raw_retell_payload, created_at, updated_at
) values

-- ── GROUP 1: Emergency / LifeSafety / "Call now" ──────────────────────────

-- 01: Marcus Webb — gas smell, evacuated (LifeSafety → "Call now")
(
  'aaaa0001-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-001', 'retell-seed-001', '+13135550001',
  E'Agent: Thanks for calling Metro HVAC. What\'s going on today?\nUser: There\'s a gas smell near my furnace and I\'ve gotten everyone outside.\nAgent: I\'m flagging this as a life-safety emergency right now. We\'ll have someone out ASAP.\nUser: Please hurry, I\'m really scared.',
  '{"customer_name":"Marcus Webb","customer_phone":"+13135550001","service_address":"4821 Woodward Ave, Detroit, MI 48201","problem_description":"Gas smell near furnace, customer evacuated the home.","hvac_issue_type":"Heating","is_safety_emergency":true,"is_urgent_escalation":false,"equipment_type":"Gas Furnace","equipment_brand":"Carrier","equipment_age":"14 years","appointment_booked":false,"appointment_datetime":null,"callback_type":null,"callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'emergency', 'safety_emergency', false,
  null, null,
  'residential', 'service', 'major_repair', 'legitimate',
  9.2, array['gas-smell','safety-emergency','heating'], 187,
  '{}'::jsonb,
  now() - interval '25 minutes', now() - interval '25 minutes'
),

-- 02: Denise Kowalski — AC out, elderly mother, 94°F inside (Urgent+escalation → high priority)
(
  'aaaa0002-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-002', 'retell-seed-002', '+13135550002',
  E'Agent: Metro HVAC, how can I help?\nUser: My AC completely stopped and my 84-year-old mother is here. It\'s 94 degrees inside.\nAgent: I\'m escalating this as an urgent priority. A technician will call you within 15 minutes.\nUser: Please, she has heart problems. This is serious.',
  '{"customer_name":"Denise Kowalski","customer_phone":"+13135550002","service_address":"1640 W 8 Mile Rd, Detroit, MI 48203","problem_description":"AC failed with elderly high-risk family member home during extreme heat.","hvac_issue_type":"No Cool","is_safety_emergency":false,"is_urgent_escalation":true,"equipment_type":"Central AC","equipment_brand":"Lennox","equipment_age":"11 years","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'urgent', 'urgent_escalation', false,
  null, null,
  'residential', 'service', 'standard_repair', 'legitimate',
  9.5, array['no-cool','urgent-escalation','elderly'], 241,
  '{}'::jsonb,
  now() - interval '90 minutes', now() - interval '90 minutes'
),

-- ── GROUP 2: Urgent / "Next up" ───────────────────────────────────────────

-- 03: Tony Ferrara — AC compressor dead, 90°F house
(
  'aaaa0003-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-003', 'retell-seed-003', '+13135550003',
  E'Agent: Metro HVAC, what can we do for you?\nUser: My AC went out completely — compressor was grinding and now nothing. It\'s 90 degrees.\nAgent: Sounds like a compressor failure. I\'ll have a tech call you back to get this handled fast.\nUser: How soon? It\'s brutal in here.',
  '{"customer_name":"Tony Ferrara","customer_phone":"+13135550003","service_address":"22315 Michigan Ave, Dearborn, MI 48124","problem_description":"AC compressor grinding then failing, no cooling, 90°F inside.","hvac_issue_type":"No Cool","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Central AC","equipment_brand":"Trane","equipment_age":"9 years","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'urgent', 'callback_later', true,
  null, null,
  'residential', 'service', 'major_repair', 'legitimate',
  8.7, array['no-cool','compressor-failure','urgent'], 198,
  '{}'::jsonb,
  now() - interval '45 minutes', now() - interval '45 minutes'
),

-- 04: Sandra Kim — furnace won't start, kids at home (stale: >60 min)
(
  'aaaa0004-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-004', 'retell-seed-004', '+13135550004',
  E'Agent: Metro HVAC, how can I help you today?\nUser: My furnace isn\'t turning on at all. I have two small kids at home and it\'s really cold.\nAgent: I understand — urgent with kids in the house. A technician will call you back shortly.\nUser: Please make it quick, it\'s 58 degrees in here.',
  '{"customer_name":"Sandra Kim","customer_phone":"+13135550004","service_address":"5502 Schaefer Rd, Dearborn, MI 48126","problem_description":"Furnace not starting, no heat, two young children at home.","hvac_issue_type":"No Heat","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Gas Furnace","equipment_brand":"Goodman","equipment_age":"7 years","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'urgent', 'callback_later', true,
  null, null,
  'residential', 'service', 'standard_repair', 'legitimate',
  9.0, array['no-heat','furnace-failure','urgent'], 215,
  '{}'::jsonb,
  now() - interval '2 hours', now() - interval '2 hours'
),

-- 05: Jorge Reyes — booking failed mid-call, system error
(
  'aaaa0005-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-005', 'retell-seed-005', '+13135550005',
  E'Agent: Metro HVAC, how can I help?\nUser: My AC is out, blowing warm air and then nothing.\nAgent: I can schedule a tech — actually I\'m hitting a system error trying to book. I\'ll flag this for a direct callback.\nUser: Okay, just have them call soon.',
  '{"customer_name":"Jorge Reyes","customer_phone":"+13135550005","service_address":"18300 Mack Ave, Grosse Pointe Farms, MI 48236","problem_description":"AC stopped working, booking failed due to system error during call.","hvac_issue_type":"No Cool","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Central AC","equipment_brand":"Rheem","equipment_age":"6 years","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'urgent', 'booking_failed', false,
  null, null,
  'residential', 'service', 'standard_repair', 'legitimate',
  7.8, array['no-cool','booking-failed','urgent'], 312,
  '{}'::jsonb,
  now() - interval '3 hours', now() - interval '3 hours'
),

-- 06: Patricia Okafor — AC out, valid 2-hour callback window (dynamic timestamps)
(
  'aaaa0006-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-006', 'retell-seed-006', '+13135550006',
  E'Agent: Metro HVAC, what\'s going on today?\nUser: My central air stopped working, need someone to take a look.\nAgent: Absolutely. What window works best for a callback?\nUser: Anytime in the next two hours works — I\'m home all afternoon.',
  jsonb_build_object(
    'customer_name', 'Patricia Okafor',
    'customer_phone', '+13135550006',
    'service_address', '3901 W 12 Mile Rd, Berkley, MI 48072',
    'problem_description', 'Central AC not working, customer available for 2-hour callback window.',
    'hvac_issue_type', 'No Cool',
    'is_safety_emergency', false,
    'is_urgent_escalation', false,
    'equipment_type', 'Central AC',
    'equipment_brand', 'York',
    'equipment_age', '5 years',
    'appointment_booked', false,
    'appointment_datetime', null,
    'callback_type', 'callback_requested',
    'callback_window_start', to_char(now() + interval '30 minutes', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    'callback_window_end',   to_char(now() + interval '150 minutes', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
  ),
  'complete', 'urgent', 'callback_later', true,
  null, null,
  'residential', 'service', 'standard_repair', 'legitimate',
  8.4, array['no-cool','callback-window','urgent'], 178,
  '{}'::jsonb,
  now() - interval '30 minutes', now() - interval '30 minutes'
),

-- ── GROUP 3: Routine / "Today" or "Can wait" ──────────────────────────────

-- 07: Robert Tanner — thermostat unresponsive
(
  'aaaa0007-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-007', 'retell-seed-007', '+13135550007',
  E'Agent: Metro HVAC, how can I help?\nUser: My thermostat isn\'t responding — I press buttons and nothing happens.\nAgent: That could be the thermostat itself or a wiring issue. I\'ll get a tech to call you back.\nUser: Sure, not a huge rush — the system still sort of works.',
  '{"customer_name":"Robert Tanner","customer_phone":"+13135550007","service_address":"30700 Woodward Ave, Royal Oak, MI 48073","problem_description":"Thermostat unresponsive, system still partially operational.","hvac_issue_type":"Thermostat","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Smart Thermostat","equipment_brand":"Nest","equipment_age":"3 years","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'routine', 'callback_later', true,
  null, null,
  'residential', 'service', 'diagnostic', 'legitimate',
  8.1, array['thermostat','routine'], 143,
  '{}'::jsonb,
  now() - interval '4 hours', now() - interval '4 hours'
),

-- 08: Angela Price — loud grinding noise for two days
(
  'aaaa0008-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-008', 'retell-seed-008', '+13135550008',
  E'Agent: Metro HVAC, what can we help with?\nUser: My AC is making a really loud grinding noise, worse than usual.\nAgent: Grinding can mean a worn bearing or debris in the fan. I\'ll have someone follow up.\nUser: It\'s been two days — still blows cold but the noise is awful.',
  '{"customer_name":"Angela Price","customer_phone":"+13135550008","service_address":"14600 Northline Rd, Southgate, MI 48195","problem_description":"AC unit making loud grinding noise for two days, still cooling.","hvac_issue_type":"Noisy System","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Central AC","equipment_brand":"Carrier","equipment_age":"8 years","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'routine', 'callback_later', true,
  null, null,
  'residential', 'service', 'standard_repair', 'legitimate',
  8.3, array['noisy-system','grinding','routine'], 167,
  '{}'::jsonb,
  now() - interval '6 hours', now() - interval '6 hours'
),

-- 09: Kevin Murphy — water dripping from air handler
(
  'aaaa0009-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-009', 'retell-seed-009', '+13135550009',
  E'Agent: Metro HVAC, how can we help?\nUser: Water is dripping from my air handler in the attic, getting on the ceiling below.\nAgent: Likely a clogged condensate drain line. I\'ll schedule a callback with a tech.\nUser: How soon can someone come? I don\'t want ceiling damage.',
  '{"customer_name":"Kevin Murphy","customer_phone":"+13135550009","service_address":"6700 15 Mile Rd, Sterling Heights, MI 48312","problem_description":"Water dripping from attic air handler, potential ceiling damage risk.","hvac_issue_type":"Leaking","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Air Handler","equipment_brand":"American Standard","equipment_age":"5 years","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'routine', 'callback_later', true,
  null, null,
  'residential', 'service', 'minor', 'legitimate',
  8.6, array['leaking','condensate-drain','routine'], 201,
  '{}'::jsonb,
  now() - interval '8 hours', now() - interval '8 hours'
),

-- 10: Fatima Hassan — burning smell, customer hung up before scheduling
(
  'aaaa0010-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-010', 'retell-seed-010', '+13135550010',
  E'Agent: Metro HVAC, what\'s happening?\nUser: I smell something burning when the heat kicks on — like a dusty burn smell.\nAgent: That can be normal at season start, but we should verify. Can I get your address?\nUser: Hang on—',
  '{"customer_name":"Fatima Hassan","customer_phone":"+13135550010","service_address":"900 Oakland Ave, Pontiac, MI 48342","problem_description":"Burning smell when heat activates, call ended before scheduling.","hvac_issue_type":"Odor","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Gas Furnace","equipment_brand":"Heil","equipment_age":"10 years","appointment_booked":false,"appointment_datetime":null,"callback_type":null,"callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'routine', 'customer_hangup', false,
  null, null,
  'residential', 'service', 'diagnostic', 'legitimate',
  6.5, array['odor','burning-smell','hung-up'], 88,
  '{}'::jsonb,
  now() - interval '5 hours', now() - interval '5 hours'
),

-- 11: Steve Nowak — AC runs but won't cool below 78°F
(
  'aaaa0011-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-011', 'retell-seed-011', '+13135550011',
  E'Agent: Metro HVAC, how can I help?\nUser: My AC is running — I can hear it — but the house won\'t get below 78 even with it set to 72.\nAgent: Sounds like a refrigerant issue or coil problem. I\'ll have a tech reach out.\nUser: Take your time, it\'s manageable but definitely not right.',
  '{"customer_name":"Steve Nowak","customer_phone":"+13135550011","service_address":"4821 Woodward Ave, Detroit, MI 48201","problem_description":"AC running but not cooling below 78°F, likely refrigerant or coil issue.","hvac_issue_type":"Cooling","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Central AC","equipment_brand":"Lennox","equipment_age":"12 years","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'routine', 'callback_later', true,
  null, null,
  'residential', 'service', 'standard_repair', 'legitimate',
  7.9, array['cooling-issue','refrigerant','routine'], 223,
  '{}'::jsonb,
  now() - interval '12 hours', now() - interval '12 hours'
),

-- ── GROUP 4: Estimate / "Today" ───────────────────────────────────────────

-- 12: Claire Benson — full HVAC replacement estimate
(
  'aaaa0012-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-012', 'retell-seed-012', '+13135550012',
  E'Agent: Metro HVAC, what can we do for you?\nUser: Our system is 22 years old and constantly breaking down. We want to replace the whole thing.\nAgent: At that age a full replacement makes sense. I\'ll have our comfort consultant call to set up a free in-home assessment.\nUser: Great, flexible on timing — no rush.',
  '{"customer_name":"Claire Benson","customer_phone":"+13135550012","service_address":"22315 Michigan Ave, Dearborn, MI 48124","problem_description":"22-year-old system needs full replacement, requesting free estimate.","hvac_issue_type":"Cooling","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Central AC + Furnace","equipment_brand":"Unknown","equipment_age":"22 years","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'estimate', 'callback_later', true,
  null, null,
  'residential', 'estimate', 'replacement', 'legitimate',
  8.8, array['estimate','replacement','full-system'], 267,
  '{}'::jsonb,
  now() - interval '18 hours', now() - interval '18 hours'
),

-- 13: Miguel Santos — ductless mini-split installation quote
(
  'aaaa0013-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-013', 'retell-seed-013', '+13135550013',
  E'Agent: Metro HVAC, how can I help?\nUser: I want to add a ductless mini-split to my garage workshop — need a quote.\nAgent: Great choice for a garage. I\'ll have our install team call you to discuss sizing and pricing.\nUser: Sounds good, just planning ahead for summer.',
  '{"customer_name":"Miguel Santos","customer_phone":"+13135550013","service_address":"5502 Schaefer Rd, Dearborn, MI 48126","problem_description":"Requesting estimate for ductless mini-split installation in garage workshop.","hvac_issue_type":"Cooling","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Ductless Mini-Split","equipment_brand":"Mitsubishi","equipment_age":"N/A","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'estimate', 'callback_later', true,
  null, null,
  'residential', 'estimate', 'replacement', 'legitimate',
  9.1, array['estimate','mini-split','installation'], 189,
  '{}'::jsonb,
  now() - interval '24 hours', now() - interval '24 hours'
),

-- 14: Rhonda Patel — commercial rooftop unit estimate
(
  'aaaa0014-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-014', 'retell-seed-014', '+13135550014',
  E'Agent: Metro HVAC, how can we help?\nUser: We run a small retail space and our rooftop unit is dying. Need a commercial replacement quote.\nAgent: We handle commercial RTUs. I\'ll have our commercial team reach out to schedule a site visit.\nUser: Perfect — the unit is probably 18-20 tons, we\'re in Southgate.',
  '{"customer_name":"Rhonda Patel","customer_phone":"+13135550014","service_address":"14600 Northline Rd, Southgate, MI 48195","problem_description":"Commercial rooftop unit failing, requesting replacement estimate for retail space.","hvac_issue_type":"Cooling","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Rooftop Unit","equipment_brand":"Carrier","equipment_age":"18 years","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'estimate', 'callback_later', true,
  null, null,
  'commercial', 'estimate', 'replacement', 'legitimate',
  8.9, array['estimate','commercial','rooftop-unit'], 298,
  '{}'::jsonb,
  now() - interval '36 hours', now() - interval '36 hours'
),

-- ── GROUP 5: Resolved ─────────────────────────────────────────────────────

-- 15: Gary Novak — reached_customer (HANDLED)
(
  'aaaa0015-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-015', 'retell-seed-015', '+13135550015',
  E'Agent: Metro HVAC, how can I help?\nUser: My AC isn\'t keeping up — runs all day and only gets to 76.\nAgent: Sounds like it may need a refrigerant charge. I\'ll schedule a callback.\nUser: That works, mornings are best for me.',
  '{"customer_name":"Gary Novak","customer_phone":"+13135550015","service_address":"3901 W 12 Mile Rd, Berkley, MI 48072","problem_description":"AC not keeping up in heat, possibly low on refrigerant.","hvac_issue_type":"Cooling","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Central AC","equipment_brand":"Trane","equipment_age":"10 years","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'urgent', 'callback_later', false,
  'reached_customer', now() - interval '44 hours',
  'residential', 'service', 'standard_repair', 'legitimate',
  8.2, array['cooling-issue','reached-customer'], 178,
  '{}'::jsonb,
  now() - interval '48 hours', now() - interval '44 hours'
),

-- 16: Tamara Fields — scheduled callback (HANDLED)
(
  'aaaa0016-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-016', 'retell-seed-016', '+13135550016',
  E'Agent: Metro HVAC, what can we do for you today?\nUser: My heat pump clicks on startup and sometimes doesn\'t turn on.\nAgent: Clicking on startup can mean a capacitor issue. Let me flag this for a tech callback.\nUser: Sure, any day this week is fine.',
  '{"customer_name":"Tamara Fields","customer_phone":"+13135550016","service_address":"30700 Woodward Ave, Royal Oak, MI 48073","problem_description":"Heat pump clicking on startup, intermittent failure to turn on.","hvac_issue_type":"Heating","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Heat Pump","equipment_brand":"American Standard","equipment_age":"7 years","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'routine', 'callback_later', false,
  'scheduled', now() - interval '46 hours',
  'residential', 'service', 'standard_repair', 'legitimate',
  8.5, array['heat-pump','capacitor','scheduled'], 205,
  '{}'::jsonb,
  now() - interval '50 hours', now() - interval '46 hours'
),

-- 17: Leo Marchetti — resolved_elsewhere (HANDLED)
(
  'aaaa0017-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-017', 'retell-seed-017', '+13135550017',
  E'Agent: Metro HVAC, how can I help?\nUser: My furnace isn\'t igniting — been out since last night.\nAgent: That could be the igniter or gas valve. I\'ll have a tech follow up shortly.\nUser: Okay, though I may call around to see who\'s available fastest.',
  '{"customer_name":"Leo Marchetti","customer_phone":"+13135550017","service_address":"1640 W 8 Mile Rd, Detroit, MI 48203","problem_description":"Furnace not igniting, customer indicated may seek other providers.","hvac_issue_type":"No Heat","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Gas Furnace","equipment_brand":"Goodman","equipment_age":"9 years","appointment_booked":false,"appointment_datetime":null,"callback_type":"callback_requested","callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'urgent', 'callback_later', false,
  'resolved_elsewhere', now() - interval '48 hours',
  'residential', 'service', 'standard_repair', 'legitimate',
  7.4, array['no-heat','igniter','resolved-elsewhere'], 156,
  '{}'::jsonb,
  now() - interval '52 hours', now() - interval '48 hours'
),

-- 18: Priya Sharma — appointment booked (UPCOMING)
(
  'aaaa0018-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-018', 'retell-seed-018', '+13135550018',
  E'Agent: Metro HVAC, how can I help you today?\nUser: I need to schedule my annual AC tune-up before summer hits.\nAgent: Absolutely — we have Thursday at 10 AM open. Does that work?\nUser: Thursday at 10 works perfectly, thank you.',
  '{"customer_name":"Priya Sharma","customer_phone":"+13135550018","service_address":"6700 15 Mile Rd, Sterling Heights, MI 48312","problem_description":"Annual AC maintenance tune-up requested before summer season.","hvac_issue_type":"Maintenance","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Central AC","equipment_brand":"Rheem","equipment_age":"4 years","appointment_booked":true,"appointment_datetime":"2026-04-03T10:00:00Z","callback_type":null,"callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'routine', 'completed', false,
  null, null,
  'residential', 'maintenance', 'minor', 'legitimate',
  9.8, array['maintenance','annual-tuneup','booked'], 312,
  '{}'::jsonb,
  now() - interval '60 hours', now() - interval '60 hours'
),

-- ── GROUP 6: Terminal / Rejected ──────────────────────────────────────────

-- 19: Dave Custer — wrong number
(
  'aaaa0019-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-019', 'retell-seed-019', '+13135550019',
  E'Agent: Metro HVAC, how can I help?\nUser: Hi, I\'m looking for Metro Plumbing?\nAgent: This is Metro HVAC, not plumbing — you may have the wrong number.\nUser: Oh sorry, my mistake. Bye.',
  '{"customer_name":"Dave Custer","customer_phone":"+13135550019","service_address":"","problem_description":"Wrong number, caller looking for plumbing company.","hvac_issue_type":null,"is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":null,"equipment_brand":null,"equipment_age":null,"appointment_booked":false,"appointment_datetime":null,"callback_type":null,"callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'routine', 'wrong_number', false,
  null, null,
  'unknown', 'unknown', 'unknown', 'legitimate',
  9.5, array['wrong-number'], 32,
  '{}'::jsonb,
  now() - interval '3 hours', now() - interval '3 hours'
),

-- 20: Helen Ford — out of service area
(
  'aaaa0020-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  'seed-call-020', 'retell-seed-020', '+13135550020',
  E'Agent: Metro HVAC, how can we help?\nUser: Hi, my AC isn\'t working and I\'m in Ann Arbor.\nAgent: Unfortunately we don\'t currently service the Ann Arbor area. I\'m sorry I can\'t help today.\nUser: Oh, that\'s too bad. Thank you anyway.',
  '{"customer_name":"Helen Ford","customer_phone":"+13135550020","service_address":"111 S Main St, Ann Arbor, MI 48104","problem_description":"AC not working, customer located outside service area.","hvac_issue_type":"Cooling","is_safety_emergency":false,"is_urgent_escalation":false,"equipment_type":"Central AC","equipment_brand":"Unknown","equipment_age":"Unknown","appointment_booked":false,"appointment_datetime":null,"callback_type":null,"callback_window_start":null,"callback_window_end":null}'::jsonb,
  'complete', 'routine', 'out_of_area', false,
  null, null,
  'residential', 'service', 'unknown', 'legitimate',
  8.0, array['out-of-area'], 67,
  '{}'::jsonb,
  now() - interval '4 hours', now() - interval '4 hours'
)

on conflict (id) do nothing;
