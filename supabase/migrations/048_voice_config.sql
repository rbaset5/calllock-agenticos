-- Migration 048: Voice agent configuration and call records
--
-- Adds voice-specific config to tenant_configs and creates tables for
-- call record persistence and booking API key management.

-- Add voice config and Cal.com config columns to tenant_configs
ALTER TABLE public.tenant_configs
  ADD COLUMN voice_config jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN calcom_config jsonb NOT NULL DEFAULT '{}'::jsonb;

-- Call records table for voice call persistence
CREATE TABLE public.call_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  call_id text NOT NULL,
  retell_call_id text NOT NULL,
  phone_number text,
  transcript text,
  raw_retell_payload jsonb NOT NULL,
  extracted_fields jsonb DEFAULT '{}'::jsonb,
  extraction_status text NOT NULL DEFAULT 'pending',
  quality_score numeric(5,2),
  tags text[] DEFAULT '{}',
  route text,
  urgency_tier text,
  caller_type text,
  primary_intent text,
  revenue_tier text,
  booking_id text,
  callback_scheduled boolean DEFAULT false,
  call_duration_seconds integer,
  end_call_reason text,
  call_recording_url text,
  synced_to_app boolean DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, call_id)
);

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER call_records_updated_at
  BEFORE UPDATE ON public.call_records
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.voice_api_keys (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  api_key_hash text NOT NULL,
  label text NOT NULL DEFAULT 'default',
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  UNIQUE(api_key_hash)
);

ALTER TABLE public.call_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.call_records FORCE ROW LEVEL SECURITY;
CREATE POLICY call_records_tenant ON public.call_records
  USING (tenant_id = public.current_tenant_id());

ALTER TABLE public.voice_api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.voice_api_keys FORCE ROW LEVEL SECURITY;
CREATE POLICY voice_api_keys_tenant ON public.voice_api_keys
  USING (tenant_id = public.current_tenant_id());

CREATE INDEX idx_call_records_phone ON public.call_records(tenant_id, phone_number);
CREATE INDEX idx_call_records_unsynced ON public.call_records(tenant_id, synced_to_app)
  WHERE synced_to_app = false;

-- Phone indexes for lookup_caller cross-table queries (prevents latency blowup at scale)
-- Only add these if the tables exist; skip if they don't yet.
CREATE INDEX IF NOT EXISTS idx_jobs_phone ON public.jobs(tenant_id, customer_phone);
CREATE INDEX IF NOT EXISTS idx_bookings_phone ON public.bookings(tenant_id, customer_phone);
