-- Scoring feedback loop: stores results of each feedback analysis run.
-- Tracks signal effectiveness metrics and weight recommendations over time.

CREATE TABLE IF NOT EXISTS public.scoring_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    rubric_hash TEXT NOT NULL,
    run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    total_prospects_analyzed INTEGER NOT NULL,
    positive_count INTEGER NOT NULL,
    negative_count INTEGER NOT NULL,
    inconclusive_count INTEGER NOT NULL,
    base_rate NUMERIC(5,4) NOT NULL,
    dimension_metrics JSONB NOT NULL,
    current_weights JSONB NOT NULL,
    suggested_weights JSONB NOT NULL,
    review_signal_metrics JSONB,
    tier_accuracy JSONB NOT NULL,
    discrimination_score NUMERIC(5,4)
);

CREATE INDEX IF NOT EXISTS idx_scoring_feedback_tenant
    ON public.scoring_feedback (tenant_id, run_at DESC);
