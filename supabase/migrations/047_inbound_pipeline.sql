-- Inbound Pipeline tables
-- Per inbound-pipeline-integration-design.md §2, §9, §10, §13:
--   inbound_messages, inbound_drafts, inbound_stage_log, poll_checkpoints,
--   enrichment_cache, prospect_emails, email_accounts.
--
-- All tables are tenant-scoped via RLS using the existing set_tenant_context() pattern
-- from migration 005. Follows the same ENABLE/FORCE/CREATE POLICY pattern as 046.
--
-- Schema evolution policy: additive only (consistent with 046).

-- =============================================================================
-- 1. inbound_messages — raw ingested messages with quarantine + scoring results
-- Write owner: Inbound Pipeline (sole writer)
-- Scoring data denormalized onto message row (spec §9 design note)
-- =============================================================================
CREATE TABLE public.inbound_messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    account_id          TEXT NOT NULL,
    rfc_message_id      TEXT NOT NULL,
    thread_id           TEXT NOT NULL,
    imap_uid            INTEGER NOT NULL,
    from_addr           TEXT NOT NULL,
    from_domain         TEXT NOT NULL,
    to_addr             TEXT NOT NULL,
    subject             TEXT NOT NULL,
    received_at         TIMESTAMPTZ NOT NULL,
    body_text           TEXT NOT NULL,
    source              TEXT NOT NULL DEFAULT 'organic'
                        CHECK (source IN ('organic', 'reply')),
    quarantine_status   TEXT NOT NULL
                        CHECK (quarantine_status IN ('clean', 'blocked', 'pending_scoring')),
    quarantine_flags    JSONB DEFAULT '[]',
    quarantine_reason   TEXT,
    prospect_id         UUID,
    scoring_status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK (scoring_status IN ('pending', 'scored', 'failed', 'skipped')),
    action              TEXT,
    total_score         INTEGER,
    score_dimensions    JSONB DEFAULT '{}',
    score_reasoning     TEXT,
    rubric_hash         TEXT,
    stage               TEXT DEFAULT 'new'
                        CHECK (stage IN ('new', 'qualified', 'engaged', 'negotiation', 'won', 'lost', 'archived')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, rfc_message_id)
);

CREATE INDEX idx_inbound_msg_domain ON public.inbound_messages (tenant_id, from_domain);
CREATE INDEX idx_inbound_msg_thread ON public.inbound_messages (tenant_id, thread_id);
CREATE INDEX idx_inbound_msg_prospect ON public.inbound_messages (tenant_id, prospect_id)
    WHERE prospect_id IS NOT NULL;
CREATE INDEX idx_inbound_msg_pending ON public.inbound_messages (tenant_id, scoring_status)
    WHERE scoring_status = 'pending';

-- =============================================================================
-- 2. inbound_drafts — generated reply drafts with reviewer verdict
-- Write owner: Inbound Pipeline (sole writer)
-- =============================================================================
CREATE TABLE public.inbound_drafts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    message_id          UUID NOT NULL REFERENCES public.inbound_messages(id),
    thread_id           TEXT NOT NULL,
    action              TEXT NOT NULL,
    template_used       TEXT NOT NULL,
    draft_text          TEXT NOT NULL,
    source              TEXT NOT NULL
                        CHECK (source IN ('llm', 'fallback_template')),
    reviewer_verdict    TEXT,
    content_gate_status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (content_gate_status IN ('passed', 'blocked', 'pending')),
    content_gate_flags  JSONB DEFAULT '[]',
    send_status         TEXT NOT NULL DEFAULT 'pending_review'
                        CHECK (send_status IN ('pending_review', 'approved', 'sent', 'rejected')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, message_id)
);

CREATE INDEX idx_inbound_draft_msg ON public.inbound_drafts (tenant_id, message_id);
CREATE INDEX idx_inbound_draft_review ON public.inbound_drafts (tenant_id, send_status)
    WHERE send_status = 'pending_review';

-- =============================================================================
-- 3. inbound_stage_log — append-only stage transition audit trail
-- Write owner: Inbound Pipeline (sole writer)
-- Per spec §10: stages tracked separately from Growth Memory lifecycle
-- =============================================================================
CREATE TABLE public.inbound_stage_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    message_id          UUID NOT NULL REFERENCES public.inbound_messages(id),
    thread_id           TEXT NOT NULL,
    from_stage          TEXT
                        CHECK (from_stage IS NULL OR from_stage IN ('new', 'qualified', 'engaged', 'negotiation', 'won', 'lost', 'archived')),
    to_stage            TEXT NOT NULL
                        CHECK (to_stage IN ('new', 'qualified', 'engaged', 'negotiation', 'won', 'lost', 'archived')),
    changed_by          TEXT NOT NULL,
    reason              TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_inbound_stage_thread ON public.inbound_stage_log (tenant_id, thread_id, created_at);

-- =============================================================================
-- 4. poll_checkpoints — IMAP UID checkpoint per account/folder
-- Write owner: Inbound Pipeline (sole writer)
-- Composite PK — no UUID, dedup key is (tenant_id, account_id, folder)
-- =============================================================================
CREATE TABLE public.poll_checkpoints (
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    account_id          TEXT NOT NULL,
    folder              TEXT NOT NULL DEFAULT 'INBOX',
    last_uid            INTEGER NOT NULL DEFAULT 0,
    last_polled_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    poll_status         TEXT NOT NULL DEFAULT 'ok'
                        CHECK (poll_status IN ('ok', 'error')),
    last_error          TEXT,
    PRIMARY KEY (tenant_id, account_id, folder)
);

-- =============================================================================
-- 5. enrichment_cache — shared cache for sender research + prospect enrichment
-- Write owner: Inbound Pipeline + Enrichment Agent (multi-writer, discriminated by source)
-- TTL is application-level (spec §9): WHERE fetched_at > now() - interval '7 days'
-- =============================================================================
CREATE TABLE public.enrichment_cache (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    cache_key           TEXT NOT NULL,
    cache_type          TEXT NOT NULL
                        CHECK (cache_type IN ('sender_research', 'prospect_enrichment')),
    source              TEXT NOT NULL
                        CHECK (source IN ('inbound_pipeline', 'enrichment_agent')),
    data                JSONB NOT NULL,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, cache_key, cache_type)
);

CREATE INDEX idx_enrichment_ttl ON public.enrichment_cache (tenant_id, cache_type, fetched_at);

-- =============================================================================
-- 6. prospect_emails — email-to-prospect mapping for reply path lookup
-- Write owner: Sender Agent + Inbound Pipeline (multi-writer, discriminated by source)
-- =============================================================================
CREATE TABLE public.prospect_emails (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    prospect_id         UUID NOT NULL,
    email               TEXT NOT NULL,
    source              TEXT NOT NULL DEFAULT 'outbound'
                        CHECK (source IN ('outbound', 'inbound', 'manual')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, email)
);

CREATE INDEX idx_prospect_email_lookup ON public.prospect_emails (tenant_id, email);
CREATE INDEX idx_prospect_email_prospect ON public.prospect_emails (tenant_id, prospect_id);

-- =============================================================================
-- 7. email_accounts — IMAP credentials (encrypted at application level)
-- Write owner: Admin / onboarding (not written by pipeline)
-- imap_credential encrypted with AES-256-GCM before storage (spec §13)
-- =============================================================================
CREATE TABLE public.email_accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    account_id          TEXT NOT NULL,
    imap_host           TEXT NOT NULL,
    imap_port           INTEGER NOT NULL DEFAULT 993,
    imap_username       TEXT NOT NULL,
    imap_auth_type      TEXT NOT NULL DEFAULT 'password'
                        CHECK (imap_auth_type IN ('password', 'oauth2')),
    imap_credential     TEXT NOT NULL,
    folders             JSONB DEFAULT '["INBOX"]',
    enabled             BOOLEAN NOT NULL DEFAULT true,
    features            JSONB DEFAULT '{"labels": false, "stage_tracking": true, "draft_generation": true, "escalation": true, "auto_archive": true}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, account_id)
);

-- =============================================================================
-- RLS policies for all inbound tables
-- Pattern: ENABLE + FORCE + CREATE POLICY (same as 005/046)
-- =============================================================================
ALTER TABLE public.inbound_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_messages FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_drafts FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_stage_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_stage_log FORCE ROW LEVEL SECURITY;
ALTER TABLE public.poll_checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.poll_checkpoints FORCE ROW LEVEL SECURITY;
ALTER TABLE public.enrichment_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.enrichment_cache FORCE ROW LEVEL SECURITY;
ALTER TABLE public.prospect_emails ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prospect_emails FORCE ROW LEVEL SECURITY;
ALTER TABLE public.email_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.email_accounts FORCE ROW LEVEL SECURITY;

CREATE POLICY inbound_messages_isolation ON public.inbound_messages
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY inbound_drafts_isolation ON public.inbound_drafts
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY inbound_stage_log_isolation ON public.inbound_stage_log
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY poll_checkpoints_isolation ON public.poll_checkpoints
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY enrichment_cache_isolation ON public.enrichment_cache
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY prospect_emails_isolation ON public.prospect_emails
    USING (tenant_id = public.current_tenant_id());
CREATE POLICY email_accounts_isolation ON public.email_accounts
    USING (tenant_id = public.current_tenant_id());
