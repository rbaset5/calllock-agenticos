-- Add AI extraction columns to outbound_calls for post-call analysis.
-- extraction: JSONB holding structured fields (objection_type, pain, temperature, etc.)
-- extraction_status: pipeline state (pending → complete | failed | skipped)
-- extraction_raw_response: raw LLM output for prompt debugging

ALTER TABLE public.outbound_calls
  ADD COLUMN IF NOT EXISTS extraction JSONB,
  ADD COLUMN IF NOT EXISTS extraction_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (extraction_status IN ('pending', 'complete', 'failed', 'skipped')),
  ADD COLUMN IF NOT EXISTS extraction_raw_response TEXT;
