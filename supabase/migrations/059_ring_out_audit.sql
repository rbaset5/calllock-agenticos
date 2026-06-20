-- Migration 059: After-hours ring-out audit runtime
--
-- Stores approved audit prospects, scheduled dial attempts, Twilio callback
-- outcomes, and caller-number health for the HVAC after-hours audit workflow.

ALTER TABLE public.scheduler_backlog
  DROP CONSTRAINT IF EXISTS scheduler_backlog_job_type_check;

ALTER TABLE public.scheduler_backlog
  ADD CONSTRAINT scheduler_backlog_job_type_check
  CHECK (job_type IN ('retention', 'tenant_eval', 'ring_out_audit_attempt'));

CREATE TABLE IF NOT EXISTS public.ring_out_audit_prospects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  tenant_slug text,
  prospect_id text NOT NULL,
  business_name text NOT NULL,
  phone text NOT NULL,
  timezone text NOT NULL,
  source_batch text NOT NULL,
  status text NOT NULL DEFAULT 'scheduled'
    CHECK (status IN ('scheduled', 'retry_pending', 'decisive')),
  attempt_count integer NOT NULL DEFAULT 0,
  first_decisive_outcome text,
  last_outcome text,
  last_outcome_at timestamptz,
  ringing_duration_seconds integer,
  estimated_rings integer,
  target_segment text,
  priority_score integer NOT NULL DEFAULT 0,
  sales_angle text NOT NULL DEFAULT '',
  imported_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, prospect_id, source_batch)
);

CREATE TABLE IF NOT EXISTS public.ring_out_audit_attempts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  tenant_slug text,
  attempt_id text NOT NULL UNIQUE,
  prospect_id text NOT NULL,
  prospect_record_id uuid REFERENCES public.ring_out_audit_prospects(id) ON DELETE CASCADE,
  business_name text NOT NULL,
  phone text NOT NULL,
  timezone text NOT NULL,
  source_batch text NOT NULL,
  attempt_number integer NOT NULL CHECK (attempt_number BETWEEN 1 AND 3),
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'dialing', 'completed', 'skipped', 'failed')),
  scheduled_for timestamptz NOT NULL,
  scheduled_for_local text NOT NULL,
  scheduler_backlog_id uuid REFERENCES public.scheduler_backlog(id),
  provider text,
  provider_status text,
  call_sid text,
  claimed_by text,
  claimed_at timestamptz,
  placed_at timestamptz,
  completed_at timestamptz,
  skipped_reason text,
  outcome text,
  call_status text,
  answered_by text,
  ringing_duration_seconds integer,
  estimated_rings integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.ring_out_audit_outcomes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  prospect_id text NOT NULL,
  attempt_id text NOT NULL,
  call_sid text NOT NULL,
  outcome text NOT NULL CHECK (
    outcome IN (
      'ring_out_confirmed',
      'after_hours_voicemail',
      'covered_after_hours',
      'answered_before_timeout',
      'carrier_failed',
      'blocked_or_rejected',
      'invalid_number',
      'ambiguous_failure'
    )
  ),
  call_status text,
  answered_by text,
  ringing_duration_seconds integer,
  estimated_rings integer,
  error_code text,
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.ring_out_audit_caller_health (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid REFERENCES public.tenants(id) ON DELETE CASCADE,
  caller_number text NOT NULL UNIQUE,
  business_profile_status text,
  shaken_stir_status text,
  voice_integrity_status text,
  cnam_status text,
  inbound_callback_status text,
  spam_label_status text,
  last_checked_at timestamptz,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ring_out_audit_prospects_batch_idx
  ON public.ring_out_audit_prospects(tenant_id, source_batch, priority_score DESC);

CREATE INDEX IF NOT EXISTS ring_out_audit_prospects_outcome_idx
  ON public.ring_out_audit_prospects(tenant_id, first_decisive_outcome, priority_score DESC);

CREATE INDEX IF NOT EXISTS ring_out_audit_attempts_due_idx
  ON public.ring_out_audit_attempts(tenant_id, status, scheduled_for);

CREATE INDEX IF NOT EXISTS ring_out_audit_attempts_prospect_idx
  ON public.ring_out_audit_attempts(tenant_id, prospect_id, attempt_number);

CREATE INDEX IF NOT EXISTS ring_out_audit_attempts_call_sid_idx
  ON public.ring_out_audit_attempts(call_sid);

CREATE INDEX IF NOT EXISTS ring_out_audit_outcomes_call_sid_idx
  ON public.ring_out_audit_outcomes(call_sid);

CREATE INDEX IF NOT EXISTS ring_out_audit_outcomes_prospect_idx
  ON public.ring_out_audit_outcomes(tenant_id, prospect_id, created_at);

ALTER TABLE public.ring_out_audit_prospects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ring_out_audit_prospects FORCE ROW LEVEL SECURITY;
CREATE POLICY ring_out_audit_prospects_tenant ON public.ring_out_audit_prospects
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

ALTER TABLE public.ring_out_audit_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ring_out_audit_attempts FORCE ROW LEVEL SECURITY;
CREATE POLICY ring_out_audit_attempts_tenant ON public.ring_out_audit_attempts
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

ALTER TABLE public.ring_out_audit_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ring_out_audit_outcomes FORCE ROW LEVEL SECURITY;
CREATE POLICY ring_out_audit_outcomes_tenant ON public.ring_out_audit_outcomes
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

ALTER TABLE public.ring_out_audit_caller_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ring_out_audit_caller_health FORCE ROW LEVEL SECURITY;
CREATE POLICY ring_out_audit_caller_health_tenant ON public.ring_out_audit_caller_health
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE TRIGGER ring_out_audit_prospects_updated_at
  BEFORE UPDATE ON public.ring_out_audit_prospects
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER ring_out_audit_attempts_updated_at
  BEFORE UPDATE ON public.ring_out_audit_attempts
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER ring_out_audit_caller_health_updated_at
  BEFORE UPDATE ON public.ring_out_audit_caller_health
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
