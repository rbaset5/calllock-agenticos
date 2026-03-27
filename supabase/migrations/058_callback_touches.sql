-- Normalized callback touch history.
-- Keeps callback_outcome on call_records as latest snapshot while appending
-- each outcome update to callback_touches for timeline display.

CREATE TABLE IF NOT EXISTS public.callback_touches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  call_id text NOT NULL,
  outcome text NOT NULL CHECK (outcome IN (
    'reached_customer',
    'scheduled',
    'left_voicemail',
    'no_answer',
    'resolved_elsewhere'
  )),
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT callback_touches_call_fk
    FOREIGN KEY (tenant_id, call_id)
    REFERENCES public.call_records(tenant_id, call_id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_callback_touches_lookup
  ON public.callback_touches (tenant_id, call_id, created_at DESC);

ALTER TABLE public.callback_touches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.callback_touches FORCE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'callback_touches'
      AND policyname = 'callback_touches_tenant'
  ) THEN
    CREATE POLICY callback_touches_tenant ON public.callback_touches
      USING (tenant_id = public.current_tenant_id());
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.log_callback_touch()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.callback_outcome IS NULL THEN
    RETURN NEW;
  END IF;

  IF TG_OP = 'INSERT'
     OR NEW.callback_outcome IS DISTINCT FROM OLD.callback_outcome
     OR NEW.callback_outcome_at IS DISTINCT FROM OLD.callback_outcome_at THEN
    INSERT INTO public.callback_touches (tenant_id, call_id, outcome, created_at)
    VALUES (
      NEW.tenant_id,
      NEW.call_id,
      NEW.callback_outcome,
      COALESCE(NEW.callback_outcome_at, now())
    );
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS callback_touches_audit ON public.call_records;

CREATE TRIGGER callback_touches_audit
  AFTER INSERT OR UPDATE OF callback_outcome, callback_outcome_at
  ON public.call_records
  FOR EACH ROW
  WHEN (NEW.callback_outcome IS NOT NULL)
  EXECUTE FUNCTION public.log_callback_touch();

-- Backfill from existing snapshot state where no touch history exists yet.
INSERT INTO public.callback_touches (tenant_id, call_id, outcome, created_at)
SELECT
  cr.tenant_id,
  cr.call_id,
  cr.callback_outcome,
  COALESCE(cr.callback_outcome_at, cr.updated_at, cr.created_at)
FROM public.call_records cr
WHERE cr.callback_outcome IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM public.callback_touches ct
    WHERE ct.tenant_id = cr.tenant_id
      AND ct.call_id = cr.call_id
  );
