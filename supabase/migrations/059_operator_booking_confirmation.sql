ALTER TABLE call_records
  ADD COLUMN booking_status TEXT DEFAULT NULL,
  ADD COLUMN booking_status_at TIMESTAMPTZ DEFAULT NULL,
  ADD COLUMN booking_notes TEXT DEFAULT NULL;

-- Helper for safe JSONB key update (avoids overwriting entire extracted_fields)
CREATE OR REPLACE FUNCTION update_extracted_field(
  p_call_id TEXT,
  p_key TEXT,
  p_value TEXT
) RETURNS void AS $$
BEGIN
  UPDATE call_records
  SET extracted_fields = jsonb_set(
    COALESCE(extracted_fields, '{}'::jsonb),
    ARRAY[p_key],
    to_jsonb(p_value)
  )
  WHERE call_id = p_call_id;
END;
$$ LANGUAGE plpgsql;
