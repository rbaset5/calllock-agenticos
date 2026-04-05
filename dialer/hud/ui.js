// dialer/hud/ui.js — DOM rendering, hotkeys, BroadcastChannel listener
// Vanilla JS ES module — no build step, no TypeScript.

import { PLAYBOOK, fillLineTemplate, linesForStage } from './playbook.js';
import { createInitialState, hudReducer, bandFromScore } from './reducer.js';
import { classifyUtterance, shouldCallLlmFallback, isUsableDeterministicResult, detectNewIntents } from './classifier.js';
import { captureSession, resetAuditTrail, logDecision, saveSession, generateReplayTimeline } from './session.js';
import { classifyWithLlm, isLlmBackoffActive } from './llm.js';
import { assignTone, shouldUpdateTone } from './tone.js';
import { computeRisk, updateTrajectory } from './risk.js';
import { composeActiveCard, generateNowSummary } from './composer.js';
import { NATIVE_STAGE_CARDS, NATIVE_OBJECTION_CARDS } from './cards.js';
import { INTENT_STAGE_MAP, HOTKEY_CONFIG, GLOBAL_HOTKEYS, BRIDGE_STAGES } from './taxonomy.js';
import { renderV2CenterPanel, renderAlsoHeard, renderProspectContext, renderTacticalCard, renderPauseStrip } from './render-v2.js';

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str;
  return el.innerHTML;
}

// ── State ──────────────────────────────────────────────────────

let state = createInitialState(PLAYBOOK);
let manualModeActive = false;
let prospectName = '';
let prospectBusiness = '';
let prospectId = null;
let callTimerInterval = null;
let callStartTime = null;
let shiftOnlyPressed = false;
let rounds = [];      // Array of { stage, line, why, source }
let roundIndex = -1;  // -1 = live/latest
let sprintContext = null;
let sprintContextStale = false;
let sprintContextCachedAt = null;
let sprintContextTimer = null;
let pauseStripTimer = null;
let pauseStripSilenceTimer = null;
let usedProbeLines = new Set(); // Probe dedup: never fire the same probe twice per call
let legendBarVisible = true;    // ? key toggles, resets to true on new call
let recentKeys = [];            // Last 3 keypresses for breadcrumb trail
let pendingIntent = null;       // One-shot intent from Alt+N, consumed by next render
let replayShowing = false;      // True after call ends, prevents dispatch from overwriting replay
let recentSignals = []; // Rolling buffer of recent classifications for burst detection
const SIGNAL_BUFFER_TTL_MS = 3500; // Signals older than this are pruned

// Decision tree navigation: → = primary path, F10 = alternate path
const STAGE_TRANSITIONS = {
  IDLE:              { f7: 'OPENER',    f8: null },
  GATEKEEPER:        { f7: 'OPENER',    f8: 'EXIT' },
  OPENER:            { f7: 'BRIDGE',    f8: null },
  PERMISSION_MOMENT: { f7: 'BRIDGE',    f8: 'EXIT' },
  MINI_PITCH:        { f7: 'BRIDGE',    f8: 'EXIT' },
  WRONG_PERSON:      { f7: 'EXIT',      f8: 'GATEKEEPER' },
  BRIDGE:            { f7: 'QUALIFIER', f8: null },
  QUALIFIER:         { f7: 'CLOSE',     f8: 'SEED_EXIT' },
  PRICING:           { f7: 'QUALIFIER', f8: 'EXIT' },
  CLOSE:             { f7: 'BOOKED',    f8: 'OBJECTION' },
  OBJECTION:         { f7: 'CLOSE',     f8: 'EXIT' },
  SEED_EXIT:         { f7: 'EXIT',      f8: null },
  BOOKED:            { f7: 'EXIT',      f8: null },
  NON_CONNECT:       { f7: 'EXIT',      f8: null },
  EXIT:              { f7: null,         f8: null },
};

// Linear ordering for ← (back) only — IDLE excluded (→ from IDLE → OPENER is one-way)
const NAV_STAGES = ['GATEKEEPER', 'OPENER', 'PERMISSION_MOMENT', 'MINI_PITCH', 'WRONG_PERSON', 'BRIDGE', 'QUALIFIER', 'PRICING', 'CLOSE', 'OBJECTION'];

// Stage display labels for the pill bar
const STAGE_DISPLAY = [
  { key: 'IDLE', label: 'IDLE' },
  { key: 'GATEKEEPER', label: 'GK' },
  { key: 'OPENER', label: 'OPEN' },
  { key: 'MINI_PITCH', label: 'MINI' },
  { key: 'WRONG_PERSON', label: 'WRONG' },
  { key: 'BRIDGE', label: 'BRIDGE' },
  { key: 'QUALIFIER', label: 'QUAL' },
  { key: 'PRICING', label: 'PRICE' },
  { key: 'CLOSE', label: 'CLOSE' },
  { key: 'OBJECTION', label: 'OBJ' },
  { key: 'EXIT', label: 'EXIT' },
  { key: 'BOOKED', label: 'BOOKED' },
];

// ── DOM refs ───────────────────────────────────────────────────

const $audioModeBadge = document.getElementById('audioModeBadge');
const $callTimer = document.getElementById('callTimer');
const $prospectInfo = document.getElementById('prospectInfo');
const $contextStrip = document.getElementById('contextStrip');
const $stageBar = document.getElementById('stageBar');
const $nowPanel = document.getElementById('nowPanel');
const $previewHint = document.getElementById('previewHint');
const $nowLine = document.getElementById('nowLine');
const $nowWhy = document.getElementById('nowWhy');
const $confidenceBadge = document.getElementById('confidenceBadge');
const $linesFeed = document.getElementById('linesFeed');
const $objectionsFeed = document.getElementById('objectionsFeed');
const $roundStrip = document.getElementById('roundStrip');

// ── Pause strip ──────────────────────────────────────────────

function activatePauseStrip() {
  renderPauseStrip(true, '\u23F8 PAUSE \u00B7 Let them answer \u00B7 Classify their response type');
  clearTimeout(pauseStripTimer);
  // Silence nudge fires at 5s, dim fires at 8s (nudge must come first)
  clearTimeout(pauseStripSilenceTimer);
  pauseStripSilenceTimer = setTimeout(() => {
    const el = document.getElementById('v2-pause-strip');
    if (el) el.textContent = '\u23F8 Hold. Let them answer.';
  }, 5000);
  pauseStripTimer = setTimeout(() => {
    const el = document.getElementById('v2-pause-strip');
    if (el) el.classList.add('dimmed');
  }, 8000);
}

function deactivatePauseStrip() {
  clearTimeout(pauseStripTimer);
  clearTimeout(pauseStripSilenceTimer);
  const el = document.getElementById('v2-pause-strip');
  if (el) el.classList.add('dimmed');
}

// ── Transcript health ─────────────────────────────────────────

let transcriptHealthTimer = null;

function startTranscriptHealthWatch() {
  clearTimeout(transcriptHealthTimer);
  transcriptHealthTimer = setTimeout(() => {
    const el = document.getElementById('v2-transcript-health');
    if (el) {
      el.textContent = 'TRANSCRIPT LAG';
      el.className = 'v2-transcript-health stale';
    }
  }, 3000);
}

function resetTranscriptHealth() {
  clearTimeout(transcriptHealthTimer);
  const el = document.getElementById('v2-transcript-health');
  if (el) {
    el.textContent = '';
    el.className = 'v2-transcript-health';
  }
  // Restart the watch if call is active
  if (state.callId && !state.ended) {
    startTranscriptHealthWatch();
  }
}

// ── Dispatch ───────────────────────────────────────────────────

function dispatch(action) {
  const prevState = state;
  state = hudReducer(state, action, PLAYBOOK);
  if (state.stage !== prevState.stage && state.stage !== 'IDLE') {
    // Keep round history across stage changes (Option B from plan)
    roundIndex = -1;
    // Delay pause strip by 3s so rep can read the line first
    clearTimeout(pauseStripTimer);
    clearTimeout(pauseStripSilenceTimer);
    pauseStripTimer = setTimeout(() => activatePauseStrip(), 3000);
    // Stage transition flash: green = manual, blue = AI (skip IDLE transitions)
    if (prevState.stage !== 'IDLE' && state.stage !== 'IDLE' && state.stage !== 'ENDED') {
      const isManual = action.type.startsWith('MANUAL_');
      flashStageTransition(isManual ? 'manual' : 'ai');
    }
  }
  if (action.type === 'TRANSCRIPT_FINAL') {
    deactivatePauseStrip();
  }
  logDecision(action, prevState, state);
  render();
  // Only re-render hotkey bar on stage change (avoid DOM thrash on every transcript)
  if (state.stage !== prevState.stage) {
    renderHotkeyBar();
  }
}

// ── BroadcastChannel ───────────────────────────────────────────

const channel = new BroadcastChannel('calllock-hud');
const queueParams = new URLSearchParams(window.location.search);

channel.addEventListener('message', (event) => {
  const msg = event.data;
  if (!msg || !msg.type) return;

  switch (msg.type) {
    case 'CALL_STARTED': {
      // Auto-reset
      resetAuditTrail();
      usedProbeLines.clear();
      recentSignals = [];
      recentKeys = [];
      pendingIntent = null;
      legendBarVisible = true;
      replayShowing = false;
      renderBreadcrumb(); // Clear stale replay stats from previous call
      prospectName = msg.prospectName || '';
      prospectBusiness = msg.businessName || '';
      prospectId = msg.prospectId || null;
      manualModeActive = false;

      dispatch({
        type: 'INIT_CALL',
        callId: msg.callSid,
        prospect: { name: prospectName, business: prospectBusiness },
        atMs: Date.now(),
      });
      dispatch({
        type: 'CALL_CONNECTED',
        callSid: msg.callSid,
        atMs: Date.now(),
      });

      startCallTimer();
      startTranscriptHealthWatch();

      // v2: populate prospect context if available
      if (msg.prospectContext) {
        dispatch({ type: 'SET_PROSPECT_CONTEXT', callSid: msg.callSid, prospectContext: msg.prospectContext });
      }
      renderProspectContext(msg.prospectContext || null);
      break;
    }

    case 'TRANSCRIPT': {
      // Validate callSid to prevent cross-call bleed
      if (msg.callSid && state.callId && msg.callSid !== state.callId) break;
      resetTranscriptHealth();
      if (!msg.isFinal) {
        handleInterimTranscript(msg);
      } else if (msg.speaker === 'prospect') {
        handleFinalProspectTranscript(msg);
      }
      break;
    }

    case 'AUDIO_MODE': {
      if (msg.mode === 'manual') {
        manualModeActive = true;
        render();
      } else if (msg.mode === 'dual') {
        // Unlatch manual mode when dual stream comes up
        manualModeActive = false;
        render();
      }
      break;
    }

    case 'CALL_ENDED': {
      if (msg.callSid && state.callId && msg.callSid !== state.callId) break;
      clearTimeout(transcriptHealthTimer);
      dispatch({
        type: 'END_CALL',
        callSid: state.callId,
        atMs: Date.now(),
      });
      const endedState = state;
      const endedProspectId = prospectId;
      const endedSession = captureSession(endedState);
      stopCallTimer();
      renderReplayTimeline();
      // Delay session save briefly to allow OUTCOME to arrive first
      setTimeout(() => saveSession(endedState, endedProspectId, endedSession), 500);
      break;
    }

    case 'OUTCOME': {
      if (msg.callSid && state.callId && msg.callSid !== state.callId) break;
      if (msg.outcome) {
        if (sprintContext && typeof sprintContext.dials_completed_today === 'number') {
          sprintContext = {
            ...sprintContext,
            dials_completed_today: sprintContext.dials_completed_today + 1,
          };
        }
        dispatch({
          type: 'OUTCOME_RECEIVED',
          callSid: state.callId,
          outcome: msg.outcome,
          atMs: Date.now(),
        });
        saveSession(state, prospectId);
      }
      break;
    }
  }
});

// ── Transcript handling ────────────────────────────────────────

function handleInterimTranscript(msg) {
  if (manualModeActive) return;
  if (msg.speaker !== 'prospect') return;

  // Run classifier for preview hint
  const result = classifyUtterance(msg.text, { stage: state.stage });
  if (result.band !== 'low') {
    const hint = formatPreviewHint(result);
    $previewHint.textContent = hint;
  }
}

function currentQueueRequest() {
  const block = (queueParams.get('block') || '').toUpperCase();
  const segment = queueParams.get('segment') || '';
  return block ? { block, segment } : null;
}

function queueCacheKey(block, date) {
  return `lastQueue-${block}-${date}`;
}

function readQueueCache(block) {
  const prefix = `lastQueue-${block}-`;
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (!key || !key.startsWith(prefix)) continue;
    try {
      const parsed = JSON.parse(localStorage.getItem(key));
      if (parsed?.payload) return parsed;
    } catch {}
  }
  return null;
}

function formatEtTime(value) {
  if (!value) return '';
  try {
    return new Date(value).toLocaleTimeString('en-US', {
      timeZone: 'America/Detroit',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

function contextCountdownText(state, stale = false) {
  if (!state) return '—';
  if (!state.block_active && state.next_block) {
    return `Next: ${state.next_block} ${formatEtTime(state.next_block_at)} ET${stale ? ' (stale)' : ''}`;
  }
  if (!state.next_segment_at || !state.next_segment_name) {
    return stale ? 'Last known state (stale)' : 'Queue live';
  }
  const minutes = Math.max(Math.floor((new Date(state.next_segment_at).getTime() - Date.now()) / 60000), 0);
  return `Next: ${state.next_segment_name} ${formatEtTime(state.next_segment_at)} ET (${minutes}m)${stale ? ' (stale)' : ''}`;
}

async function loadSprintContext() {
  const request = currentQueueRequest();
  if (!request || !$contextStrip) return;

  try {
    const params = new URLSearchParams({ block: request.block, exclude_dialed: 'true' });
    if (request.segment) params.set('segment', request.segment);
    const response = await fetch(`/current-queue?${params.toString()}`, { credentials: 'same-origin' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    sprintContext = payload.state || null;
    sprintContextStale = false;
    sprintContextCachedAt = Date.now();
  } catch (error) {
    const cached = readQueueCache(request.block);
    if (cached?.payload?.state) {
      sprintContext = cached.payload.state;
      sprintContextStale = true;
      sprintContextCachedAt = cached.cachedAt || Date.now();
    } else {
      sprintContext = null;
      sprintContextStale = false;
      sprintContextCachedAt = null;
    }
  }

  render();
}

function handleFinalProspectTranscript(msg) {
  // Clear preview
  $previewHint.textContent = '';

  if (manualModeActive) return;

  // Run rules classifier
  const result = classifyUtterance(msg.text, { stage: state.stage });
  const now = Date.now();
  const turn = {
    speaker: 'prospect',
    text: msg.text,
    atMs: msg.atMs || now,
    utteranceId: msg.utteranceId,
  };

  // Push to rolling signal buffer + prune stale entries
  const signal = result.detectedIntent || result.objectionBucket || result.bridgeAngle || result.qualifierRead || null;
  if (signal) {
    recentSignals.push({ signal, atMs: now, seq: msg.seq });
  }
  recentSignals = recentSignals.filter(s => now - s.atMs < SIGNAL_BUFFER_TTL_MS);

  if (isUsableDeterministicResult(result)) {
    // High/medium confidence: commit via reducer
    dispatch({
      type: 'TRANSCRIPT_FINAL',
      callSid: state.callId,
      turn,
      rule: result,
      seq: msg.seq,
      atMs: msg.atMs || Date.now(),
    });
    // v2: run turn lifecycle after dispatch updates state
    processTurn(msg.text, result);
  } else {
    // Low confidence: add transcript but don't change state
    dispatch({
      type: 'TRANSCRIPT_FINAL',
      callSid: state.callId,
      turn,
      rule: result,
      seq: msg.seq,
      atMs: msg.atMs || Date.now(),
    });
    // v2: run turn lifecycle even for low-confidence (tone/risk still useful)
    processTurn(msg.text, result);

    // Try LLM fallback — pass rules result so we can fall through on 503
    if (shouldCallLlmFallback(result)) {
      if (isLlmBackoffActive() && result.confidence > 0) {
        // Synchronous fallthrough: LLM is known-down, promote rules result
        // immediately instead of going async (which loses the race with the
        // next transcript message).
        dispatch({
          type: 'LLM_RESULT',
          callSid: state.callId,
          utteranceId: msg.utteranceId,
          seq: msg.seq,
          result: {
            ...result,
            band: 'medium',
            confidence: Math.max(result.confidence, 0.55),
            why: (result.why || 'rules') + ' (sync fallthrough, LLM down)',
            utterance: msg.text,
          },
          atMs: Date.now(),
        });
      } else {
        triggerLlmFallback(msg.text, msg.utteranceId, msg.seq, result);
      }
    }
  }
}

async function triggerLlmFallback(utterance, utteranceId, seq, rulesResult) {
  // Capture state BEFORE await to prevent cross-call bleed if a new call
  // arrives while the LLM request is in-flight.
  const capturedCallId = state.callId;
  const capturedStage = state.stage;
  const capturedContext = {
    bridgeAngle: state.bridgeAngle,
    lastObjectionBucket: state.lastObjectionBucket,
  };

  const llmResult = await classifyWithLlm(
    utterance,
    capturedStage,
    capturedContext,
    utteranceId,
  );

  if (llmResult) {
    dispatch({
      type: 'LLM_RESULT',
      callSid: capturedCallId,
      utteranceId,
      seq,
      result: {
        ...llmResult,
        band: bandFromScore(llmResult.confidence ?? 0.7),
        why: llmResult.why || 'LLM classification',
        utterance,
      },
      atMs: Date.now(),
    });
  } else if (rulesResult && rulesResult.confidence > 0) {
    // Graceful degradation: LLM unavailable (503/timeout/error).
    // Promote the low-confidence rules result to medium so the conversation
    // can advance instead of freezing. Better a best-guess transition than
    // a permanently stuck HUD.
    console.warn('[hud/llm] LLM unavailable, falling through to rules result:', rulesResult.why);
    dispatch({
      type: 'LLM_RESULT',
      callSid: capturedCallId,
      utteranceId,
      seq,
      result: {
        ...rulesResult,
        band: 'medium',
        confidence: Math.max(rulesResult.confidence, 0.55),
        why: (rulesResult.why || 'rules') + ' (LLM unavailable, rules fallthrough)',
        utterance,
      },
      atMs: Date.now(),
    });
  } else {
    dispatch({
      type: 'LLM_FAILED',
      callSid: capturedCallId,
      atMs: Date.now(),
    });
  }
}

function formatPreviewHint(result) {
  const parts = [];
  if (result.bridgeAngle && result.bridgeAngle !== 'unknown') {
    parts.push('BRIDGE \u2014 ' + result.bridgeAngle);
  }
  if (result.qualifierRead && result.qualifierRead !== 'unknown') {
    parts.push('QUAL \u2014 ' + result.qualifierRead);
  }
  if (result.objectionBucket) {
    parts.push('OBJ \u2014 ' + result.objectionBucket);
  }
  if (result.stageSuggestion) {
    parts.push(result.stageSuggestion);
  }
  return parts.length > 0 ? 'likely: ' + parts.join(', ') : '';
}


// ── Call timer ─────────────────────────────────────────────────

function startCallTimer() {
  stopCallTimer();
  callStartTime = Date.now();
  callTimerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - callStartTime) / 1000);
    const m = Math.floor(elapsed / 60);
    const s = elapsed % 60;
    $callTimer.textContent = String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
  }, 1000);
}

function stopCallTimer() {
  if (callTimerInterval) {
    clearInterval(callTimerInterval);
    callTimerInterval = null;
  }
}

// ── Hotkey bar + breadcrumb ────────────────────────────────────

/** Render the stage-aware hotkey legend bar from HOTKEY_CONFIG. */
function renderHotkeyBar() {
  const $bar = document.getElementById('hotkey-bar');
  if (!$bar) return;
  if (replayShowing) return; // Don't overwrite replay timeline
  if (!legendBarVisible) { $bar.style.display = 'none'; return; }
  $bar.style.display = '';
  const stageKeys = HOTKEY_CONFIG[state.stage] || [];
  const globalItems = GLOBAL_HOTKEYS.filter(g =>
    g.key !== 'Shift' || state.stage === 'CLOSE' || state.stage === 'OBJECTION'
  );
  // All values from HOTKEY_CONFIG constants, _esc() for defense-in-depth (existing pattern)
  const parts = [];
  for (const h of stageKeys) {
    const span = document.createElement('span');
    span.className = 'hotkey-item';
    const kbd = document.createElement('kbd');
    kbd.textContent = h.key;
    span.appendChild(kbd);
    span.appendChild(document.createTextNode(' ' + h.label));
    parts.push(span);
  }
  if (stageKeys.length > 0) {
    const sep = document.createElement('span');
    sep.className = 'hotkey-item';
    sep.style.opacity = '0.3';
    sep.textContent = '|';
    parts.push(sep);
  }
  for (const g of globalItems) {
    const span = document.createElement('span');
    span.className = 'hotkey-item';
    const kbd = document.createElement('kbd');
    kbd.textContent = g.key;
    span.appendChild(kbd);
    span.appendChild(document.createTextNode(' ' + g.label));
    parts.push(span);
  }
  $bar.replaceChildren(...parts);
}

/** Push a key label to the breadcrumb trail (max 3, sliding window). */
function pushRecentKey(key, label) {
  recentKeys.push({ key, label, ts: Date.now() });
  if (recentKeys.length > 3) recentKeys.shift();
  renderBreadcrumb();
}

/** Render the last-3-keys breadcrumb trail below the legend bar. */
function renderBreadcrumb() {
  const $strip = document.getElementById('quick-pick-strip');
  if (!$strip) return;
  if (recentKeys.length === 0) { $strip.replaceChildren(); return; }
  const pills = [];
  for (const r of recentKeys) {
    const span = document.createElement('span');
    span.className = 'quick-pick';
    span.style.pointerEvents = 'none';
    span.style.opacity = '0.6';
    const keySpan = document.createElement('span');
    keySpan.className = 'quick-pick-key';
    keySpan.textContent = r.key;
    const labelSpan = document.createElement('span');
    labelSpan.className = 'quick-pick-label';
    labelSpan.textContent = r.label;
    span.appendChild(keySpan);
    span.appendChild(labelSpan);
    pills.push(span);
  }
  $strip.replaceChildren(...pills);
}

/** Render post-call replay timeline into the hotkey bar area. */
function renderReplayTimeline() {
  replayShowing = true;
  const $bar = document.getElementById('hotkey-bar');
  const $strip = document.getElementById('quick-pick-strip');
  if (!$bar) return;
  $bar.style.display = ''; // Force visible even if ? toggled it off

  const events = generateReplayTimeline();
  if (events.length === 0) {
    $bar.replaceChildren();
    const msg = document.createElement('span');
    msg.className = 'hotkey-item';
    msg.textContent = 'No keypresses this call';
    $bar.appendChild(msg);
    if ($strip) $strip.replaceChildren();
    return;
  }

  // Render into hotkey bar: compact timeline of events
  const frag = document.createDocumentFragment();
  const header = document.createElement('span');
  header.className = 'hotkey-item';
  header.style.color = '#a5b4fc';
  header.textContent = 'REPLAY';
  frag.appendChild(header);

  const sep = document.createElement('span');
  sep.className = 'hotkey-item';
  sep.style.opacity = '0.3';
  sep.textContent = '|';
  frag.appendChild(sep);

  // Show up to 12 events inline, with timing
  const maxInline = 12;
  const shown = events.slice(0, maxInline);
  for (const ev of shown) {
    const span = document.createElement('span');
    span.className = 'hotkey-item';
    const secs = (ev.offsetMs / 1000).toFixed(0);
    if (ev.type === 'keypress') {
      const kbd = document.createElement('kbd');
      kbd.textContent = ev.key;
      if (ev.isOverride) kbd.style.borderColor = '#f59e0b';
      span.appendChild(kbd);
      span.appendChild(document.createTextNode(' ' + secs + 's'));
    } else {
      span.style.opacity = '0.5';
      span.textContent = ev.from + '\u2192' + ev.to + ' ' + secs + 's';
    }
    frag.appendChild(span);
  }

  if (events.length > maxInline) {
    const more = document.createElement('span');
    more.className = 'hotkey-item';
    more.style.opacity = '0.4';
    more.textContent = '+' + (events.length - maxInline) + ' more';
    frag.appendChild(more);
  }

  $bar.replaceChildren(frag);

  // Summary stats in the breadcrumb strip area
  if ($strip) {
    const keypresses = events.filter(e => e.type === 'keypress');
    const overrides = keypresses.filter(e => e.isOverride);
    const stageChanges = events.filter(e => e.type === 'stage_change');
    const manualChanges = stageChanges.filter(e => e.source === 'manual');
    const aiChanges = stageChanges.filter(e => e.source === 'ai');

    const stats = document.createElement('span');
    stats.className = 'hotkey-item';
    stats.style.fontSize = '10px';
    stats.style.color = '#737373';
    stats.textContent = keypresses.length + ' keys | ' +
      overrides.length + ' overrides | ' +
      manualChanges.length + ' manual / ' + aiChanges.length + ' AI transitions';
    $strip.replaceChildren(stats);
  }
}

/** Log a keypress event to the session audit trail. */
function logKeypress(stage, key, action, value, isOverride) {
  const entry = { ts: Date.now(), stage, key, action, value, isOverride, source: 'manual' };
  logDecision({ type: 'KEYPRESS_LOG', ...entry }, state, state);
}

// ── Hotkeys ────────────────────────────────────────────────────

document.addEventListener('keydown', (e) => {
  const now = Date.now();

  // Track whether Shift is being used solo or as a modifier
  if (e.key === 'Shift') { shiftOnlyPressed = true; return; }
  if (e.shiftKey) { shiftOnlyPressed = false; }

  switch (true) {
    // F9 — Non-connect
    case e.key === 'F9': {
      e.preventDefault();
      dispatch({
        type: 'MANUAL_NON_CONNECT',
        callSid: state.callId,
        atMs: now,
      });
      break;
    }

    // Space — Custom round bookmark (off-script response)
    case e.key === ' ' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      if (['IDLE', 'EXIT', 'ENDED', 'BOOKED'].includes(state.stage)) return;
      e.preventDefault();
      recordRound('CUSTOM', 'off-script', 'custom');
      break;
    }

    // ← — Step back through rounds, then go back a stage
    case e.key === 'ArrowLeft': {
      e.preventDefault();
      const effectiveIdx = roundIndex === -1 ? rounds.length - 1 : roundIndex;
      if (rounds.length > 0 && effectiveIdx > 0) {
        roundIndex = effectiveIdx - 1;
        const round = rounds[roundIndex];
        $nowLine.textContent = round.source === 'custom' ? '(off-script response)' : round.line;
        $nowWhy.textContent = `Round ${roundIndex + 1} — ${round.source}`;
        renderRoundStrip();
        return;
      }
      // No more rounds — go back a stage
      const BACK_MAP = {
        BOOKED:      'CLOSE',
        SEED_EXIT:   'QUALIFIER',
        EXIT:        'CLOSE',
        NON_CONNECT: 'OPENER',
      };
      let target;
      if (BACK_MAP[state.stage]) {
        target = BACK_MAP[state.stage];
      } else {
        const currentIdx = NAV_STAGES.indexOf(state.stage);
        if (currentIdx <= 0) break;
        target = NAV_STAGES[currentIdx - 1];
      }
      dispatch({
        type: 'MANUAL_SET_STAGE',
        callSid: state.callId,
        stage: target,
        atMs: now,
      });
      break;
    }

    // → — Step forward through rounds, then advance stage
    case e.key === 'ArrowRight': {
      e.preventDefault();
      if (roundIndex !== -1 && roundIndex < rounds.length - 1) {
        roundIndex++;
        const round = rounds[roundIndex];
        $nowLine.textContent = round.source === 'custom' ? '(off-script response)' : round.line;
        $nowWhy.textContent = `Round ${roundIndex + 1} — ${round.source}`;
        renderRoundStrip();
        return;
      }
      if (roundIndex !== -1) {
        roundIndex = -1; // Return to live
        render();
        return;
      }
      const nextStage = STAGE_TRANSITIONS[state.stage]?.f7;
      if (!nextStage) break;
      dispatch({
        type: 'MANUAL_SET_STAGE',
        callSid: state.callId,
        stage: nextStage,
        atMs: now,
      });
      break;
    }

    // F10 — Alternate path (branch in decision tree)
    case e.key === 'F10': {
      e.preventDefault();
      const altStage = STAGE_TRANSITIONS[state.stage]?.f8;
      if (!altStage) break;
      dispatch({
        type: 'MANUAL_SET_STAGE',
        callSid: state.callId,
        stage: altStage,
        atMs: now,
      });
      break;
    }

    // 1-4 — Context-sensitive via HOTKEY_CONFIG lookup
    case ['1', '2', '3', '4'].includes(e.key) && !e.ctrlKey && !e.metaKey: {
      const isAltOverride = e.altKey;
      const stageKeys = HOTKEY_CONFIG[state.stage] || [];
      // Alt+N = cross-stage intent override (use bridge config if in bridge family, else objection)
      const lookupStage = isAltOverride
        ? (BRIDGE_STAGES.includes(state.stage) ? 'BRIDGE' : 'CLOSE')
        : state.stage;
      const config = (HOTKEY_CONFIG[lookupStage] || []).find(h => h.key === e.key);
      if (!config) break;
      // Without Alt, blocked stages produce no config entries (empty array)
      if (!isAltOverride && stageKeys.length === 0) break;
      e.preventDefault();
      logKeypress(state.stage, isAltOverride ? `Alt+${e.key}` : e.key, config.action, config.value, isAltOverride);
      if (isAltOverride) {
        // Alt+N: set pending intent for composer WITHOUT dispatching to reducer.
        // This avoids mutating stage/objection state. Composer consumes intent on next render.
        pendingIntent = { type: config.type, value: config.value };
        render();
        renderHotkeyBar();
      } else {
        // Normal 1-4: dispatch to reducer as before (mutates state)
        const actionPayload = config.action === 'MANUAL_SET_BRIDGE_ANGLE'
          ? { type: config.action, callSid: state.callId, angle: config.value, atMs: now }
          : { type: config.action, callSid: state.callId, bucket: config.value, atMs: now };
        dispatch(actionPayload);
      }
      pushRecentKey(isAltOverride ? `Alt+${e.key}` : e.key, config.label);
      break;
    }

    // ? — Toggle legend bar visibility
    case e.key === '?': {
      e.preventDefault();
      legendBarVisible = !legendBarVisible;
      renderHotkeyBar();
      break;
    }

    // Shift+F1 — Reset
    case (e.key === 'F1' && e.shiftKey): {
      e.preventDefault();
      dispatch({
        type: 'END_CALL',
        callSid: state.callId,
        atMs: now,
      });
      saveSession(state, prospectId);

      // Show replay timeline before clearing audit trail
      renderReplayTimeline();

      // Reset after brief delay (replay stays visible until next call)
      setTimeout(() => {
        resetAuditTrail();
        rounds = [];
        roundIndex = -1;
        prospectName = '';
        prospectBusiness = '';
        prospectId = null;
        manualModeActive = false;
        pendingIntent = null;
        legendBarVisible = true;
        recentKeys = [];
        state = createInitialState(PLAYBOOK);
        stopCallTimer();
        callStartTime = null;
        $callTimer.textContent = '00:00';
        render();
        // Don't renderHotkeyBar here — replay timeline is showing
        // It will be replaced by legend on next CALL_STARTED
      }, 100);
      break;
    }

  }
});

document.addEventListener('keyup', (e) => {
  if (e.key === 'Shift' && shiftOnlyPressed) {
    shiftOnlyPressed = false;
    if (state.stage !== 'CLOSE' && state.stage !== 'OBJECTION') return;
    dispatch({ type: 'HEDGE_REQUESTED', callSid: state.callId, atMs: Date.now() });
    return;
  }
  shiftOnlyPressed = false;
});


// ── v2 Turn Orchestrator ──────────────────────────────────────

/**
 * v2 Turn lifecycle orchestrator (spec Section 27).
 * Runs the full pipeline: classify → tone → risk → route → summary → compose → render → log
 * Called after classifyUtterance returns for a final prospect transcript.
 *
 * @param {string} utterance - the prospect's utterance text
 * @param {object} classification - result from classifyUtterance
 */
function processTurn(utterance, classification) {
  // Step 1: classification already done by caller

  // Step 2: Assign tone (rules-based)
  const toneResult = assignTone(utterance, {
    primaryIntent: classification.detectedIntent || classification.bridgeAngle || classification.objectionBucket || null,
  }, state.stage);

  // Apply hysteresis - only update if threshold crossed
  const currentTone = { tone_label: state.tone, tone_confidence: state.toneConfidence };
  if (shouldUpdateTone(currentTone, toneResult, state._consecutiveToneCount || 0)) {
    dispatch({
      type: 'SET_TONE',
      callSid: state.callId,
      tone: toneResult.tone_label,
      toneSource: toneResult.tone_source,
      toneConfidence: toneResult.tone_confidence,
    });
    state._consecutiveToneCount = 0;
  } else if (toneResult.tone_label === state._lastCandidateTone) {
    state._consecutiveToneCount = (state._consecutiveToneCount || 0) + 1;
  } else {
    state._consecutiveToneCount = 0;
  }
  state._lastCandidateTone = toneResult.tone_label;

  // Step 3: Update trajectory and compute risk (for objection-eligible stages)
  const primaryIntent = classification.detectedIntent || classification.objectionBucket || classification.bridgeAngle || classification.qualifierRead || null;
  if (primaryIntent) {
    // Detect secondary intent: check if the utterance also matches a different signal
    const secondaryCheck = detectNewIntents(utterance, state.stage);
    const secondaryIntent = (secondaryCheck && secondaryCheck.intent !== primaryIntent) ? secondaryCheck.intent : null;
    const isCompound = !!secondaryIntent;

    const classObj = {
      primary: { intent: primaryIntent },
      compound: isCompound,
      utterance: utterance,
    };
    const wasSalvage = state.stage === 'OBJECTION' && state.trajectory.turnsInCurrentStage > 0;
    const newTrajectory = updateTrajectory(state.trajectory, classObj, state.stage, wasSalvage);
    const risk = computeRisk(newTrajectory, classObj);

    // Update state trajectory and risk (direct mutation for non-reducer fields)
    state.trajectory = newTrajectory;
    state.risk = risk;
    state.primaryIntent = primaryIntent;
    state.compound = isCompound;
    state._secondaryIntent = secondaryIntent;
  }

  // Step 4: Generate NOW summary BEFORE dispatch (so render() has it ready)
  state.nowSummary = generateNowSummary({
    primaryIntent: primaryIntent,
    tone: state.tone,
    toneConfidence: state.toneConfidence,
  });

  // Step 5: Check for dedicated stage routing via INTENT_STAGE_MAP
  if (classification.detectedIntent && INTENT_STAGE_MAP[classification.detectedIntent]) {
    const targetStage = INTENT_STAGE_MAP[classification.detectedIntent];
    if (targetStage === 'PRICING' && state.stage !== 'PRICING') {
      dispatch({ type: 'PRICING_INTERRUPT', callSid: state.callId });
    } else if (targetStage === 'MINI_PITCH' && state.stage !== 'MINI_PITCH') {
      dispatch({ type: 'MANUAL_SET_STAGE', callSid: state.callId, stage: 'MINI_PITCH', atMs: Date.now() });
    } else if (targetStage === 'WRONG_PERSON' && state.stage !== 'WRONG_PERSON') {
      dispatch({ type: 'MANUAL_SET_STAGE', callSid: state.callId, stage: 'WRONG_PERSON', atMs: Date.now() });
    } else if (targetStage === 'EXIT' && state.stage !== 'EXIT') {
      dispatch({ type: 'MANUAL_SET_STAGE', callSid: state.callId, stage: 'EXIT', atMs: Date.now() });
    }
  }

  // Steps 6-8 (compose + render + log) happen in render() which is called by dispatch
}

// ── Render ─────────────────────────────────────────────────────

function render() {
  // Prospect info
  if (prospectName || prospectBusiness) {
    const parts = [prospectName, prospectBusiness].filter(Boolean);
    $prospectInfo.textContent = parts.join(' \u2014 ');
  } else if (state.callId) {
    $prospectInfo.textContent = state.callId;
  } else {
    $prospectInfo.textContent = 'No active call';
  }

  // Audio mode badge
  if (manualModeActive) {
    $audioModeBadge.textContent = 'MANUAL MODE';
    $audioModeBadge.className = 'audio-mode-badge manual-mode';
  } else {
    $audioModeBadge.textContent = 'DUAL';
    $audioModeBadge.className = 'audio-mode-badge';
  }

  // Stage bar
  renderStageBar();
  renderContextStrip();

  // Side panels
  renderLinesPanel();
  renderObjectionsPanel();
  renderRoundStrip();

  // NOW panel
  $nowPanel.setAttribute('data-stage', state.stage);
  renderObjectionPicker();
  if (roundIndex === -1) {
    const rawLine = state.now?.line || 'Waiting for call...';
    const dedupedLine = dedupProbeLine(rawLine);
    $nowLine.textContent = fillLineTemplate(dedupedLine, currentLineContext());
    $nowWhy.textContent = state.now?.why || '';
  }

  // Confidence badge
  renderConfidenceBadge();

  // v2 center panel render (pendingIntent consumed once then cleared)
  const intentForCompose = pendingIntent;
  pendingIntent = null;
  const activeCard = composeActiveCard({
    stage: state.stage,
    activeObjection: state.activeObjection,
    requestIntent: intentForCompose,
    tone: state.tone,
    deliveryModifier: state.deliveryModifier,
    stageCards: NATIVE_STAGE_CARDS,
    objectionCards: NATIVE_OBJECTION_CARDS,
  });
  // Fill template placeholders ({NAME}, {DAY}, etc.) in card lines
  const ctx = currentLineContext();
  if (activeCard.primaryLine) activeCard.primaryLine = fillLineTemplate(activeCard.primaryLine, ctx);
  if (activeCard.backupLine) activeCard.backupLine = fillLineTemplate(activeCard.backupLine, ctx);
  if (activeCard.clarifyingQuestion) activeCard.clarifyingQuestion = fillLineTemplate(activeCard.clarifyingQuestion, ctx);
  renderV2CenterPanel(activeCard, state);
  // Show "also heard" badge when burst contains signals beyond the current card
  const currentSignal = state.primaryIntent || state.activeObjection || null;
  renderAlsoHeard(recentSignals, currentSignal);
  renderTacticalCard(activeCard);

}

function renderContextStrip() {
  if (!$contextStrip) return;
  const request = currentQueueRequest();
  if (!request || !sprintContext) {
    $contextStrip.classList.remove('visible');
    $contextStrip.innerHTML = '';
    return;
  }

  if (sprintContextTimer) {
    clearInterval(sprintContextTimer);
    sprintContextTimer = null;
  }

  const block = sprintContext.block_active ? (sprintContext.current_block || request.block) : 'BREAK';
  const blockClass = String(block).toLowerCase();
  const sprintProgress = sprintContext.sprint_index && sprintContext.sprints_target_today
    ? `${sprintContext.sprint_index}/${sprintContext.sprints_target_today}`
    : '';
  const dials = `${sprintContext.dials_completed_today || 0}/${sprintContext.dials_target_today || 0} dials`;
  const countdown = contextCountdownText(sprintContext, sprintContextStale);
  const cachedSuffix = sprintContextStale && sprintContextCachedAt
    ? ` • cached ${Math.max(Math.floor((Date.now() - sprintContextCachedAt) / 60000), 0)}m ago`
    : '';

  $contextStrip.innerHTML = `
    <div class="context-strip-top">
      <span class="context-badge ${blockClass}">${_esc(block)}</span>
      ${sprintProgress ? `<span class="context-strip-value">Sprint ${_esc(sprintProgress)}</span>` : ''}
      ${sprintContext.active_segment ? `<span class="context-strip-value">${_esc(sprintContext.active_segment)}</span>` : ''}
      <span class="context-strip-value">${_esc(dials)}</span>
      <span class="context-strip-countdown">${_esc(countdown)}${_esc(cachedSuffix)}</span>
    </div>
    ${sprintContext.instruction ? `<div class="context-strip-note">${_esc(sprintContext.instruction)}</div>` : ''}
  `;
  $contextStrip.classList.add('visible');

  if (sprintContext.next_segment_at || sprintContext.next_block_at) {
    sprintContextTimer = setInterval(() => {
      const countdownEl = $contextStrip.querySelector('.context-strip-countdown');
      if (countdownEl && sprintContext) {
        const cached = sprintContextStale && sprintContextCachedAt
          ? ` • cached ${Math.max(Math.floor((Date.now() - sprintContextCachedAt) / 60000), 0)}m ago`
          : '';
        countdownEl.textContent = `${contextCountdownText(sprintContext, sprintContextStale)}${cached}`;
      }
    }, 60000);
  }
}

// ── Objection picker ──────────────────────────────────────────
// Shows a 2x2 grid of labeled objection cards when in OBJECTION stage
// and no bucket has been selected yet. Replaces the now-line text.

const OBJECTION_CARDS = [
  { key: '1', bucket: 'timing', name: 'Timing', cues: '"busy, bad time, not now, call back"' },
  { key: '2', bucket: 'interest', name: 'Interest', cues: '"not interested, we\'re set, don\'t need"' },
  { key: '3', bucket: 'info', name: 'Info', cues: '"send me info, email me, website"' },
  { key: '4', bucket: 'authority', name: 'Authority', cues: '"not my decision, wife handles, partner"' },
];

let $objectionPicker = null;

function renderObjectionPicker() {
  // Show picker when stage is OBJECTION and no bucket selected yet
  const showPicker = state.stage === 'OBJECTION' && !state.lastObjectionBucket;

  if (showPicker && !$objectionPicker) {
    // Create picker
    $objectionPicker = document.createElement('div');
    $objectionPicker.className = 'objection-picker';

    for (const card of OBJECTION_CARDS) {
      const el = document.createElement('div');
      el.className = 'objection-card';
      el.innerHTML =
        '<div class="objection-card-header">' +
          '<span class="objection-card-key">' + card.key + '</span>' +
          '<span class="objection-card-name">' + card.name + '</span>' +
        '</div>' +
        '<div class="objection-card-cues">' + card.cues + '</div>';
      el.addEventListener('click', () => {
        dispatch({
          type: 'MANUAL_SET_OBJECTION',
          callSid: state.callId,
          bucket: card.bucket,
          atMs: Date.now(),
        });
      });
      $objectionPicker.appendChild(el);
    }

    // Insert before the now-line
    $nowPanel.insertBefore($objectionPicker, $nowLine);
    $nowLine.style.display = 'none';
    $nowWhy.style.display = 'none';
    $previewHint.style.display = 'none';
  } else if (!showPicker && $objectionPicker) {
    // Remove picker
    $objectionPicker.remove();
    $objectionPicker = null;
    $nowLine.style.display = '';
    $nowWhy.style.display = '';
    $previewHint.style.display = '';
  }
}

// ── Side panel renderers ───────────────────────────────────────

function renderLinesPanel() {
  if (!$linesFeed) return;
  $linesFeed.replaceChildren();

  const stageLines = linesForStage(state.stage, PLAYBOOK);
  if (stageLines.length) {
    $linesFeed.appendChild(buildSidePanelSection('CURRENT STAGE', stageLines, 'stage', 'lines'));
  }
  if (PLAYBOOK.powerLines?.length) {
    $linesFeed.appendChild(buildSidePanelSection('POWER LINES', PLAYBOOK.powerLines, 'power', 'lines'));
  }
  if (PLAYBOOK.recoveryLines?.length) {
    $linesFeed.appendChild(buildSidePanelSection('RECOVERY', PLAYBOOK.recoveryLines, 'recovery', 'lines'));
  }
}

function renderObjectionsPanel() {
  if (!$objectionsFeed) return;
  $objectionsFeed.replaceChildren();

  const entries = Object.entries(PLAYBOOK.objections).map(([bucket, data]) => ({
    label: `${bucket.toUpperCase()} — ${data.keywords.slice(0, 3).join(', ')}`,
    line: data.reset,
  }));
  $objectionsFeed.appendChild(buildSidePanelSection('OBJECTION RESETS', entries, 'objection', 'objection'));
}

function buildSidePanelSection(title, entries, kind, source) {
  const section = document.createElement('div');
  section.className = 'line-bank-section';

  const heading = document.createElement('div');
  heading.className = 'line-bank-section-title';
  heading.textContent = title;
  section.appendChild(heading);

  for (const entry of entries) {
    const row = document.createElement('button');
    row.type = 'button';
    row.className = 'line-bank-row ' + kind;

    const label = document.createElement('span');
    label.className = 'line-bank-label';
    label.textContent = entry.label || entry.tag;

    const text = document.createElement('span');
    text.className = 'line-bank-text';
    text.textContent = fillLineTemplate(entry.line, currentLineContext());

    row.appendChild(label);
    row.appendChild(text);
    row.addEventListener('click', () => {
      const filledLine = fillLineTemplate(entry.line, currentLineContext());
      recordRound(filledLine, entry.label || entry.tag, source);
      dispatch({
        type: 'LINE_BANK_SELECT',
        callSid: state.callId,
        line: filledLine,
        atMs: Date.now(),
      });
    });
    section.appendChild(row);
  }

  return section;
}

// ── Round history ──────────────────────────────────────────────

function recordRound(line, why, source) {
  if (roundIndex !== -1) {
    rounds = rounds.slice(0, roundIndex + 1);
  }
  rounds.push({ stage: state.stage, line, why, source });
  roundIndex = -1;
  renderRoundStrip();
}

function renderRoundStrip() {
  if (!$roundStrip) return;
  $roundStrip.replaceChildren();

  const effectiveIndex = roundIndex === -1 ? rounds.length - 1 : roundIndex;

  rounds.forEach((round, i) => {
    const bubble = document.createElement('div');
    bubble.className = 'round-bubble';

    if (i === effectiveIndex && rounds.length > 0) {
      bubble.classList.add('current');
    } else if (i < effectiveIndex) {
      bubble.classList.add('past');
    }

    bubble.textContent = round.source === 'custom' ? '\u2726' : String(i + 1);
    bubble.title = round.line === 'CUSTOM' ? 'Off-script' : round.line;

    bubble.addEventListener('click', () => {
      roundIndex = i;
      $nowLine.textContent = round.source === 'custom' ? '(off-script response)' : round.line;
      $nowWhy.textContent = `Round ${i + 1} \u2014 ${round.source}`;
      renderRoundStrip();
    });

    $roundStrip.appendChild(bubble);
  });
}


function currentLineContext() {
  return {
    name: prospectName,
    business: prospectBusiness,
    day: state.scheduledDay,
  };
}

// Probe dedup: never show the exact same probe line twice in one call.
// If the line was already used, return a situational variant.
const PROBE_VARIANTS = [
  "When you can't get to a new customer call right away, what usually happens?",
  "When you're on a job and the phone rings, what usually happens to that customer?",
  "What happens after 5 or on weekends when a new customer calls in?",
  "When she's already helping someone and another call comes in, what happens then?",
  "What happens when you're already tied up and another call comes in?",
];
function dedupProbeLine(line) {
  // Only dedup probe/bridge/reset lines (not openers, closes, pitches, etc.)
  // Probes are the pain-discovery questions that can repeat across stages.
  const isProbe = /what (?:usually )?happens|when .+ calls? (?:come|comes) in/i.test(line);
  if (!isProbe) {
    return line;
  }
  if (!usedProbeLines.has(line)) {
    usedProbeLines.add(line);
    return line;
  }
  // Find an unused variant
  for (const variant of PROBE_VARIANTS) {
    if (!usedProbeLines.has(variant)) {
      usedProbeLines.add(variant);
      return variant;
    }
  }
  // All variants used (5+ probes in one call is unlikely) — use the line anyway
  return line;
}

/** Flash the stage bar to indicate transition source (green=manual, blue=AI). */
function flashStageTransition(source) {
  const $bar = document.getElementById('stageBar');
  if (!$bar) return;
  $bar.classList.remove('flash-manual', 'flash-ai');
  // Force reflow to restart animation
  void $bar.offsetWidth;
  $bar.classList.add(source === 'manual' ? 'flash-manual' : 'flash-ai');
  setTimeout(() => $bar.classList.remove('flash-manual', 'flash-ai'), 400);
}

function renderStageBar() {
  const stageOrder = STAGE_DISPLAY.map((s) => s.key);
  const currentIdx = stageOrder.indexOf(state.stage);
  // For stages not in display list (BOOKED, EXIT, etc.), find nearest display stage
  const effectiveIdx = currentIdx >= 0 ? currentIdx : stageOrder.indexOf(mapToDisplayStage(state.stage));

  const pills = $stageBar.querySelectorAll('.stage-pill');
  pills.forEach((pill) => {
    const pillStage = pill.getAttribute('data-stage');
    const pillIdx = stageOrder.indexOf(pillStage);

    pill.className = 'stage-pill';

    if (pillStage === state.stage || (currentIdx < 0 && pillStage === mapToDisplayStage(state.stage))) {
      pill.classList.add('current');
    } else if (pillIdx < effectiveIdx && effectiveIdx >= 0) {
      pill.classList.add('past');
    } else {
      pill.classList.add('future');
    }
  });
}

function mapToDisplayStage(stage) {
  switch (stage) {
    case 'SEED_EXIT': return 'QUALIFIER';
    case 'NON_CONNECT': return 'IDLE';
    case 'ENDED': return 'IDLE';
    case 'CONFUSION': return 'MINI_PITCH';
    case 'PERMISSION_MOMENT': return 'OPENER';
    default: return stage;
  }
}

function renderConfidenceBadge() {
  const source = state.now?.classificationSource || 'none';
  let label = '';
  let cls = 'confidence-badge';

  if (manualModeActive) {
    label = 'MANUAL MODE';
    cls += ' manual-mode-badge';
  } else {
    switch (source) {
      case 'rules':
        label = 'RULE';
        cls += ' rules';
        break;
      case 'llm':
        label = 'LLM';
        cls += ' llm';
        break;
      case 'manual':
        label = 'MANUAL';
        cls += ' manual';
        break;
      case 'fallback':
        label = 'FALLBACK';
        cls += ' fallback';
        break;
      default:
        label = '';
        cls += ' manual';
        break;
    }
  }

  $confidenceBadge.textContent = label;
  $confidenceBadge.className = cls;
}

// ── Initial render ─────────────────────────────────────────────

loadSprintContext();
render();

console.log('[hud/ui] Sales HUD initialized. Listening on BroadcastChannel "calllock-hud".');
