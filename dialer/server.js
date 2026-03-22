const express = require('express');
const cors = require('cors');
const path = require('path');
const twilio = require('twilio');
const { createClient } = require('@supabase/supabase-js');

const OUTBOUND_TENANT_ID = '00000000-0000-0000-0000-000000000001';
const OUTBOUND_CALL_OUTCOME_EVENT = 'outbound/call.outcome-logged';

const app = express();
app.use(cors());
app.use(express.urlencoded({ extended: false }));
app.use(express.json());
app.use(express.static(__dirname));

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
  PORT = '3004',
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

setInterval(() => {
  const cutoff = Date.now() - 10 * 60 * 1000;
  for (const [sid, data] of callStore) {
    if (data.updatedAt < cutoff) callStore.delete(sid);
  }
}, 5 * 60 * 1000);

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
  res.sendFile(path.join(__dirname, 'index.html'));
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

app.post('/twiml', (req, res) => {
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

app.post('/callbacks/recording', (req, res) => {
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

app.post('/callbacks/transcription', (req, res) => {
  const { CallSid, TranscriptionText, TranscriptionStatus } = req.body;
  console.log(`[transcription] CallSid=${CallSid} status=${TranscriptionStatus} length=${TranscriptionText?.length || 0}`);

  if (TranscriptionStatus === 'completed' && TranscriptionText) {
    storeCall(CallSid, { transcriptionText: TranscriptionText });
  }

  const data = callStore.get(CallSid);
  if (data?.prospectId && data?.recordingUrl) {
    writeOutcomeRecord(CallSid).catch((error) => console.error('[outbound] write failed:', error.message));
  }

  res.sendStatus(200);
});

app.get('/health', (_req, res) => res.json({ status: 'ok' }));

app.listen(parseInt(PORT, 10), () => {
  console.log(`[call-server] Listening on port ${PORT}`);
  console.log(`[call-server] TwiML App: ${TWILIO_TWIML_APP_SID}`);
  console.log(`[call-server] Callback base: ${CALL_SERVER_BASE_URL}`);
});
