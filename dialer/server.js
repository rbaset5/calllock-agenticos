// Load local .env, then parent .env.local (first wins via dotenv, manual loader skips existing)
require('dotenv').config();
const _fs = require('fs');
const _envPath = require('path').join(__dirname, '..', '.env.local');
if (_fs.existsSync(_envPath)) {
  _fs.readFileSync(_envPath, 'utf8').split('\n').forEach(line => {
    const m = line.match(/^([^#=\s]+)\s*=\s*(.*)$/);
    if (m && !process.env[m[1].trim()]) process.env[m[1].trim()] = m[2].trim();
  });
}

const express = require('express');
const cors = require('cors');
const path = require('path');
const { randomUUID } = require('crypto');
const twilio = require('twilio');
const { createClient } = require('@supabase/supabase-js');
const { registerStatusCallbackRoute } = require('./status-callbacks');

const OUTBOUND_TENANT_ID = '00000000-0000-0000-0000-000000000001';
const OUTBOUND_CALL_OUTCOME_EVENT = 'outbound/call.outcome-logged';
const OUTBOUND_EXTRACTION_COMPLETE_EVENT = 'outbound/call.extraction-complete';

const app = express();
app.use(cors());
app.use(express.urlencoded({ extended: false }));
app.use(express.json());
// ────────────────────────────────────────────────────────────────────
// DEPRECATED — /hud v2 card-based HUD (static mount + routes below).
// Superseded by /hotkey (see app.get('/hotkey') below). Scheduled for
// deletion in a follow-up PR once /hotkey has battle-tested on 50+ real
// dials. See TODOS.md "Sales HUD" section. DO NOT add new features here.
// ────────────────────────────────────────────────────────────────────
// Only serve the hud/ subdirectory as static (not the whole dialer/ dir which includes server.js)
// no-cache for JS modules during development — prevents stale ES module imports
app.use('/hud', express.static(path.join(__dirname, 'hud'), {
  setHeaders: (res, filePath) => {
    if (filePath.endsWith('.js')) {
      res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    }
  },
}));

const {
  TWILIO_ACCOUNT_SID,
  TWILIO_AUTH_TOKEN,
  TWILIO_API_KEY_SID,
  TWILIO_API_KEY_SECRET,
  TWILIO_PHONE_NUMBER,
  TWILIO_TWIML_APP_SID,
  CALL_SERVER_BASE_URL,
  SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL,
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

// Local presence: state → Twilio number for outbound caller ID.
// Falls back to TWILIO_PHONE_NUMBER if state not mapped.
const LOCAL_PRESENCE_NUMBERS = {
  FL: '+13526767831',
  MI: '+12314473584',
  IL: '+13097412672',
  TX: '+13252164094',
  AZ: '+19287560437',
};
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
      outcome: callData.outcome || 'unknown',
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
    console.warn('[auth] HUD_INTERNAL_TOKEN not set — HUD endpoints are unprotected');
    return next();
  }
  const token = req.headers['x-hud-token'] || readCookie(req, 'calllock_hud_token');
  if (!token) {
    return res.status(403).json({ error: 'Missing HUD token' });
  }
  // Constant-time comparison to prevent timing attacks
  const a = Buffer.from(token);
  const b = Buffer.from(HUD_INTERNAL_TOKEN);
  if (a.length !== b.length || !require('crypto').timingSafeEqual(a, b)) {
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

registerStatusCallbackRoute(app, {
  validateTwilioSignature,
  storeCall,
  logger: console,
});

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

// Sprint start date: fetched from harness on startup, hardcoded fallback
let _sprintStartIso = '2026-03-30';
async function _fetchSprintStart() {
  if (!HARNESS_BASE_URL) return;
  try {
    const resp = await fetch(`${HARNESS_BASE_URL}/outbound/current-queue?block=AM`, { signal: AbortSignal.timeout(3000) });
    if (resp.ok) {
      const data = await resp.json();
      const start = data?.state?.schedule_start;
      if (start && /^\d{4}-\d{2}-\d{2}$/.test(start)) _sprintStartIso = start;
    }
  } catch { /* harness may not be up yet */ }
}
_fetchSprintStart();
setInterval(_fetchSprintStart, 24 * 60 * 60 * 1000);


async function buildLocalScoreboard(today = new Date()) {
  if (!supabase) {
    return {
      daily_dials: 0,
      daily_target: 0,
      day_number: 0,
      connect_rate: 0,
      demos_booked_today: 0,
      weekly_dials: 0,
      total_dials: 0,
    };
  }

  const todayIso = today.toISOString().slice(0, 10);
  const sprintStartIso = _sprintStartIso;
  const { data, error } = await supabase.rpc('sprint_scoreboard', {
    p_tenant_id: OUTBOUND_TENANT_ID,
    p_start_date: sprintStartIso,
    p_today: todayIso,
  });

  if (error) throw error;

  const raw = data || {};
  const dailyDials = Number(raw.daily_dials || 0);
  const dailyConnects = Number(raw.daily_connects || 0);
  const dailyDemos = Number(raw.daily_demos || 0);

  return {
    daily_dials: dailyDials,
    daily_target: 0,
    day_number: 0,
    connect_rate: dailyDials > 0 ? Number(((dailyConnects / dailyDials) * 100).toFixed(1)) : 0,
    demos_booked_today: dailyDemos,
    weekly_dials: Number(raw.weekly_dials || 0),
    total_dials: Number(raw.total_dials || 0),
    callbacks_completed: Number(raw.callbacks_completed || 0),
    total_connects: Number(raw.total_connects || 0),
    total_demos: Number(raw.total_demos || 0),
    total_closes: Number(raw.total_closes || 0),
    customers_signed: Number(raw.customers_signed || 0),
    fallback: true,
  };
}

async function insertDialStartedFallback(prospectId) {
  if (!supabase) {
    throw new Error('Supabase is not configured');
  }

  const twilioCallSid = `dial-started-${randomUUID()}`;
  const payload = {
    tenant_id: OUTBOUND_TENANT_ID,
    prospect_id: prospectId,
    twilio_call_sid: twilioCallSid,
    called_at: new Date().toISOString(),
    outcome: 'dial_started',
    call_outcome_type: 'dial_started',
  };

  const { data, error } = await supabase
    .from('outbound_calls')
    .insert(payload)
    .select('id')
    .limit(1);

  if (error) throw error;

  return {
    id: data?.[0]?.id || null,
    twilio_call_sid: twilioCallSid,
    fallback: true,
  };
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
    .upsert(payload, { onConflict: 'tenant_id,twilio_call_sid' })
    .select();

  if (error) {
    storeCall(callSid, { outcomeWritten: false });
    throw error;
  }

  await mergePendingHudSession(callSid);

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

app.get('/', (req, res) => {
  const tokenParam = req.query.token;
  if (tokenParam && HUD_INTERNAL_TOKEN) {
    const a = Buffer.from(tokenParam);
    const b = Buffer.from(HUD_INTERNAL_TOKEN);
    if (a.length === b.length && require('crypto').timingSafeEqual(a, b)) {
      setHudCookie(res);
    }
  }
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.get('/combo', (req, res) => {
  res.sendFile(path.join(__dirname, 'combo.html'));
});

app.get('/twilio-client.js', (_req, res) => {
  res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.sendFile(path.join(__dirname, 'twilio-client.js'));
});

app.get('/combo-loader.js', (_req, res) => {
  res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.sendFile(path.join(__dirname, 'combo-loader.js'));
});

app.get('/twilio-audio.js', (_req, res) => {
  res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.sendFile(path.join(__dirname, 'twilio-audio.js'));
});

app.get('/call-feedback.js', (_req, res) => {
  res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.sendFile(path.join(__dirname, 'call-feedback.js'));
});

app.get('/media-permissions.js', (_req, res) => {
  res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.sendFile(path.join(__dirname, 'media-permissions.js'));
});

app.get('/hud', (req, res) => {
  // Only set the cookie if the request provides the token via query param
  // (from a deep link). Don't stamp it on every unauthenticated page load.
  const tokenParam = req.query.token;
  if (tokenParam && HUD_INTERNAL_TOKEN) {
    const a = Buffer.from(tokenParam);
    const b = Buffer.from(HUD_INTERNAL_TOKEN);
    if (a.length === b.length && require('crypto').timingSafeEqual(a, b)) {
      setHudCookie(res);
    }
  }
  res.sendFile(path.join(__dirname, 'hud', 'index.html'));
});

// Pure hotkey HUD — no classifier, no BroadcastChannel, no auto-transitions.
// Driven entirely by keystrokes. See dialer/hud/hotkey.html.
app.get('/hotkey', (req, res) => {
  const tokenParam = req.query.token;
  if (tokenParam && HUD_INTERNAL_TOKEN) {
    const a = Buffer.from(tokenParam);
    const b = Buffer.from(HUD_INTERNAL_TOKEN);
    if (a.length === b.length && require('crypto').timingSafeEqual(a, b)) {
      setHudCookie(res);
    }
  }
  res.sendFile(path.join(__dirname, 'hud', 'hotkey.html'));
});

app.get('/token', validateHudToken, (_req, res) => {
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

app.get('/prospects', validateHudToken, async (_req, res) => {
  if (!supabase) {
    res.status(500).json({ error: 'SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required' });
    return;
  }

  try {
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
      .limit(1000);

    if (error) {
      console.error('[prospects] Supabase query error:', error.message, error.code);
      res.status(500).json({ error: error.message });
      return;
    }

    res.json({ prospects: (data || []).map(toFrontendProspect) });
  } catch (err) {
    console.error('[prospects] Unexpected error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

app.get('/current-queue', async (req, res) => {
  const { block, segment = '', exclude_dialed = 'true' } = req.query;
  if (!block) {
    return res.status(400).json({ error: 'block is required' });
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (HARNESS_EVENT_SECRET) headers.Authorization = `Bearer ${HARNESS_EVENT_SECRET}`;

    const params = new URLSearchParams({
      block: String(block),
      exclude_dialed: String(exclude_dialed),
    });
    if (segment) params.set('segment', String(segment));

    const response = await fetch(`${HARNESS_BASE_URL}/outbound/current-queue?${params.toString()}`, {
      headers,
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!response.ok) {
      throw new Error(`Harness returned ${response.status}`);
    }

    const payload = await response.json();
    const queue = payload.queue || {};
    if (Array.isArray(queue.prospects)) {
      queue.prospects = queue.prospects.map(toFrontendProspect);
    }
    if (Array.isArray(queue.queues)) {
      queue.queues = queue.queues.map((entry) => ({
        ...entry,
        prospects: Array.isArray(entry.prospects) ? entry.prospects.map(toFrontendProspect) : [],
      }));
    }

    res.json({ state: payload.state || null, queue });
  } catch (err) {
    clearTimeout(timeout);
    res.status(503).json({ error: 'Queue unavailable', detail: err.message });
  }
});

app.post('/twiml', validateTwilioSignature, (req, res) => {
  const to = req.body.To;
  if (!to) {
    res.status(400).send('Missing To parameter');
    return;
  }

  const prospectState = (req.body.ProspectState || '').toUpperCase();
  const callerId = LOCAL_PRESENCE_NUMBERS[prospectState] || TWILIO_PHONE_NUMBER;

  const VoiceResponse = twilio.twiml.VoiceResponse;
  const response = new VoiceResponse();
  const dial = response.dial({
    callerId,
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
    console.warn('[scoreboard] Harness unavailable, falling back to Supabase RPC:', err.message);
    try {
      const fallback = await buildLocalScoreboard();
      res.json(fallback);
    } catch (fallbackErr) {
      res.status(503).json({ error: 'Scoreboard unavailable', detail: fallbackErr.message });
    }
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
    console.warn('[dial-started] Harness unavailable, falling back to direct insert:', err.message);
    try {
      const fallback = await insertDialStartedFallback(prospect_id);
      res.json(fallback);
    } catch (fallbackErr) {
      res.status(503).json({ error: 'Dial start write failed', detail: fallbackErr.message });
    }
  }
});

// ── HUD endpoints ──────────────────────────────────────────────

app.get('/hud/deepgram-token', validateHudToken, async (_req, res) => {
  if (!DEEPGRAM_API_KEY) {
    return res.status(503).json({ error: 'DEEPGRAM_API_KEY not set' });
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2000);
    const response = await fetch('https://api.deepgram.com/v1/auth/grant', {
      method: 'POST',
      headers: {
        'Authorization': `Token ${DEEPGRAM_API_KEY}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ ttl_seconds: 60 }),
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!response.ok) {
      const detail = await response.text();
      console.error('[hud/deepgram] Token mint failed:', response.status, detail);
      return res.status(503).json({ error: 'Could not mint Deepgram token' });
    }

    const data = await response.json();
    if (!data.access_token) {
      console.error('[hud/deepgram] Token mint missing access_token');
      return res.status(503).json({ error: 'Could not mint Deepgram token' });
    }

    res.json({
      key: data.access_token,
      expires_in: typeof data.expires_in === 'number' ? data.expires_in : 60,
    });
  } catch (error) {
    if (error.name === 'AbortError') {
      console.error('[hud/deepgram] Token mint timed out');
    } else {
      console.error('[hud/deepgram] Token mint error:', error.message);
    }
    res.status(503).json({ error: 'Could not mint Deepgram token' });
  }
});

app.post('/hud/groq-classify', validateHudToken, async (req, res) => {
  const {
    utterance,
    stage,
    bridgeAngle,
    lastObjectionBucket,
    utteranceId,
    requestTone,
    requestSecondaryIntent,
  } = req.body;

  if (!GROQ_API_KEY) {
    return res.status(503).json({ error: true, reason: 'GROQ_API_KEY not set' });
  }

  // Input validation
  if (typeof utterance !== 'string' || !utterance.trim() || utterance.length > 500) {
    return res.status(400).json({ error: true, reason: 'Invalid utterance' });
  }

  const VALID_STAGES = ['GATEKEEPER', 'OPENER', 'BRIDGE', 'QUALIFIER', 'CLOSE', 'OBJECTION', 'SEED_EXIT', 'BOOKED', 'EXIT', 'NON_CONNECT'];
  if (!VALID_STAGES.includes(stage)) {
    return res.status(400).json({ error: true, reason: 'Invalid stage' });
  }

  const VALID_BRIDGE_ANGLES = ['missed_calls', 'competition', 'overwhelmed', 'fallback', 'unknown'];
  const VALID_OBJECTION_BUCKETS = ['timing', 'interest', 'info', 'authority', 'unknown'];
  const VALID_QUALIFIER_READS = ['pain', 'no_pain', 'unknown_pain', 'unknown'];
  const VALID_TONES = ['rushed', 'skeptical', 'annoyed', 'curious', 'guarded', 'neutral', 'unknown'];
  const VALID_SECONDARY_INTENTS = [
    'yes',
    'curiosity',
    'engaged_answer',
    'timing',
    'interest',
    'info',
    'authority',
    'existing_coverage',
    'answering_service',
    'pricing_question',
    'pricing_resistance',
    'confusion',
    'authority_mismatch',
    'brush_off',
    'time_pressure',
  ];

  const systemPrompt = `You are a cold call stage classifier for an HVAC contractor sales call. Given a prospect's utterance and the current call stage, classify the response. Return ONLY a valid JSON object with no other text.

Current stage: ${stage}
${bridgeAngle ? 'Current bridge angle: ' + bridgeAngle : ''}
${lastObjectionBucket ? 'Last objection bucket: ' + lastObjectionBucket : ''}

Return JSON with these fields (include only relevant ones):
- "bridgeAngle": one of [${VALID_BRIDGE_ANGLES.join(', ')}] (only if stage is OPENER or BRIDGE)
- "objectionBucket": one of [${VALID_OBJECTION_BUCKETS.join(', ')}] (only if stage is CLOSE or OBJECTION)
- "qualifierRead": one of [${VALID_QUALIFIER_READS.join(', ')}] (only if stage is QUALIFIER)
- "tone": one of [${VALID_TONES.join(', ')}]${requestTone ? ' (include when you can infer prospect tone)' : ' (omit unless requested)'}
- "tone_confidence": number 0-1${requestTone ? ' (only when tone is present)' : ' (omit unless requested)'}
- "secondary_intent": one of [${VALID_SECONDARY_INTENTS.join(', ')}]${requestSecondaryIntent ? ' (include only when a credible secondary signal is present)' : ' (omit unless requested)'}
- "secondary_confidence": number 0-1${requestSecondaryIntent ? ' (only when secondary_intent is present)' : ' (omit unless requested)'}
- "confidence": number 0-1
- "why": brief explanation

Example: {"bridgeAngle":"missed_calls","confidence":0.82,"why":"mentions voicemail"}`;

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1500);

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
    if (parsed.tone && !VALID_TONES.includes(parsed.tone)) {
      console.warn('[hud/groq] Invalid tone:', parsed.tone);
      return res.json({ error: true });
    }
    if (parsed.secondary_intent && !VALID_SECONDARY_INTENTS.includes(parsed.secondary_intent)) {
      console.warn('[hud/groq] Invalid secondary_intent:', parsed.secondary_intent);
      return res.json({ error: true });
    }

    // Whitelist only expected fields (don't spread arbitrary LLM output)
    res.json({
      bridgeAngle: parsed.bridgeAngle || undefined,
      objectionBucket: parsed.objectionBucket || undefined,
      qualifierRead: parsed.qualifierRead || undefined,
      tone: requestTone ? (parsed.tone || undefined) : undefined,
      tone_confidence: requestTone && typeof parsed.tone_confidence === 'number' ? parsed.tone_confidence : undefined,
      secondary_intent: requestSecondaryIntent ? (parsed.secondary_intent || undefined) : undefined,
      secondary_confidence:
        requestSecondaryIntent && typeof parsed.secondary_confidence === 'number'
          ? parsed.secondary_confidence
          : undefined,
      confidence: typeof parsed.confidence === 'number' ? parsed.confidence : 0.5,
      why: typeof parsed.why === 'string' ? parsed.why.slice(0, 200) : undefined,
      utteranceId,
    });
  } catch (err) {
    if (err.name === 'AbortError') {
      console.warn('[hud/groq] Timeout (1500ms)');
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
