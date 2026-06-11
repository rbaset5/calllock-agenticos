-- Migration 058: Voice production-layer evidence capture
--
-- Adds normalized evidence tables around Retell call records. Retell remains
-- the real-time runtime; these tables support debugging and production review.

CREATE TABLE public.voice_call_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid REFERENCES public.tenants(id),
  call_id text NOT NULL,
  retell_call_id text NOT NULL,
  event_type text NOT NULL,
  event_timestamp timestamptz,
  source text NOT NULL DEFAULT 'retell',
  payload jsonb NOT NULL,
  payload_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.voice_tool_calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid REFERENCES public.tenants(id),
  call_id text NOT NULL,
  retell_call_id text,
  tool_name text NOT NULL,
  request_payload jsonb NOT NULL,
  response_payload jsonb,
  status text NOT NULL,
  latency_ms integer,
  error_type text,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.voice_config_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid REFERENCES public.tenants(id),
  call_id text NOT NULL,
  retell_agent_id text,
  retell_llm_id text,
  config_source_path text,
  config_hash text NOT NULL,
  config_snapshot jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, call_id)
);

CREATE TABLE public.voice_safety_findings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  call_id text NOT NULL,
  finding_type text NOT NULL,
  severity text NOT NULL,
  status text NOT NULL DEFAULT 'open',
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.voice_call_debug_packets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  call_id text NOT NULL,
  packet jsonb NOT NULL,
  failure_bucket text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, call_id)
);

ALTER TABLE public.voice_call_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.voice_call_events FORCE ROW LEVEL SECURITY;
CREATE POLICY voice_call_events_tenant ON public.voice_call_events
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

ALTER TABLE public.voice_tool_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.voice_tool_calls FORCE ROW LEVEL SECURITY;
CREATE POLICY voice_tool_calls_tenant ON public.voice_tool_calls
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

ALTER TABLE public.voice_config_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.voice_config_snapshots FORCE ROW LEVEL SECURITY;
CREATE POLICY voice_config_snapshots_tenant ON public.voice_config_snapshots
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

ALTER TABLE public.voice_safety_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.voice_safety_findings FORCE ROW LEVEL SECURITY;
CREATE POLICY voice_safety_findings_tenant ON public.voice_safety_findings
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

ALTER TABLE public.voice_call_debug_packets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.voice_call_debug_packets FORCE ROW LEVEL SECURITY;
CREATE POLICY voice_call_debug_packets_tenant ON public.voice_call_debug_packets
  USING (tenant_id = public.current_tenant_id())
  WITH CHECK (tenant_id = public.current_tenant_id());

CREATE INDEX idx_voice_call_events_call
  ON public.voice_call_events(tenant_id, call_id, created_at);

CREATE INDEX idx_voice_tool_calls_call
  ON public.voice_tool_calls(tenant_id, call_id, created_at);

CREATE INDEX idx_voice_tool_calls_tool_status
  ON public.voice_tool_calls(tenant_id, tool_name, status, created_at DESC);

CREATE INDEX idx_voice_config_snapshots_call
  ON public.voice_config_snapshots(tenant_id, call_id);

CREATE INDEX idx_voice_safety_findings_call
  ON public.voice_safety_findings(tenant_id, call_id, created_at);

CREATE INDEX idx_voice_safety_findings_status
  ON public.voice_safety_findings(tenant_id, status, severity);

CREATE INDEX idx_voice_call_debug_packets_call
  ON public.voice_call_debug_packets(tenant_id, call_id);

CREATE TRIGGER voice_call_debug_packets_updated_at
  BEFORE UPDATE ON public.voice_call_debug_packets
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
