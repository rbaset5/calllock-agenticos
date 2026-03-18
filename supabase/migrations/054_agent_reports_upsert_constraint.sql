-- Add unique constraint for daily report upsert.
-- Each agent writes one report per day per tenant.
-- persist_node upserts on this constraint.
create unique index if not exists idx_agent_reports_unique
  on public.agent_reports (agent_id, report_date, tenant_id);
