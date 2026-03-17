-- Temporary RLS bypass for app rollout. Remove this when contractor auth ships.
-- Reference: docs/superpowers/plans/2026-03-17-calllock-app-migration.md

CREATE POLICY call_records_anon_read
ON public.call_records
FOR SELECT
TO anon
USING (true);

CREATE INDEX idx_call_records_created
ON public.call_records(created_at DESC);
