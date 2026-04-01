CREATE TABLE IF NOT EXISTS public.outbound_call_hud_sessions (
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    twilio_call_sid TEXT NOT NULL,
    prospect_id UUID REFERENCES public.outbound_prospects(id) ON DELETE SET NULL,
    hud_session JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, twilio_call_sid)
);

CREATE INDEX IF NOT EXISTS idx_outbound_call_hud_sessions_prospect
    ON public.outbound_call_hud_sessions (prospect_id);

ALTER TABLE public.outbound_call_hud_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.outbound_call_hud_sessions FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS outbound_call_hud_sessions_isolation ON public.outbound_call_hud_sessions;
CREATE POLICY outbound_call_hud_sessions_isolation ON public.outbound_call_hud_sessions
    USING (tenant_id = public.current_tenant_id());
