-- Review scanner enrichment columns for outbound prospects
ALTER TABLE outbound_prospects
  ADD COLUMN IF NOT EXISTS review_signals JSONB,
  ADD COLUMN IF NOT EXISTS review_opener TEXT,
  ADD COLUMN IF NOT EXISTS review_enrichment_score INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS desperation_score INTEGER DEFAULT 0;
