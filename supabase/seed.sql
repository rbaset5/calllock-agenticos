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
