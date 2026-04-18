-- Inbound callbacks to our outbound caller-ID numbers (FL/MI/IL/TX/AZ).
-- Populated by dialer/server.js /inbound/voicemail-complete and /inbound/sms.
-- Conceptually distinct from outbound_prospects: these are people reaching
-- back out to us, not people we're prospecting. Joining is best-effort by
-- from_number against outbound_prospects.phone_number.

CREATE TABLE IF NOT EXISTS public.inbound_missed_calls (
    id              BIGSERIAL PRIMARY KEY,
    kind            TEXT NOT NULL CHECK (kind IN ('voice', 'sms')),
    call_sid        TEXT,           -- NULL for sms; CallSid for voice
    message_sid     TEXT,           -- NULL for voice; MessageSid for sms
    from_number     TEXT NOT NULL,
    to_number       TEXT NOT NULL,  -- which CallLock number they hit
    recording_sid   TEXT,
    recording_url   TEXT,
    duration_seconds INTEGER,
    transcription   TEXT,
    sms_body        TEXT,
    forwarded       BOOLEAN NOT NULL DEFAULT FALSE,  -- did the cell-forward connect?
    handled_at      TIMESTAMPTZ,    -- set when Rashid marks it dealt-with
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS inbound_missed_calls_from_number_idx
    ON public.inbound_missed_calls (from_number);
CREATE INDEX IF NOT EXISTS inbound_missed_calls_created_at_idx
    ON public.inbound_missed_calls (created_at DESC);
CREATE INDEX IF NOT EXISTS inbound_missed_calls_unhandled_idx
    ON public.inbound_missed_calls (created_at DESC) WHERE handled_at IS NULL;
