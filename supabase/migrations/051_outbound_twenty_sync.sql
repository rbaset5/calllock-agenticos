-- Add Twenty CRM tracking column to outbound_prospects
ALTER TABLE public.outbound_prospects ADD COLUMN twenty_company_id TEXT;
