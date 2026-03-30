-- Outbound lifecycle automation support.
-- Adds updated_at tracking to outbound_prospects and RPC functions
-- for cross-table lifecycle queries (callbacks, strikes, voicemail requeue).

-- 1. Add updated_at column with auto-trigger
ALTER TABLE public.outbound_prospects
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE OR REPLACE FUNCTION public.set_outbound_prospect_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_outbound_prospect_updated_at ON public.outbound_prospects;
CREATE TRIGGER trg_outbound_prospect_updated_at
  BEFORE UPDATE ON public.outbound_prospects
  FOR EACH ROW
  EXECUTE FUNCTION public.set_outbound_prospect_updated_at();

-- 2. Add indexes for lifecycle queries
CREATE INDEX IF NOT EXISTS idx_outbound_calls_outcome
  ON public.outbound_calls (tenant_id, outcome);
CREATE INDEX IF NOT EXISTS idx_outbound_calls_called_at
  ON public.outbound_calls (tenant_id, called_at DESC);
CREATE INDEX IF NOT EXISTS idx_outbound_calls_callback_date
  ON public.outbound_calls (tenant_id, callback_date)
  WHERE callback_date IS NOT NULL;

-- 3. RPC: list_due_callbacks
-- Returns prospects with callbacks due today (or earlier today).
-- Joins outbound_calls (where callback_date lives) with outbound_prospects (where stage lives).
-- Uses DISTINCT ON to get the most recent callback per prospect.
CREATE OR REPLACE FUNCTION public.list_due_callbacks(
  p_tenant_id UUID,
  p_today DATE
)
RETURNS TABLE(
  prospect_id UUID,
  business_name TEXT,
  phone TEXT,
  phone_normalized TEXT,
  metro TEXT,
  timezone TEXT,
  total_score INTEGER,
  callback_date DATE,
  called_at TIMESTAMPTZ,
  notes TEXT
)
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT DISTINCT ON (c.prospect_id)
    p.id,
    p.business_name,
    p.phone,
    p.phone_normalized,
    p.metro,
    p.timezone,
    p.total_score,
    c.callback_date,
    c.called_at,
    c.notes
  FROM public.outbound_calls c
  JOIN public.outbound_prospects p
    ON p.id = c.prospect_id AND p.tenant_id = c.tenant_id
  WHERE c.tenant_id = p_tenant_id
    AND c.outcome = 'answered_callback'
    AND c.callback_date <= p_today
    AND p.stage = 'callback'
  ORDER BY c.prospect_id, c.called_at DESC;
$$;

-- 4. RPC: list_overdue_callbacks
-- Returns prospects with callbacks overdue by more than a given number of days.
CREATE OR REPLACE FUNCTION public.list_overdue_callbacks(
  p_tenant_id UUID,
  p_today DATE,
  p_grace_days INTEGER DEFAULT 3
)
RETURNS TABLE(
  prospect_id UUID,
  business_name TEXT,
  phone TEXT,
  metro TEXT,
  stage TEXT,
  callback_date DATE,
  days_overdue INTEGER
)
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT DISTINCT ON (c.prospect_id)
    p.id,
    p.business_name,
    p.phone,
    p.metro,
    p.stage,
    c.callback_date,
    (p_today - c.callback_date)::INTEGER AS days_overdue
  FROM public.outbound_calls c
  JOIN public.outbound_prospects p
    ON p.id = c.prospect_id AND p.tenant_id = c.tenant_id
  WHERE c.tenant_id = p_tenant_id
    AND c.outcome = 'answered_callback'
    AND c.callback_date < (p_today - p_grace_days)
    AND p.stage = 'callback'
  ORDER BY c.prospect_id, c.called_at DESC;
$$;

-- 5. RPC: list_recent_no_answer_strikes
-- Returns prospects whose N most recent calls are ALL no_answer,
-- excluding prospects with any prior answered_interested outcome (warm-lead protection).
-- Only considers prospects in call_ready or called stage.
CREATE OR REPLACE FUNCTION public.list_recent_no_answer_strikes(
  p_tenant_id UUID,
  p_min_strikes INTEGER DEFAULT 3
)
RETURNS TABLE(
  prospect_id UUID,
  business_name TEXT,
  phone TEXT,
  stage TEXT,
  consecutive_no_answer BIGINT,
  last_no_answer_at TIMESTAMPTZ
)
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  WITH ranked_calls AS (
    SELECT
      c.prospect_id,
      c.outcome,
      c.called_at,
      ROW_NUMBER() OVER (PARTITION BY c.prospect_id ORDER BY c.called_at DESC) AS rn
    FROM public.outbound_calls c
    WHERE c.tenant_id = p_tenant_id
  ),
  recent_streak AS (
    SELECT
      prospect_id,
      COUNT(*) AS consecutive_no_answer,
      MAX(called_at) AS last_no_answer_at
    FROM ranked_calls
    WHERE rn <= p_min_strikes
      AND outcome = 'no_answer'
    GROUP BY prospect_id
    HAVING COUNT(*) = p_min_strikes
  ),
  warm_leads AS (
    SELECT DISTINCT prospect_id
    FROM public.outbound_calls
    WHERE tenant_id = p_tenant_id
      AND outcome = 'answered_interested'
  )
  SELECT
    p.id,
    p.business_name,
    p.phone,
    p.stage,
    rs.consecutive_no_answer,
    rs.last_no_answer_at
  FROM recent_streak rs
  JOIN public.outbound_prospects p ON p.id = rs.prospect_id AND p.tenant_id = p_tenant_id
  WHERE p.stage IN ('call_ready', 'called')
    AND rs.prospect_id NOT IN (SELECT prospect_id FROM warm_leads);
$$;

-- 6. RPC: list_voicemail_requeue_candidates
-- Returns prospects who received a voicemail N+ calendar days ago
-- and are still in 'called' stage (not yet requeued or progressed).
CREATE OR REPLACE FUNCTION public.list_voicemail_requeue_candidates(
  p_tenant_id UUID,
  p_min_days INTEGER DEFAULT 3
)
RETURNS TABLE(
  prospect_id UUID,
  business_name TEXT,
  phone TEXT,
  metro TEXT,
  stage TEXT,
  voicemail_at TIMESTAMPTZ,
  days_since INTEGER
)
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT DISTINCT ON (c.prospect_id)
    p.id,
    p.business_name,
    p.phone,
    p.metro,
    p.stage,
    c.called_at AS voicemail_at,
    (current_date - c.called_at::date)::INTEGER AS days_since
  FROM public.outbound_calls c
  JOIN public.outbound_prospects p
    ON p.id = c.prospect_id AND p.tenant_id = c.tenant_id
  WHERE c.tenant_id = p_tenant_id
    AND c.outcome = 'voicemail_left'
    AND c.called_at < (now() - (p_min_days || ' days')::INTERVAL)
    AND p.stage = 'called'
  ORDER BY c.prospect_id, c.called_at DESC;
$$;

-- 7. RPC: list_cooling_leads
-- Returns prospects in 'interested' stage for 5+ days with no demo scheduled.
CREATE OR REPLACE FUNCTION public.list_cooling_leads(
  p_tenant_id UUID,
  p_stale_days INTEGER DEFAULT 5
)
RETURNS TABLE(
  prospect_id UUID,
  business_name TEXT,
  phone TEXT,
  metro TEXT,
  days_since_interested INTEGER,
  has_demo BOOLEAN
)
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT
    p.id,
    p.business_name,
    p.phone,
    p.metro,
    (current_date - p.updated_at::date)::INTEGER AS days_since_interested,
    EXISTS (
      SELECT 1 FROM public.outbound_calls c
      WHERE c.prospect_id = p.id
        AND c.tenant_id = p_tenant_id
        AND c.demo_scheduled = true
    ) AS has_demo
  FROM public.outbound_prospects p
  WHERE p.tenant_id = p_tenant_id
    AND p.stage = 'interested'
    AND p.updated_at < (now() - (p_stale_days || ' days')::INTERVAL)
    AND NOT EXISTS (
      SELECT 1 FROM public.outbound_calls c
      WHERE c.prospect_id = p.id
        AND c.tenant_id = p_tenant_id
        AND c.demo_scheduled = true
    );
$$;

-- 8. RPC: today_call_stats
-- Returns aggregate stats for calls made today (or a given date).
CREATE OR REPLACE FUNCTION public.today_call_stats(
  p_tenant_id UUID,
  p_date DATE DEFAULT CURRENT_DATE
)
RETURNS TABLE(
  total_calls BIGINT,
  answered BIGINT,
  interested BIGINT,
  not_interested BIGINT,
  callbacks BIGINT,
  voicemails BIGINT,
  no_answers BIGINT,
  wrong_numbers BIGINT,
  demos_scheduled BIGINT
)
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT
    COUNT(*)::BIGINT AS total_calls,
    COUNT(*) FILTER (WHERE outcome LIKE 'answered_%')::BIGINT AS answered,
    COUNT(*) FILTER (WHERE outcome = 'answered_interested')::BIGINT AS interested,
    COUNT(*) FILTER (WHERE outcome = 'answered_not_interested')::BIGINT AS not_interested,
    COUNT(*) FILTER (WHERE outcome = 'answered_callback')::BIGINT AS callbacks,
    COUNT(*) FILTER (WHERE outcome = 'voicemail_left')::BIGINT AS voicemails,
    COUNT(*) FILTER (WHERE outcome = 'no_answer')::BIGINT AS no_answers,
    COUNT(*) FILTER (WHERE outcome = 'wrong_number')::BIGINT AS wrong_numbers,
    COUNT(*) FILTER (WHERE demo_scheduled = true)::BIGINT AS demos_scheduled
  FROM public.outbound_calls
  WHERE tenant_id = p_tenant_id
    AND called_at >= p_date::TIMESTAMPTZ
    AND called_at < (p_date + 1)::TIMESTAMPTZ;
$$;

-- 9. Revoke public execute on lifecycle RPCs (prevent tenant bypass via SECURITY DEFINER)
REVOKE EXECUTE ON FUNCTION public.list_due_callbacks(UUID, DATE) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.list_overdue_callbacks(UUID, DATE, INTEGER) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.list_recent_no_answer_strikes(UUID, INTEGER) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.list_voicemail_requeue_candidates(UUID, INTEGER) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.list_cooling_leads(UUID, INTEGER) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.today_call_stats(UUID, DATE) FROM PUBLIC;
