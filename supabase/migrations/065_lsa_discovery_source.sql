-- Allow 'lsa_discovery' as a valid source for outbound_prospects.
-- LSA businesses are confirmed Google Local Services advertisers discovered via SerpAPI.
ALTER TABLE outbound_prospects DROP CONSTRAINT IF EXISTS outbound_prospects_source_check;
ALTER TABLE outbound_prospects ADD CONSTRAINT outbound_prospects_source_check
    CHECK (source IN ('leads_db', 'google_places', 'manual', 'lsa_discovery'));
