const express = require('express');
const cors = require('cors');
const path = require('path');
const twilio = require('twilio');
const { createClient } = require('@supabase/supabase-js');

const OUTBOUND_TENANT_ID = '00000000-0000-0000-0000-000000000001';
const OUTBOUND_CALL_OUTCOME_EVENT = 'outbound/call.outcome-logged';
const OUTBOUND_EXTRACTION_COMPLETE_EVENT = 'outbound/call.extraction-complete';

const app = express();
app.use(cors());
app.use(express.urlencoded({ extended: false }));
app.use(express.json());
app.use(express.static(__dirname, { index: false }));

const {
  TWILIO_ACCOUNT_SID,
  TWILIO_AUTH_TOKEN,
  TWILIO_API_KEY_SID,
  TWILIO_API_KEY_SECRET,
  TWILIO_PHONE_NUMBER,
  TWILIO_TWIML_APP_SID,
  CALL_SERVER_BASE_URL,
  SUPABASE_URL,
  SUPABASE_SERVICE_ROLE_KEY,
  INNGEST_EVENT_URL,
  INNGEST_EVENT_KEY,
  OUTBOUND_SOURCE_VERSION = 'dialer-v1',
  HARNESS_BASE_URL = 'http://localhost:8000',
  HARNESS_EVENT_SECRET = '',
  NODE_ENV = 'development',
  PORT = '3004',
  DEEPGRAM_API_KEY,
  GROQ_API_KEY,
  HUD_INTERNAL_TOKEN,
} = process.env;

const twilioClient = twilio(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN);
const supabase = SUPABASE_URL && SUPABASE_SERVICE_ROLE_KEY
  ? createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
      auth: { autoRefreshToken: false, persistSession: false },
    })
  : null;

const callStore = new Map();

function storeCall(callSid, data) {
  const existing = callStore.get(callSid) || {};
  callStore.set(callSid, { ...existing, ...data, updatedAt: Date.now() });
}

// Twilio webhook signature validation middleware
function validateTwilioSignature(req, res, next) {
  if (!CALL_SERVER_BASE_URL || !TWILIO_AUTH_TOKEN) {
    if (NODE_ENV === 'production') {
      console.error('[security] Twilio validation env vars missing in production');
      return res.sendStatus(500);
    }
    return next(); // skip validation in dev only
  }
  const signature = req.headers['x-twilio-signature'];
  if (!signature) {
    console.warn('[security] Missing Twilio signature on', req.originalUrl);
    return res.sendStatus(403);
  }
  const url = `${CALL_SERVER_BASE_URL}${req.originalUrl}`;
  const valid = twilio.validateRequest(TWILIO_AUTH_TOKEN, signature, url, req.body);
  if (!valid) {
    console.warn('[security] Invalid Twilio signature on', req.originalUrl);
    return res.sendStatus(403);
  }
  next();
}

// Async LLM extraction: POST transcript to harness, update outbound_calls with result
async function runExtractionAsync(callSid, transcript, callData) {
  const prospectContext = {
    business_name: callData.businessName || '',
    metro: callData.metro || '',
    reviews: callData.reviews || '',
  };

  let result;
  try {
    const response = await fetch(`${HARNESS_BASE_URL}/outbound/extract`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(HARNESS_EVENT_SECRET && { Authorization: `Bearer ${HARNESS_EVENT_SECRET}` }),
      },
      body: JSON.stringify({ transcript, prospect_context: prospectContext }),
      signal: AbortSignal.timeout(60000), // 60s timeout for LLM extraction
    });
    if (!response.ok) {
      throw new Error(`Harness returned ${response.status}`);
    }
    result = await response.json();
  } catch (error) {
    console.error(`[extraction] Harness call failed for ${callSid}:`, error.message);
    if (supabase) {
      await supabase.from('outbound_calls')
        .update({ extraction_status: 'failed', extraction_raw_response: error.message })
        .eq('twilio_call_sid', callSid)
        .eq('tenant_id', OUTBOUND_TENANT_ID);
    }
    return;
  }

  if (!supabase) return;

  const patch = {
    extraction: result.extraction || null,
    extraction_status: result.status || 'failed',
    extraction_raw_response: result.raw_response || null,
  };

  const { error } = await supabase.from('outbound_calls')
    .update(patch)
    .eq('twilio_call_sid', callSid)
    .eq('tenant_id', OUTBOUND_TENANT_ID);

  if (error) {
    console.error(`[extraction] Supabase update failed for ${callSid}:`, error.message);
    return;
  }

  console.log(`[extraction] ${result.status} for ${callSid}`);

  // Emit extraction-complete event for Discord notification
  if (result.status === 'complete' && result.extraction) {
    await emitInngestEvent(OUTBOUND_EXTRACTION_COMPLETE_EVENT, {
      tenant_id: OUTBOUND_TENANT_ID,
      prospect_id: callData.prospectId,
      twilio_call_sid: callSid,
      business_name: callData.businessName || '',
      extraction: result.extraction,
      source_version: OUTBOUND_SOURCE_VERSION,
    });
  }
}

setInterval(() => {
  const cutoff = Date.now() - 10 * 60 * 1000;
  for (const [sid, data] of callStore) {
    if (data.updatedAt < cutoff) callStore.delete(sid);
  }
}, 5 * 60 * 1000);

// HUD session store — holds hud_session data for calls that arrive before writeOutcomeRecord
const hudSessionStore = new Map();
const HUD_SESSION_STAGING_TABLE = 'outbound_call_hud_sessions';

// Clean up stale HUD sessions after 30 minutes (same pattern as callStore)
setInterval(() => {
  const cutoff = Date.now() - 30 * 60 * 1000;
  for (const [sid, data] of hudSessionStore) {
    if (data._storedAt && data._storedAt < cutoff) hudSessionStore.delete(sid);
  }
}, 10 * 60 * 1000);

function readCookie(req, name) {
  const header = req.headers.cookie;
  if (!header) return undefined;
  for (const part of header.split(';')) {
    const [rawKey, ...rest] = part.trim().split('=');
    if (rawKey === name) {
      return decodeURIComponent(rest.join('='));
    }
  }
  return undefined;
}

function validateHudToken(req, res, next) {
  if (!HUD_INTERNAL_TOKEN) {
    if (NODE_ENV === 'production') {
      return res.status(500).json({ error: 'HUD auth is not configured' });
    }
    return next();
  }
  const token = req.headers['x-hud-token'] || readCookie(req, 'calllock_hud_token');
  if (token !== HUD_INTERNAL_TOKEN) {
    return res.status(403).json({ error: 'Invalid HUD token' });
  }
  next();
}

function setHudCookie(res) {
  if (!HUD_INTERNAL_TOKEN) return;
  res.cookie('calllock_hud_token', HUD_INTERNAL_TOKEN, {
    httpOnly: true,
    sameSite: 'strict',
    secure: NODE_ENV === 'production',
    path: '/',
  });
}

async function stageHudSession(twilioCallSid, prospectId, hudSession) {
  if (supabase) {
    const { error } = await supabase
      .from(HUD_SESSION_STAGING_TABLE)
      .upsert(
        {
          tenant_id: OUTBOUND_TENANT_ID,
          twilio_call_sid: twilioCallSid,
          prospect_id: prospectId || null,
          hud_session: hudSession,
          updated_at: new Date().toISOString(),
        },
        { onConflict: 'tenant_id,twilio_call_sid' },
      );
    if (error) throw error;
    return;
  }

  hudSessionStore.set(twilioCallSid, {
    hudSession,
    prospectId: prospectId || null,
    _storedAt: Date.now(),
  });
}

async function deleteStagedHudSession(twilioCallSid) {
  if (supabase) {
    const { error } = await supabase
      .from(HUD_SESSION_STAGING_TABLE)
      .delete()
      .eq('tenant_id', OUTBOUND_TENANT_ID)
      .eq('twilio_call_sid', twilioCallSid);
    if (error) {
      console.error('[hud/session] Failed to clear staged session:', error.message);
    }
    return;
  }
  hudSessionStore.delete(twilioCallSid);
}

async function mergePendingHudSession(callSid) {
  if (supabase) {
    const { data, error } = await supabase
      .from(HUD_SESSION_STAGING_TABLE)
      .select('hud_session')
      .eq('tenant_id', OUTBOUND_TENANT_ID)
      .eq('twilio_call_sid', callSid)
      .limit(1);

    if (error) {
      console.error('[hud/session] Failed to load staged session:', error.message);
      return false;
    }

    const pendingHud = data?.[0]?.hud_session;
    if (!pendingHud) return false;

    const { error: updateError } = await supabase
      .from('outbound_calls')
      .update({ hud_session: pendingHud })
      .eq('twilio_call_sid', callSid)
      .eq('tenant_id', OUTBOUND_TENANT_ID);

    if (updateError) {
      console.error('[hud/session] Failed to merge staged session:', updateError.message);
      return false;
    }

    await deleteStagedHudSession(callSid);
    console.log(`[hud/session] Merged staged hud_session for ${callSid}`);
    return true;
  }

  const pendingHud = hudSessionStore.get(callSid);
  if (!pendingHud || !pendingHud.hudSession) return false;
  hudSessionStore.delete(callSid);
  return false;
}

function topSignals(signals = []) {
  return [...signals]
    .sort((left, right) => {
      if ((right.signal_tier || 0) !== (left.signal_tier || 0)) {
        return (left.signal_tier || 0) - (right.signal_tier || 0);
      }
      return (right.score || 0) - (left.score || 0);
    })
    .slice(0, 3);
}

function summarizeSignals(signalRows = [], callTests = []) {
  const labels = {
    paid_demand: 'paid demand active',
    after_hours_behavior: 'after-hours leakage',
    no_backup_intake: 'no backup intake',
    hours_mismatch: 'hours mismatch',
    owner_operated: 'owner-operated',
    no_admin_layer: 'no admin layer',
    review_pain: 'review pain',
    simple_ivr: 'simple IVR',
  };

  const signalText = topSignals(signalRows)
    .map((signal) => labels[signal.signal_type] || signal.signal_type)
    .slice(0, 2);
  const latestTest = [...callTests].sort((a, b) => new Date(b.called_at || 0) - new Date(a.called_at || 0))[0];
  if (latestTest?.result === 'voicemail') signalText.push('voicemail after hours');
  if (latestTest?.result === 'no_answer') signalText.push('ring-out after hours');
  return signalText.join(' + ') || 'dispatch maturity signal pending';
}

function buildCallHook(signalRows = [], callTests = []) {
  const latestTest = [...callTests].sort((a, b) => new Date(b.called_at || 0) - new Date(a.called_at || 0))[0];
  if (latestTest?.result === 'no_answer') {
    return 'I called your shop after hours and nobody picked up. That is the problem I solve.';
  }
  if (latestTest?.result === 'voicemail') {
    return 'You are running demand, but after-hours calls still fall into voicemail.';
  }

  const strongest = topSignals(signalRows)[0]?.signal_type;
  if (strongest === 'paid_demand') {
    return 'You are already paying for calls. I help make sure the expensive ones do not die after hours.';
  }
  if (strongest === 'owner_operated' || strongest === 'no_admin_layer') {
    return 'If you are the person answering every call, what happens when you are on a job?';
  }
  if (strongest === 'review_pain') {
    return 'Missed calls show up in reviews faster than most owners expect.';
  }
  return 'I found a phone-handling leak in your shop that is costing you booked jobs.';
}

function toFrontendProspect(prospect) {
  const signals = prospect.prospect_signals || [];
  const tests = prospect.call_tests || [];
  return {
    id: prospect.id,
    business_name: prospect.business_name,
    phone: prospect.phone || prospect.phone_normalized,
    address: prospect.address || prospect.raw_source?.address || '',
    website: prospect.website || '',
    metro: prospect.metro || '',
    timezone: prospect.timezone || '',
    total_score: prospect.total_score || 0,
    tier: prospect.score_tier || 'unscored',
    signal_summary: summarizeSignals(signals, tests),
    call_hook: buildCallHook(signals, tests),
    signal_details: signals.map((signal) => signal.signal_type),
  };
}

function mapOutcome(outcome) {
  switch (outcome) {
    case 'voicemail':
      return { outcome: 'voicemail_left', demoScheduled: false };
    case 'not_interested':
      return { outcome: 'answered_not_interested', demoScheduled: false };
    case 'wrong_number':
      return { outcome: 'wrong_number', demoScheduled: false };
    case 'interested':
      return { outcome: 'answered_interested', demoScheduled: false };
    case 'demo':
      return { outcome: 'answered_interested', demoScheduled: true };
    case 'callback':
      return { outcome: 'answered_callback', demoScheduled: false };
    case 'gatekeeper':
      return { outcome: 'gatekeeper_blocked', demoScheduled: false };
    case 'no_answer':
    default:
      return { outcome: 'no_answer', demoScheduled: false };
  }
}

async function emitInngestEvent(eventName, payload) {
  if (!INNGEST_EVENT_URL) return;
  const headers = { 'Content-Type': 'application/json' };
  if (INNGEST_EVENT_KEY) {
    headers.Authorization = `Bearer ${INNGEST_EVENT_KEY}`;
  }

  try {
    const response = await fetch(INNGEST_EVENT_URL, {
      method: 'POST',
      headers,
      body: JSON.stringify({ name: eventName, data: payload }),
    });
    if (!response.ok) {
      console.error('[inngest] event failed', response.status);
    }
  } catch (error) {
    console.error('[inngest] event failed', error.message);
  }
}

async function updateProspectStage(prospectId, outcome, demoScheduled) {
  if (!supabase || !prospectId) return;
  const patch = {};
  if (outcome === 'answered_interested') {
    patch.stage = demoScheduled ? 'converted' : 'interested';
  } else if (outcome === 'answered_callback') {
    patch.stage = 'callback';
  } else if (outcome === 'wrong_number') {
    patch.stage = 'disqualified';
    patch.disqualification_reason = 'wrong_number';
  } else {
    patch.stage = 'called';
  }
  await supabase.from('outbound_prospects').update(patch).eq('id', prospectId);
}

async function writeOutcomeRecord(callSid) {
  const data = callStore.get(callSid);
  if (!data || !data.prospectId || !supabase) return;
  if (data.outcomeWritten) return;
  storeCall(callSid, { outcomeWritten: true });

  const mapped = mapOutcome(data.outcome);
  const payload = {
    tenant_id: OUTBOUND_TENANT_ID,
    prospect_id: data.prospectId,
    twilio_call_sid: callSid,
    outcome: mapped.outcome,
    notes: data.notes || null,
    call_hook_used: data.callHookUsed || null,
    demo_scheduled: mapped.demoScheduled,
    callback_date: data.callbackDate || null,
    recording_url: data.recordingUrl ? `${data.recordingUrl}.mp3` : null,
    transcript: data.transcriptionText || null,
  };

  const { data: inserted, error } = await supabase
    .from('outbound_calls')
    .upsert(payload, { onConflict: 'tenant_id,twilio_call_sid', ignoreDuplicates: true })
    .select();

  if (error) {
    storeCall(callSid, { outcomeWritten: false });
    throw error;
  }

  if (inserted && inserted.length > 0) {
    await mergePendingHudSession(callSid);

    await updateProspectStage(data.prospectId, mapped.outcome, mapped.demoScheduled);
    await emitInngestEvent(OUTBOUND_CALL_OUTCOME_EVENT, {
      tenant_id: OUTBOUND_TENANT_ID,
      prospect_id: data.prospectId,
      twilio_call_sid: callSid,
      outcome: mapped.outcome,
      source_version: OUTBOUND_SOURCE_VERSION,
    });
  }
}

app.get('/', (_req, res) => {
  setHudCookie(res);
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.get('/hud', (_req, res) => {
  setHudCookie(res);
  res.sendFile(path.join(__dirname, 'hud', 'index.html'));
});

app.get('/token', (_req, res) => {
  const AccessToken = twilio.jwt.AccessToken;
  const VoiceGrant = AccessToken.VoiceGrant;

  const token = new AccessToken(
    TWILIO_ACCOUNT_SID,
    TWILIO_API_KEY_SID,
    TWILIO_API_KEY_SECRET,
    { identity: 'calllock-agent', ttl: 3600 },
  );

  const grant = new VoiceGrant({
    outgoingApplicationSid: TWILIO_TWIML_APP_SID,
    incomingAllow: false,
  });
  token.addGrant(grant);

  res.json({ token: token.toJwt() });
});

app.get('/prospects', async (_req, res) => {
  if (!supabase) {
    res.status(500).json({ error: 'SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required' });
    return;
  }

  const { data, error } = await supabase
    .from('outbound_prospects')
    .select(`
      id,
      business_name,
      phone,
      phone_normalized,
      website,
      address,
      metro,
      timezone,
      total_score,
      score_tier,
      raw_source,
      prospect_signals(signal_type, signal_tier, score, observed_at),
      call_tests(result, called_at, local_time),
      prospect_scores(total_score, tier, scored_at)
    `)
    .eq('tenant_id', OUTBOUND_TENANT_ID)
    .eq('stage', 'call_ready')
    .order('total_score', { ascending: false })
    .limit(200);

  if (error) {
    res.status(500).json({ error: error.message });
    return;
  }

  res.json({ prospects: (data || []).map(toFrontendProspect) });
});

app.post('/twiml', validateTwilioSignature, (req, res) => {
  const to = req.body.To;
  if (!to) {
    res.status(400).send('Missing To parameter');
    return;
  }

  const VoiceResponse = twilio.twiml.VoiceResponse;
  const response = new VoiceResponse();
  const dial = response.dial({
    callerId: TWILIO_PHONE_NUMBER,
    record: 'record-from-answer-dual',
    recordingStatusCallback: `${CALL_SERVER_BASE_URL}/callbacks/recording`,
    recordingStatusCallbackMethod: 'POST',
    recordingStatusCallbackEvent: 'completed',
  });
  dial.number(to);

  res.type('text/xml');
  res.send(response.toString());
});

app.post('/calls/:callSid/metadata', (req, res) => {
  const { callSid } = req.params;
  const {
    prospectId,
    businessName,
    outcome,
    notes,
    callbackDate,
    callHookUsed,
  } = req.body;

  console.log(`[metadata] CallSid=${callSid} prospect=${prospectId} business=${businessName} outcome=${outcome}`);
  storeCall(callSid, { prospectId, businessName, outcome, notes, callbackDate, callHookUsed });

  const data = callStore.get(callSid);
  if (data?.transcriptionText && data?.prospectId) {
    writeOutcomeRecord(callSid).catch((error) => console.error('[outbound] write failed:', error.message));
  }

  res.json({ ok: true });
});

app.post('/callbacks/recording', validateTwilioSignature, (req, res) => {
  const { CallSid, RecordingSid, RecordingUrl, RecordingDuration, RecordingStatus } = req.body;

  if (RecordingStatus !== 'completed') {
    res.sendStatus(200);
    return;
  }

  console.log(`[recording] CallSid=${CallSid} duration=${RecordingDuration}s url=${RecordingUrl}`);
  storeCall(CallSid, { recordingSid: RecordingSid, recordingUrl: RecordingUrl, recordingDuration: RecordingDuration });

  twilioClient.transcriptions
    .create({
      recordingSid: RecordingSid,
      statusCallback: `${CALL_SERVER_BASE_URL}/callbacks/transcription`,
    })
    .then((transcription) => console.log(`[transcription] Started ${transcription.sid} for recording ${RecordingSid}`))
    .catch((error) => {
      console.error('[transcription] Failed to start:', error.message);
      const data = callStore.get(CallSid);
      if (data?.prospectId) {
        writeOutcomeRecord(CallSid).catch((innerError) => console.error('[outbound] write failed:', innerError.message));
      }
    });

  res.sendStatus(200);
});

app.post('/callbacks/transcription', validateTwilioSignature, (req, res) => {
  const { CallSid, TranscriptionText, TranscriptionStatus } = req.body;
  console.log(`[transcription] CallSid=${CallSid} status=${TranscriptionStatus} length=${TranscriptionText?.length || 0}`);

  if (TranscriptionStatus === 'completed' && TranscriptionText) {
    storeCall(CallSid, { transcriptionText: TranscriptionText });
  }

  const data = callStore.get(CallSid);

  // Sequence: write outcome row first, THEN trigger extraction.
  // Extraction does an UPDATE by twilio_call_sid — the row must exist.
  (async () => {
    if (data?.prospectId && data?.recordingUrl) {
      try {
        await writeOutcomeRecord(CallSid);
      } catch (error) {
        console.error('[outbound] write failed:', error.message);
      }
    }

    if (TranscriptionText && TranscriptionText.length >= 50) {
      try {
        await runExtractionAsync(CallSid, TranscriptionText, data || {});
      } catch (error) {
        console.error('[extraction] async failed:', error.message);
      }
    }
  })();

  res.sendStatus(200);
});

// Daily plan proxy — calls harness with 3s timeout, falls back to ranked list
app.get('/daily-plan', async (_req, res) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (HARNESS_EVENT_SECRET) headers['Authorization'] = `Bearer ${HARNESS_EVENT_SECRET}`;
    const response = await fetch(`${HARNESS_BASE_URL}/outbound/daily-plan`, {
      headers,
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!response.ok) throw new Error(`Harness returned ${response.status}`);
    const plan = await response.json();
    res.json(plan);
  } catch (err) {
    clearTimeout(timeout);
    console.warn('[daily-plan] Harness unavailable, falling back to ranked list:', err.message);
    // Fallback: return basic ranked list without sprint structure
    try {
      if (!supabase) return res.json({ fallback: true, blocks: [], callbacks: [], fresh_leads: [] });
      const { data } = await supabase
        .from('outbound_prospects')
        .select('id, business_name, phone, phone_normalized, metro, timezone, total_score, score_tier')
        .eq('tenant_id', OUTBOUND_TENANT_ID)
        .eq('stage', 'call_ready')
        .order('total_score', { ascending: false })
        .limit(50);
      res.json({ fallback: true, blocks: [], callbacks: [], fresh_leads: data || [] });
    } catch (fallbackErr) {
      res.status(503).json({ error: 'Plan unavailable', fallback_error: fallbackErr.message });
    }
  }
});

app.get('/scoreboard', async (_req, res) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (HARNESS_EVENT_SECRET) headers.Authorization = `Bearer ${HARNESS_EVENT_SECRET}`;
    const response = await fetch(`${HARNESS_BASE_URL}/outbound/scoreboard`, {
      headers,
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!response.ok) throw new Error(`Harness returned ${response.status}`);
    const metrics = await response.json();
    res.json(metrics);
  } catch (err) {
    clearTimeout(timeout);
    console.warn('[scoreboard] Harness unavailable:', err.message);
    res.status(503).json({ error: 'Scoreboard unavailable', detail: err.message });
  }
});

app.post('/dial-started', async (req, res) => {
  const { prospect_id } = req.body || {};
  if (!prospect_id) {
    res.status(400).json({ error: 'prospect_id is required' });
    return;
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (HARNESS_EVENT_SECRET) headers.Authorization = `Bearer ${HARNESS_EVENT_SECRET}`;
    const response = await fetch(`${HARNESS_BASE_URL}/outbound/dial-started`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ prospect_id }),
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!response.ok) throw new Error(`Harness returned ${response.status}`);
    const payload = await response.json();
    res.json(payload);
  } catch (err) {
    clearTimeout(timeout);
    console.warn('[dial-started] Harness unavailable:', err.message);
    res.status(503).json({ error: 'Dial start write failed', detail: err.message });
  }
});

// ── HUD endpoints ──────────────────────────────────────────────

app.get('/hud/deepgram-token', validateHudToken, (_req, res) => {
  res.json({ key: DEEPGRAM_API_KEY || '' });
});

app.post('/hud/groq-classify', validateHudToken, async (req, res) => {
  const { utterance, stage, bridgeAngle, lastObjectionBucket, utteranceId } = req.body;

  if (!GROQ_API_KEY) {
    return res.json({ error: true, reason: 'GROQ_API_KEY not set' });
  }

  const VALID_BRIDGE_ANGLES = ['missed_calls', 'competition', 'overwhelmed', 'fallback', 'unknown'];
  const VALID_OBJECTION_BUCKETS = ['timing', 'interest', 'info', 'authority', 'unknown'];
  const VALID_QUALIFIER_READS = ['pain', 'no_pain', 'unknown_pain', 'unknown'];

  const systemPrompt = `You are a cold call stage classifier for an HVAC contractor sales call. Given a prospect's utterance and the current call stage, classify the response. Return ONLY a valid JSON object with no other text.

Current stage: ${stage}
${bridgeAngle ? 'Current bridge angle: ' + bridgeAngle : ''}
${lastObjectionBucket ? 'Last objection bucket: ' + lastObjectionBucket : ''}

Return JSON with these fields (include only relevant ones):
- "bridgeAngle": one of [${VALID_BRIDGE_ANGLES.join(', ')}] (only if stage is OPENER or BRIDGE)
- "objectionBucket": one of [${VALID_OBJECTION_BUCKETS.join(', ')}] (only if stage is CLOSE or OBJECTION)
- "qualifierRead": one of [${VALID_QUALIFIER_READS.join(', ')}] (only if stage is QUALIFIER)
- "confidence": number 0-1
- "why": brief explanation

Example: {"bridgeAngle":"missed_calls","confidence":0.82,"why":"mentions voicemail"}`;

  try {
    const controller = new AbortController();
    // 2s timeout (600ms was too aggressive for Groq cold starts)
    const timeout = setTimeout(() => controller.abort(), 2000);

    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${GROQ_API_KEY}`,
      },
      body: JSON.stringify({
        model: 'llama-3.1-8b-instant',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: utterance },
        ],
        temperature: 0.1,
        max_tokens: 150,
        response_format: { type: 'json_object' },
      }),
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!response.ok) {
      console.error('[hud/groq] API returned', response.status);
      return res.json({ error: true });
    }

    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;

    if (!content) {
      return res.json({ error: true });
    }

    let parsed;
    try {
      parsed = JSON.parse(content);
    } catch {
      console.error('[hud/groq] Invalid JSON from model:', content);
      return res.json({ error: true });
    }

    // Validate enum values
    if (parsed.bridgeAngle && !VALID_BRIDGE_ANGLES.includes(parsed.bridgeAngle)) {
      console.warn('[hud/groq] Invalid bridgeAngle:', parsed.bridgeAngle);
      return res.json({ error: true });
    }
    if (parsed.objectionBucket && !VALID_OBJECTION_BUCKETS.includes(parsed.objectionBucket)) {
      console.warn('[hud/groq] Invalid objectionBucket:', parsed.objectionBucket);
      return res.json({ error: true });
    }
    if (parsed.qualifierRead && !VALID_QUALIFIER_READS.includes(parsed.qualifierRead)) {
      console.warn('[hud/groq] Invalid qualifierRead:', parsed.qualifierRead);
      return res.json({ error: true });
    }

    // Whitelist only expected fields (don't spread arbitrary LLM output)
    res.json({
      bridgeAngle: parsed.bridgeAngle || undefined,
      objectionBucket: parsed.objectionBucket || undefined,
      qualifierRead: parsed.qualifierRead || undefined,
      confidence: typeof parsed.confidence === 'number' ? parsed.confidence : 0.5,
      why: typeof parsed.why === 'string' ? parsed.why.slice(0, 200) : undefined,
      utteranceId,
    });
  } catch (err) {
    if (err.name === 'AbortError') {
      console.warn('[hud/groq] Timeout (600ms)');
    } else {
      console.error('[hud/groq] Error:', err.message);
    }
    res.json({ error: true });
  }
});

app.post('/hud/session-log', validateHudToken, async (req, res) => {
  const { twilio_call_sid, prospect_id, hud_session } = req.body;

  if (!twilio_call_sid || !hud_session) {
    return res.status(400).json({ error: 'twilio_call_sid and hud_session are required' });
  }

  try {
    await stageHudSession(twilio_call_sid, prospect_id, hud_session);
  } catch (error) {
    console.error('[hud/session-log] Failed to stage session:', error.message);
    return res.status(503).json({ error: 'Could not persist hud_session' });
  }

  if (supabase) {
    const { data: updated, error } = await supabase
      .from('outbound_calls')
      .update({ hud_session })
      .eq('twilio_call_sid', twilio_call_sid)
      .eq('tenant_id', OUTBOUND_TENANT_ID)
      .select('id');

    if (error) {
      console.error('[hud/session-log] Supabase update error:', error.message);
    }

    if (updated && updated.length > 0) {
      await deleteStagedHudSession(twilio_call_sid);
      console.log('[hud/session-log] Updated hud_session for', twilio_call_sid);
      return res.json({ ok: true, merged: true });
    }
  }

  console.log('[hud/session-log] Staged pending hud_session for', twilio_call_sid);
  res.json({ ok: true, merged: false });
});

app.get('/health', (_req, res) => res.json({ status: 'ok' }));

app.listen(parseInt(PORT, 10), () => {
  console.log(`[call-server] Listening on port ${PORT}`);
  console.log(`[call-server] TwiML App: ${TWILIO_TWIML_APP_SID}`);
  console.log(`[call-server] Callback base: ${CALL_SERVER_BASE_URL}`);
});
