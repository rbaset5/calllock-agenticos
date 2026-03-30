-- Outbound Pipeline tables
-- Internal-only prospecting tables for the CallLock outbound scout.
-- All tables are tenant-scoped via RLS using the existing set_tenant_context() pattern.

INSERT INTO public.tenants (id, slug, name, industry_pack_id, status)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'calllock-internal',
    'CallLock Internal',
    'hvac',
    'active'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.tenant_configs (tenant_id)
VALUES ('00000000-0000-0000-0000-000000000001')
ON CONFLICT (tenant_id) DO NOTHING;

CREATE TABLE public.outbound_prospects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id),
    business_name TEXT NOT NULL,
    trade TEXT NOT NULL
        CHECK (trade IN ('hvac', 'plumbing')),
    metro TEXT,
    website TEXT,
    address TEXT,
    phone TEXT,
    phone_normalized TEXT NOT NULL,
    source TEXT NOT NULL
        CHECK (source IN ('leads_db', 'google_places', 'manual')),
    source_listing_id TEXT,
    timezone TEXT,
    raw_source JSONB NOT NULL DEFAULT '{}'::jsonb,
    total_score INTEGER NOT NULL DEFAULT 0,
    score_tier TEXT NOT NULL DEFAULT 'unscored'
        CHECK (score_tier IN ('unscored', 'a_lead', 'b_lead', 'c_lead', 'disqualified')),
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    stage TEXT NOT NULL DEFAULT 'discovered'
        CHECK (stage IN ('discovered', 'validated', 'scored', 'tested', 'call_ready', 'called',
                         'interested', 'callback', 'converted', 'disqualified')),
    disqualification_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, phone_normalized)
);

CREATE TABLE public.prospect_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id),
    prospect_id UUID NOT NULL REFERENCES public.outbound_prospects(id) ON DELETE CASCADE,
    signal_type TEXT NOT NULL,
    signal_tier INTEGER NOT NULL,
    raw_evidence JSONB DEFAULT '{}'::jsonb,
    score INTEGER NOT NULL DEFAULT 0,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.prospect_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id),
    prospect_id UUID NOT NULL REFERENCES public.outbound_prospects(id) ON DELETE CASCADE,
    dimension_scores JSONB NOT NULL,
    total_score INTEGER NOT NULL,
    tier TEXT NOT NULL
        CHECK (tier IN ('a_lead', 'b_lead', 'c_lead', 'disqualified')),
    rubric_hash TEXT NOT NULL,
    scored_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.call_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id),
    prospect_id UUID NOT NULL REFERENCES public.outbound_prospects(id) ON DELETE CASCADE,
    twilio_call_sid TEXT NOT NULL,
    called_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    day_of_week TEXT NOT NULL,
    local_time TEXT NOT NULL,
    result TEXT NOT NULL
        CHECK (result IN ('answered_human', 'voicemail', 'no_answer', 'busy', 'uncertain', 'failed')),
    amd_status TEXT,
    ring_duration_ms INTEGER
);

CREATE TABLE public.outbound_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id UUID NOT NULL REFERENCES public.outbound_prospects(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES public.tenants(id),
    twilio_call_sid TEXT NOT NULL,
    called_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    outcome TEXT NOT NULL
        CHECK (outcome IN ('answered_interested', 'answered_not_interested', 'answered_callback',
                           'voicemail_left', 'no_answer', 'wrong_number', 'gatekeeper_blocked')),
    notes TEXT,
    call_hook_used TEXT,
    demo_scheduled BOOLEAN DEFAULT false,
    callback_date DATE,
    growth_memory_id UUID,
    recording_url TEXT,
    transcript TEXT,
    UNIQUE (tenant_id, twilio_call_sid)
);

CREATE INDEX idx_prospect_signals_prospect ON public.prospect_signals (prospect_id);
CREATE INDEX idx_prospect_scores_prospect ON public.prospect_scores (prospect_id);
CREATE INDEX idx_call_tests_prospect ON public.call_tests (prospect_id);
CREATE INDEX idx_outbound_calls_prospect ON public.outbound_calls (prospect_id);
CREATE INDEX idx_outbound_prospects_call_list ON public.outbound_prospects (tenant_id, stage, total_score DESC);
CREATE INDEX idx_outbound_prospects_probe ON public.outbound_prospects (tenant_id, stage, score_tier, timezone);

ALTER TABLE public.outbound_prospects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.outbound_prospects FORCE ROW LEVEL SECURITY;
ALTER TABLE public.prospect_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prospect_signals FORCE ROW LEVEL SECURITY;
ALTER TABLE public.prospect_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prospect_scores FORCE ROW LEVEL SECURITY;
ALTER TABLE public.call_tests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.call_tests FORCE ROW LEVEL SECURITY;
ALTER TABLE public.outbound_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.outbound_calls FORCE ROW LEVEL SECURITY;

CREATE POLICY outbound_prospects_isolation ON public.outbound_prospects
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY prospect_signals_isolation ON public.prospect_signals
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY prospect_scores_isolation ON public.prospect_scores
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY call_tests_isolation ON public.call_tests
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY outbound_calls_isolation ON public.outbound_calls
    USING (tenant_id = public.current_tenant_id());
