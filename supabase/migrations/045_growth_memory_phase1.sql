-- Growth Memory Phase 1 tables
-- Per design-doc.md §7.10: Phase 1 requires segment_performance, angle_effectiveness,
-- touchpoint_log, experiment_history, cost_per_acquisition, routing_decision_log,
-- journey_assignments (schema only), loss_records (schema only).
-- Plus: growth_dead_letter_queue (ADR 011), belief_events, and supporting tables.
--
-- All tables are tenant-scoped via RLS using the existing set_tenant_context() pattern
-- from migration 005. Idempotency enforced via UNIQUE constraints per ADR 011.
--
-- Schema evolution policy (design-doc.md §7.10):
--   Phase 1-2: additive only. No column removes, no type changes, no renames.

-- =============================================================================
-- 1. touchpoint_log — append-only source of truth for all interactions
-- Write owner: all components append (multi-writer, each row tagged with source)
-- Partitioned by month for query performance and archival
-- =============================================================================
CREATE TABLE public.touchpoint_log (
    touchpoint_id       UUID PRIMARY KEY,  -- caller MUST supply (no DEFAULT — prevents silent dedup bypass per ADR 011)
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    prospect_id         UUID NOT NULL,
    company_id          UUID,
    touchpoint_type     TEXT NOT NULL,  -- email_sent, email_replied, page_viewed, etc.
    channel             TEXT NOT NULL DEFAULT 'cold_email',
    experiment_id       UUID,
    arm_id              TEXT,
    attribution_token   TEXT,
    signal_quality_score NUMERIC(3,2),
    cost                NUMERIC(10,4) DEFAULT 0,
    metadata            JSONB DEFAULT '{}',
    source_component    TEXT NOT NULL,
    source_version      TEXT NOT NULL,
    seasonal_context    JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    partition_month     TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM')
);

-- Idempotency: touchpoint_id is PK (UUID set by sender per ADR 011)
CREATE INDEX idx_touchpoint_prospect ON public.touchpoint_log (tenant_id, prospect_id, created_at);
CREATE INDEX idx_touchpoint_experiment ON public.touchpoint_log (tenant_id, experiment_id, arm_id) WHERE experiment_id IS NOT NULL;
CREATE INDEX idx_touchpoint_month ON public.touchpoint_log (tenant_id, partition_month);
CREATE INDEX idx_touchpoint_type ON public.touchpoint_log (tenant_id, touchpoint_type, created_at);

-- =============================================================================
-- 2. experiment_history — full experiment lifecycle with outcome data
-- Write owner: Experiment Allocator
-- =============================================================================
CREATE TABLE public.experiment_history (
    experiment_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    wedge_id            TEXT NOT NULL,
    segment             TEXT NOT NULL,
    channel             TEXT NOT NULL DEFAULT 'cold_email',
    lifecycle_stage_scope TEXT,
    arms                JSONB NOT NULL DEFAULT '[]',
    status              TEXT NOT NULL DEFAULT 'exploring'
                        CHECK (status IN ('exploring', 'converging', 'winner_declared', 'retired', 'killed')),
    gate_status         JSONB DEFAULT '{}',
    winner_arm_id       TEXT,
    winner_declared_at  TIMESTAMPTZ,
    seasonal_context    JSONB DEFAULT '{}',
    source_version      TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_experiment_tenant_status ON public.experiment_history (tenant_id, status);
CREATE INDEX idx_experiment_wedge ON public.experiment_history (tenant_id, wedge_id, segment);

-- =============================================================================
-- 3. segment_performance — angle x page x proof --> conversion rates over time
-- Write owner: Experiment Allocator
-- =============================================================================
CREATE TABLE public.segment_performance (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    wedge_id            TEXT NOT NULL,
    segment             TEXT NOT NULL,
    angle               TEXT NOT NULL,
    channel             TEXT NOT NULL DEFAULT 'cold_email',
    page                TEXT,
    proof_asset         TEXT,
    sample_size         INTEGER NOT NULL DEFAULT 0,
    conversion_rate     NUMERIC(5,4) DEFAULT 0,
    cost_per_conversion NUMERIC(10,2),
    confidence          NUMERIC(3,2) DEFAULT 0,
    seasonal_context    JSONB DEFAULT '{}',
    source_version      TEXT NOT NULL,
    version             INTEGER NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, wedge_id, segment, angle, channel, page, proof_asset)
);

-- Upsert on the UNIQUE key with version counter for conflict detection (§7.10)
CREATE INDEX idx_segperf_lookup ON public.segment_performance (tenant_id, wedge_id, segment);

-- =============================================================================
-- 4. angle_effectiveness — angle --> performance by segment, decay detection
-- Write owner: Experiment Allocator
-- =============================================================================
CREATE TABLE public.angle_effectiveness (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    wedge_id            TEXT NOT NULL,
    angle               TEXT NOT NULL,
    segment             TEXT NOT NULL,
    channel             TEXT NOT NULL DEFAULT 'cold_email',
    effectiveness_score NUMERIC(5,4) DEFAULT 0,
    sample_size         INTEGER NOT NULL DEFAULT 0,
    decay_detected      BOOLEAN DEFAULT false,
    decay_rate          NUMERIC(5,4),
    seasonal_context    JSONB DEFAULT '{}',
    source_version      TEXT NOT NULL,
    version             INTEGER NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, wedge_id, angle, segment, channel)
);

CREATE INDEX idx_angle_lookup ON public.angle_effectiveness (tenant_id, wedge_id, segment);

-- =============================================================================
-- 5. cost_per_acquisition — experiment x arm x channel --> cost breakdown
-- Write owner: Cost Layer
-- =============================================================================
CREATE TABLE public.cost_per_acquisition (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    experiment_id       UUID REFERENCES public.experiment_history(experiment_id),
    arm_id              TEXT,
    channel             TEXT NOT NULL DEFAULT 'cold_email',
    enrichment_cost     NUMERIC(10,4) DEFAULT 0,
    asset_creation_cost NUMERIC(10,4) DEFAULT 0,
    send_cost           NUMERIC(10,4) DEFAULT 0,
    human_review_cost   NUMERIC(10,4) DEFAULT 0,
    total_cost_per_meeting NUMERIC(10,2),
    total_cost_per_pilot   NUMERIC(10,2),
    seasonal_context    JSONB DEFAULT '{}',
    source_version      TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, experiment_id, arm_id, channel)
);

CREATE INDEX idx_cost_experiment ON public.cost_per_acquisition (tenant_id, experiment_id);

-- =============================================================================
-- 6. routing_decision_log — append-only routing decisions with full context
-- Write owner: Message Router + Page Router
-- =============================================================================
CREATE TABLE public.routing_decision_log (
    decision_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    prospect_id         UUID NOT NULL,
    lifecycle_state     TEXT NOT NULL,
    channel             TEXT NOT NULL DEFAULT 'cold_email',
    inputs              JSONB NOT NULL,   -- segment, experiment, thompson scores, etc.
    outputs             JSONB NOT NULL,   -- template, angle, page, proof, slots
    gates_passed        JSONB DEFAULT '{}',
    source_version      TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Idempotency: decision_id is PK (UUID set by caller)
CREATE INDEX idx_routing_prospect ON public.routing_decision_log (tenant_id, prospect_id, created_at);
CREATE INDEX idx_routing_experiment ON public.routing_decision_log (tenant_id, created_at)
    WHERE (inputs->>'experiment_id') IS NOT NULL;

-- =============================================================================
-- 7. journey_assignments — active journey state per prospect (schema only in Phase 1)
-- Write owner: Journey Orchestrator
-- =============================================================================
CREATE TABLE public.journey_assignments (
    journey_assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    prospect_id         UUID NOT NULL,
    journey_id          TEXT NOT NULL,
    experiment_id       UUID,
    arm_id              TEXT,
    current_step        INTEGER NOT NULL DEFAULT 1,
    total_steps         INTEGER NOT NULL,
    step_history        JSONB DEFAULT '[]',
    adaptive_modifications JSONB DEFAULT '[]',
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'completed', 'archived', 'paused')),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    next_step_due_at    TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    seasonal_context    JSONB DEFAULT '{}',
    source_version      TEXT NOT NULL,
    UNIQUE (tenant_id, prospect_id, status) -- one active journey per prospect
);

CREATE INDEX idx_journey_active ON public.journey_assignments (tenant_id, status, next_step_due_at)
    WHERE status = 'active';

-- =============================================================================
-- 8. loss_records — structured loss reasons with cross-references (schema only in Phase 1)
-- Write owner: Lifecycle State Machine (on LOST transition)
-- =============================================================================
CREATE TABLE public.loss_records (
    loss_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    prospect_id         UUID NOT NULL,
    lifecycle_transition TEXT NOT NULL,
    loss_reason         TEXT NOT NULL
                        CHECK (loss_reason IN ('price', 'competitor', 'timing', 'no_need',
                                               'bad_fit', 'feature_gap', 'trust', 'unknown')),
    loss_reason_detail  TEXT,
    competitor_name     TEXT,
    experiment_id       UUID,
    arm_id              TEXT,
    segment             TEXT,
    geographic_context  JSONB DEFAULT '{}',
    days_in_pipeline    INTEGER,
    touches_before_loss INTEGER,
    last_angle          TEXT,
    last_proof_asset    TEXT,
    recoverable         BOOLEAN DEFAULT false,
    recovery_eligible_after TIMESTAMPTZ,
    seasonal_context    JSONB DEFAULT '{}',
    source_version      TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, prospect_id, lifecycle_transition)
);

CREATE INDEX idx_loss_reason ON public.loss_records (tenant_id, loss_reason);
CREATE INDEX idx_loss_recoverable ON public.loss_records (tenant_id, recovery_eligible_after)
    WHERE recoverable = true;

-- =============================================================================
-- 9. belief_events — inferred belief shifts per touchpoint (derived layer)
-- Write owner: Belief Layer
-- =============================================================================
CREATE TABLE public.belief_events (
    belief_event_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    source_touchpoint_id UUID NOT NULL,
    prospect_id         UUID NOT NULL,
    touchpoint_type     TEXT NOT NULL,
    belief_shift        TEXT NOT NULL CHECK (belief_shift IN ('up', 'down', 'flat', 'unknown')),
    confidence          NUMERIC(3,2) NOT NULL DEFAULT 0,
    signal_map_version  TEXT NOT NULL,
    source_version      TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source_touchpoint_id)  -- idempotent on touchpoint per ADR 011
);

CREATE INDEX idx_belief_prospect ON public.belief_events (tenant_id, prospect_id, created_at);
CREATE INDEX idx_belief_shift ON public.belief_events (tenant_id, belief_shift, confidence)
    WHERE confidence >= 0.3;  -- only actionable beliefs

-- =============================================================================
-- 10. insight_log — append-only multi-writer insight store
-- Write owner: multiple (Growth Advisor, Combination Discovery, Content Intelligence, etc.)
-- =============================================================================
CREATE TABLE public.insight_log (
    insight_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    source_component    TEXT NOT NULL,
    insight_type        TEXT NOT NULL,
    supersedes_insight_id UUID REFERENCES public.insight_log(insight_id),
    content             JSONB NOT NULL,
    confidence          NUMERIC(3,2) DEFAULT 0,
    review_status       TEXT NOT NULL DEFAULT 'pending'
                        CHECK (review_status IN ('pending', 'approved', 'rejected', 'expired')),
    reviewed_by         TEXT,
    reviewed_at         TIMESTAMPTZ,
    source_version      TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_insight_type ON public.insight_log (tenant_id, insight_type, created_at);
CREATE INDEX idx_insight_pending ON public.insight_log (tenant_id, review_status, created_at)
    WHERE review_status = 'pending';

-- =============================================================================
-- 11. growth_dead_letter_queue — unrecoverable events (ADR 011)
-- =============================================================================
CREATE TABLE public.growth_dead_letter_queue (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    event_type          TEXT NOT NULL,
    event_payload       JSONB NOT NULL,
    error_class         TEXT NOT NULL,
    error_message       TEXT,
    retry_count         INTEGER NOT NULL DEFAULT 0,
    max_retries         INTEGER NOT NULL DEFAULT 3,
    source_version      TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at         TIMESTAMPTZ,
    resolution          TEXT CHECK (resolution IN ('replayed', 'discarded', 'manual')),
    resolved_by         TEXT
);

CREATE INDEX idx_dlq_unresolved ON public.growth_dead_letter_queue (tenant_id, created_at)
    WHERE resolved_at IS NULL;

-- =============================================================================
-- 12. founder_overrides — rejected recommendations + reasoning (training signal)
-- Write owner: Founder Review UI
-- =============================================================================
CREATE TABLE public.founder_overrides (
    override_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    recommendation_id   UUID,  -- references insight_log if applicable
    original_recommendation JSONB NOT NULL,
    override_action     TEXT NOT NULL CHECK (override_action IN ('rejected', 'modified', 'deferred')),
    rejection_reason    TEXT CHECK (rejection_reason IN ('data_wrong', 'timing_wrong', 'strategy_wrong', 'other')),
    rejection_detail    TEXT,
    override_value      JSONB,  -- what the founder chose instead
    source_version      TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_override_tenant ON public.founder_overrides (tenant_id, created_at);

-- =============================================================================
-- 13. wedge_fitness_snapshots — weekly composite score per wedge (ADR 014)
-- Write owner: Growth Advisor (weekly batch)
-- =============================================================================
CREATE TABLE public.wedge_fitness_snapshots (
    snapshot_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    wedge               TEXT NOT NULL,
    snapshot_week       DATE NOT NULL,            -- Monday of the reporting week (stable dedup key)
    score               NUMERIC(5,2) NOT NULL,   -- composite 0-100
    component_scores    JSONB NOT NULL,           -- 9 component scores + cold_start flags
    gates_status        JSONB NOT NULL,           -- automation_eligible, closed_loop_eligible, etc.
    blocking_gaps       JSONB DEFAULT '[]',       -- human-readable reasons for blocked gates
    launch_recommendation TEXT,
    source_version      TEXT NOT NULL,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),  -- actual execution time (observability only)
    UNIQUE (tenant_id, wedge, snapshot_week)      -- one snapshot per wedge per reporting week
);

CREATE INDEX idx_wedge_fitness_latest ON public.wedge_fitness_snapshots (tenant_id, wedge, snapshot_week DESC);

-- =============================================================================
-- RLS policies for all new tables
-- Uses the same pattern as migration 005
-- =============================================================================
ALTER TABLE public.touchpoint_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.touchpoint_log FORCE ROW LEVEL SECURITY;
ALTER TABLE public.experiment_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.experiment_history FORCE ROW LEVEL SECURITY;
ALTER TABLE public.segment_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.segment_performance FORCE ROW LEVEL SECURITY;
ALTER TABLE public.angle_effectiveness ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.angle_effectiveness FORCE ROW LEVEL SECURITY;
ALTER TABLE public.cost_per_acquisition ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cost_per_acquisition FORCE ROW LEVEL SECURITY;
ALTER TABLE public.routing_decision_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.routing_decision_log FORCE ROW LEVEL SECURITY;
ALTER TABLE public.journey_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.journey_assignments FORCE ROW LEVEL SECURITY;
ALTER TABLE public.loss_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.loss_records FORCE ROW LEVEL SECURITY;
ALTER TABLE public.belief_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.belief_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.insight_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.insight_log FORCE ROW LEVEL SECURITY;
ALTER TABLE public.growth_dead_letter_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.growth_dead_letter_queue FORCE ROW LEVEL SECURITY;
ALTER TABLE public.founder_overrides ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.founder_overrides FORCE ROW LEVEL SECURITY;
ALTER TABLE public.wedge_fitness_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wedge_fitness_snapshots FORCE ROW LEVEL SECURITY;

CREATE POLICY touchpoint_log_isolation ON public.touchpoint_log
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY experiment_history_isolation ON public.experiment_history
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY segment_performance_isolation ON public.segment_performance
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY angle_effectiveness_isolation ON public.angle_effectiveness
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY cost_per_acquisition_isolation ON public.cost_per_acquisition
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY routing_decision_log_isolation ON public.routing_decision_log
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY journey_assignments_isolation ON public.journey_assignments
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY loss_records_isolation ON public.loss_records
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY belief_events_isolation ON public.belief_events
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY insight_log_isolation ON public.insight_log
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY growth_dlq_isolation ON public.growth_dead_letter_queue
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY founder_overrides_isolation ON public.founder_overrides
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY wedge_fitness_snapshots_isolation ON public.wedge_fitness_snapshots
    USING (tenant_id = public.current_tenant_id());
