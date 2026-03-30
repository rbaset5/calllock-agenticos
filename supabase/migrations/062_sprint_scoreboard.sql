-- Sprint scoreboard + dial-started support for Sales Assistant V2.

-- Expand legacy outcome constraint to include dial_started (backward compatibility).
ALTER TABLE public.outbound_calls DROP CONSTRAINT IF EXISTS outbound_calls_outcome_check;
ALTER TABLE public.outbound_calls ADD CONSTRAINT outbound_calls_outcome_check
  CHECK (outcome IN (
    'answered_interested', 'answered_not_interested', 'answered_callback',
    'voicemail_left', 'no_answer', 'wrong_number', 'gatekeeper_blocked',
    'dial_started'
  ));

-- Structured outcome type for richer event semantics.
ALTER TABLE public.outbound_calls
  ADD COLUMN IF NOT EXISTS call_outcome_type TEXT
  CHECK (call_outcome_type IN (
    'answered_interested', 'answered_not_interested', 'answered_callback',
    'voicemail_left', 'no_answer', 'wrong_number', 'gatekeeper_blocked',
    'demo_booked', 'close_attempted', 'callback_scheduled', 'dial_started'
  ));

-- Next-action fields for pipeline review follow-up.
ALTER TABLE public.outbound_prospects
  ADD COLUMN IF NOT EXISTS next_action_date DATE;

ALTER TABLE public.outbound_prospects
  ADD COLUMN IF NOT EXISTS next_action_type TEXT
  CHECK (next_action_type IN (
    'callback', 'close_attempt', 'followup_close', 'demo_to_close',
    'close_or_onboard', NULL
  ));

-- Composite index to speed date-range scoreboard reads.
CREATE INDEX IF NOT EXISTS idx_outbound_calls_tenant_date
  ON public.outbound_calls(tenant_id, called_at);

-- Single-query scoreboard RPC.
CREATE OR REPLACE FUNCTION public.sprint_scoreboard(
  p_tenant_id UUID,
  p_start_date DATE,
  p_today DATE
) RETURNS JSONB
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT jsonb_build_object(
    'daily_dials', COUNT(*) FILTER (
      WHERE called_at::date = p_today
        AND outcome <> 'dial_started'
        AND COALESCE(call_outcome_type, '') <> 'dial_started'
    ),
    'daily_connects', COUNT(*) FILTER (
      WHERE called_at::date = p_today
        AND outcome LIKE 'answered_%'
    ),
    'daily_demos', COUNT(*) FILTER (
      WHERE called_at::date = p_today
        AND demo_scheduled = true
    ),
    'daily_close_attempts', COUNT(*) FILTER (
      WHERE called_at::date = p_today
        AND call_outcome_type = 'close_attempted'
    ),
    'callbacks_completed', COUNT(*) FILTER (
      WHERE called_at::date = p_today
        AND outcome = 'answered_callback'
    ),
    'weekly_dials', COUNT(*) FILTER (
      WHERE called_at::date >= date_trunc('week', p_today::timestamp)::date
        AND called_at::date < (date_trunc('week', p_today::timestamp)::date + 7)
        AND outcome <> 'dial_started'
        AND COALESCE(call_outcome_type, '') <> 'dial_started'
    ),
    'weekly_connects', COUNT(*) FILTER (
      WHERE called_at::date >= date_trunc('week', p_today::timestamp)::date
        AND called_at::date < (date_trunc('week', p_today::timestamp)::date + 7)
        AND outcome LIKE 'answered_%'
    ),
    'weekly_demos', COUNT(*) FILTER (
      WHERE called_at::date >= date_trunc('week', p_today::timestamp)::date
        AND called_at::date < (date_trunc('week', p_today::timestamp)::date + 7)
        AND demo_scheduled = true
    ),
    'total_dials', COUNT(*) FILTER (
      WHERE called_at::date >= p_start_date
        AND outcome <> 'dial_started'
        AND COALESCE(call_outcome_type, '') <> 'dial_started'
    ),
    'total_connects', COUNT(*) FILTER (
      WHERE called_at::date >= p_start_date
        AND outcome LIKE 'answered_%'
    ),
    'total_demos', COUNT(*) FILTER (
      WHERE called_at::date >= p_start_date
        AND demo_scheduled = true
    ),
    'total_closes', COUNT(*) FILTER (
      WHERE called_at::date >= p_start_date
        AND call_outcome_type = 'close_attempted'
    ),
    'customers_signed', (
      SELECT COUNT(*) FROM public.outbound_prospects
      WHERE tenant_id = p_tenant_id AND stage = 'converted'
    )
  )
  FROM public.outbound_calls
  WHERE tenant_id = p_tenant_id;
$$;

REVOKE EXECUTE ON FUNCTION public.sprint_scoreboard(UUID, DATE, DATE) FROM PUBLIC;
