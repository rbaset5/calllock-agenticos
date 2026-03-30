-- Test tenant and seeded call records for Product Guardian eng-app checks.
-- These records have known field values that eng-app validates against
-- via headless browser (Playwright).
-- This fixture set is deterministic and CI-focused; realistic day-to-day
-- app data lives in supabase/seed.sql.
--
-- The test tenant is identified by a well-known UUID.
-- Guardian agents use this tenant for automated health checks.

-- Only insert if test tenant doesn't already exist (idempotent).
insert into public.tenants (id, name, slug)
values (
  'a0000000-0000-0000-0000-000000000001',
  'Guardian Test Tenant',
  'guardian-test'
) on conflict (id) do nothing;

-- Seed 5 call records with known extraction values.
-- eng-app will load the app filtered to this tenant and verify each field renders.
insert into public.call_records (
  id, tenant_id, call_id, retell_call_id, phone_number,
  extracted_fields, extraction_status, urgency_tier,
  end_call_reason, callback_scheduled, created_at
) values
(
  'b0000000-0000-0000-0000-000000000001',
  'a0000000-0000-0000-0000-000000000001',
  'test-call-001', 'retell-test-001', '+15551000001',
  '{
    "customer_name": "Alice Johnson",
    "customer_phone": "+15551000001",
    "service_address": "123 Oak Street, Austin, TX 78701",
    "problem_description": "AC unit not cooling, compressor making loud noise",
    "urgency_tier": "urgent",
    "caller_type": "residential",
    "primary_intent": "service",
    "hvac_issue_type": "Cooling",
    "is_safety_emergency": false,
    "equipment_type": "Central AC",
    "equipment_brand": "Carrier",
    "equipment_age": "8 years",
    "appointment_booked": true,
    "appointment_datetime": "2026-03-19T10:00:00Z",
    "callback_type": null,
    "end_call_reason": "completed",
    "route": "legitimate",
    "revenue_tier": "standard_repair",
    "tags": ["cooling-issue", "compressor-noise"],
    "quality_score": 8.5
  }'::jsonb,
  'complete', 'urgent', 'completed', false,
  now() - interval '2 hours'
),
(
  'b0000000-0000-0000-0000-000000000002',
  'a0000000-0000-0000-0000-000000000001',
  'test-call-002', 'retell-test-002', '+15551000002',
  '{
    "customer_name": "Bob Martinez",
    "customer_phone": "+15551000002",
    "service_address": "456 Elm Ave, Austin, TX 78702",
    "problem_description": "Gas smell near furnace",
    "urgency_tier": "emergency",
    "caller_type": "residential",
    "primary_intent": "service",
    "hvac_issue_type": "Heating",
    "is_safety_emergency": true,
    "equipment_type": "Gas Furnace",
    "equipment_brand": "Lennox",
    "equipment_age": "12 years",
    "appointment_booked": false,
    "appointment_datetime": null,
    "callback_type": null,
    "end_call_reason": "safety_emergency",
    "route": "legitimate",
    "revenue_tier": "major_repair",
    "tags": ["gas-leak", "safety-emergency", "heating-issue"],
    "quality_score": 9.0
  }'::jsonb,
  'complete', 'emergency', 'safety_emergency', false,
  now() - interval '1 hour'
),
(
  'b0000000-0000-0000-0000-000000000003',
  'a0000000-0000-0000-0000-000000000001',
  'test-call-003', 'retell-test-003', '+15551000003',
  '{
    "customer_name": "Carol Chen",
    "customer_phone": "+15551000003",
    "service_address": "789 Pine Blvd, Austin, TX 78703",
    "problem_description": "Annual maintenance check requested",
    "urgency_tier": "routine",
    "caller_type": "residential",
    "primary_intent": "maintenance",
    "hvac_issue_type": "Maintenance",
    "is_safety_emergency": false,
    "equipment_type": "Heat Pump",
    "equipment_brand": "Trane",
    "equipment_age": "3 years",
    "appointment_booked": true,
    "appointment_datetime": "2026-03-25T14:00:00Z",
    "callback_type": null,
    "end_call_reason": "completed",
    "route": "legitimate",
    "revenue_tier": "minor",
    "tags": ["maintenance", "annual-checkup"],
    "quality_score": 9.5
  }'::jsonb,
  'complete', 'routine', 'completed', false,
  now() - interval '30 minutes'
),
(
  'b0000000-0000-0000-0000-000000000004',
  'a0000000-0000-0000-0000-000000000001',
  'test-call-004', 'retell-test-004', '+15551000004',
  '{
    "customer_name": "Dave Wilson",
    "customer_phone": "+15551000004",
    "service_address": "321 Maple Dr, Austin, TX 78704",
    "problem_description": "Want an estimate for new system installation",
    "urgency_tier": "estimate",
    "caller_type": "residential",
    "primary_intent": "estimate",
    "hvac_issue_type": "Cooling",
    "is_safety_emergency": false,
    "equipment_type": "Window Unit",
    "equipment_brand": "Unknown",
    "equipment_age": "15 years",
    "appointment_booked": false,
    "appointment_datetime": null,
    "callback_type": "callback_requested",
    "end_call_reason": "callback_later",
    "route": "legitimate",
    "revenue_tier": "replacement",
    "tags": ["estimate", "new-install", "replacement"],
    "quality_score": 7.0
  }'::jsonb,
  'complete', 'estimate', 'callback_later', true,
  now() - interval '15 minutes'
),
(
  'b0000000-0000-0000-0000-000000000005',
  'a0000000-0000-0000-0000-000000000001',
  'test-call-005', 'retell-test-005', '+15551000005',
  '{
    "customer_name": "Eve Taylor",
    "customer_phone": "+15551000005",
    "service_address": "654 Cedar Ln, Austin, TX 78705",
    "problem_description": "Wrong number, looking for a plumber",
    "urgency_tier": "routine",
    "caller_type": "unknown",
    "primary_intent": "wrong_number",
    "hvac_issue_type": null,
    "is_safety_emergency": false,
    "equipment_type": null,
    "equipment_brand": null,
    "equipment_age": null,
    "appointment_booked": false,
    "appointment_datetime": null,
    "callback_type": null,
    "end_call_reason": "wrong_number",
    "route": "legitimate",
    "revenue_tier": "unknown",
    "tags": ["wrong-number"],
    "quality_score": 10.0
  }'::jsonb,
  'complete', 'routine', 'wrong_number', false,
  now() - interval '5 minutes'
)
on conflict (id) do nothing;
