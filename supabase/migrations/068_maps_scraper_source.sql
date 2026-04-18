-- Allow 'maps_scraper' as a valid source for outbound_prospects.
-- Maps scraper pulls HVAC shops from Google Maps via gosom/google-maps-scraper
-- for the Week 1 Cohort A discovery experiment (4.0-4.5 stars, 50-100 reviews).
--
-- CRITICAL: This migration preserves 'lsa_discovery' which was added in
-- migration 065. Dropping it would orphan all existing LSA prospects.
ALTER TABLE outbound_prospects DROP CONSTRAINT IF EXISTS outbound_prospects_source_check;
ALTER TABLE outbound_prospects ADD CONSTRAINT outbound_prospects_source_check
    CHECK (source IN ('leads_db', 'google_places', 'manual', 'lsa_discovery', 'maps_scraper'));
