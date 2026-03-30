-- Callback workflow columns on call_records
-- callback_outcome: owner-selected outcome after reviewing/acting on a call
-- callback_outcome_at: timestamp of the most recent outcome selection

ALTER TABLE public.call_records
  ADD COLUMN IF NOT EXISTS callback_outcome TEXT
    CHECK (callback_outcome IN (
      'reached_customer', 'scheduled', 'left_voicemail', 'no_answer', 'resolved_elsewhere'
    )),
  ADD COLUMN IF NOT EXISTS callback_outcome_at TIMESTAMPTZ;

-- Ensure realtime UPDATE events deliver full row (not just changed columns)
ALTER TABLE public.call_records REPLICA IDENTITY FULL;
