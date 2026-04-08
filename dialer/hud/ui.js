// dialer/hud/ui.js — DOM rendering, hotkeys, BroadcastChannel listener
// Vanilla JS ES module — no build step, no TypeScript.

import { PLAYBOOK, fillLineTemplate, linesForStage } from './playbook.js';
import { createInitialState, hudReducer, bandFromScore } from './reducer.js';
import { classifyUtterance, shouldCallLlmFallback, isUsableDeterministicResult, detectNewIntents } from './classifier.js';
import { captureSession, resetAuditTrail, logDecision, saveSession } from './session.js';
import { classifyWithLlm, isLlmBackoffActive } from './llm.js';
import { assignTone, shouldUpdateTone } from './tone.js';
import { computeRisk, updateTrajectory } from './risk.js';
import { composeActiveCard, generateNowSummary } from './composer.js';
import { NATIVE_STAGE_CARDS, NATIVE_OBJECTION_CARDS } from './cards.js';
import { INTENT_STAGE_MAP, GLOBAL_HOTKEYS, OBJECTION_HOTKEYS, BRIDGE_HOTKEYS } from './taxonomy.js';
import { renderV2CenterPanel, renderProspectContext, renderPauseStrip, renderLeftPane, renderRightPane, renderCompactIdentity } from './render-v2.js';

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
let prospectMetro = '';
let prospectId = null;

const METRO_CITY = {
  TX: 'Houston',
  FL: 'Orlando',
  MI: 'West Bloomfield',
  IL: 'Chicago',
  AZ: 'Phoenix',
};
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
const $hotkeyBar = document.getElementById('hotkey-bar');

// Populate hotkey legend from taxonomy (hidden by default)
for (const h of GLOBAL_HOTKEYS) {
  const span = document.createElement('span');
  span.className = 'hotkey-item';
  const kbd = document.createElement('kbd');
  kbd.textContent = h.key;
  span.appendChild(kbd);
  span.appendChild(document.createTextNode(h.label));
  $hotkeyBar.appendChild(span);
}
$hotkeyBar.style.display = 'none';

// Static hotkey bars — render once, always visible
const $objHotkeyBar = document.getElementById('objection-hotkey-bar');
const $bridgeHotkeyBar = document.getElementById('bridge-hotkey-bar');
let _hotkeyBarVisible = false;

for (const h of OBJECTION_HOTKEYS) {
  const span = document.createElement('span');
  span.className = 'hotkey-item';
  const kbd = document.createElement('kbd');
  kbd.textContent = h.key;
  span.appendChild(kbd);
  span.appendChild(document.createTextNode(h.label));
  $objHotkeyBar.appendChild(span);
}

for (const h of BRIDGE_HOTKEYS) {
  const span = document.createElement('span');
  span.className = 'hotkey-item';
  const kbd = document.createElement('kbd');
  kbd.textContent = h.key;
  span.appendChild(kbd);
  span.appendChild(document.createTextNode(h.label));
  $bridgeHotkeyBar.appendChild(span);
}

// ── FAQ box (always-on, rendered once) ───────────────────────

const $faqBox = document.getElementById('faq-box');

// Intent/objection → FAQ item id mapping for smart highlight
const FAQ_HIGHLIGHT_MAP = {
  // Intents (from processTurn phase 2)
  confusion: 'what',
  // Objection buckets (from state.activeObjection)
  existing_coverage: 'switch',
  answering_service: 'vs_answering',
  tried_ai: 'tried_ai',
};

let _faqHighlightTimer = null;

function renderFaqBox(prospectCtx) {
  if (!$faqBox) return;
  $faqBox.textContent = '';

  const header = document.createElement('div');
  header.className = 'faq-header';
  header.id = 'faq-header';
  header.textContent = 'QUICK ANSWERS';
  $faqBox.appendChild(header);

  for (const item of PLAYBOOK.faq) {
    const row = document.createElement('div');
    row.className = 'faq-item';
    row.dataset.faqId = item.id;

    const q = document.createElement('div');
    q.className = 'faq-question';
    q.textContent = item.question;

    const a = document.createElement('div');
    a.className = 'faq-answer';
    // Personalize if prospect context available
    let answerText = item.answer;
    if (prospectCtx) {
      if (prospectCtx.trade && item.id === 'what') {
        answerText = answerText.replace('your phone', prospectCtx.trade + ' calls');
      }
      if (prospectCtx.fsm_tool && item.id === 'system') {
        answerText = 'Works with ' + prospectCtx.fsm_tool + '. No switching required.';
      }
      if (prospectCtx.location && item.id === 'afterhours') {
        answerText = answerText.replace("when you're on a job", "when you're on a job in " + prospectCtx.location);
      }
    }
    a.textContent = answerText;

    row.appendChild(q);
    row.appendChild(a);
    row.addEventListener('click', () => row.classList.toggle('expanded'));
    $faqBox.appendChild(row);
  }

  // Competitor cheat sheet (conditional)
  if (prospectCtx && prospectCtx.competitor && PLAYBOOK.competitors[prospectCtx.competitor]) {
    const comp = PLAYBOOK.competitors[prospectCtx.competitor];
    const section = document.createElement('div');
    section.className = 'faq-competitor-section';

    const compHeader = document.createElement('div');
    compHeader.className = 'faq-competitor-header';
    compHeader.textContent = 'VS. ' + comp.name.toUpperCase();
    section.appendChild(compHeader);

    const compLine = document.createElement('div');
    compLine.className = 'faq-competitor-item';
    compLine.textContent = comp.line;
    section.appendChild(compLine);

    $faqBox.appendChild(section);
  }
}

function highlightFaqItem(faqId) {
  if (!$faqBox || !faqId) return;
  // Clear previous
  clearTimeout(_faqHighlightTimer);
  const prev = $faqBox.querySelector('.faq-highlight');
  if (prev) prev.classList.remove('faq-highlight');

  const target = $faqBox.querySelector(`[data-faq-id="${faqId}"]`);
  if (!target) return;
  target.classList.add('faq-highlight');
  target.scrollIntoView({ block: 'nearest', behavior: 'smooth' });

  _faqHighlightTimer = setTimeout(() => {
    target.classList.remove('faq-highlight');
  }, 3000);
}

// Render FAQ on init (will re-render when prospect context arrives)
renderFaqBox(null);

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
    // Clear round history on stage change — rounds are per-stage context
    rounds = [];
    roundIndex = -1;
    renderRoundStrip();
    // Delay pause strip by 3s so rep can read the line first
    clearTimeout(pauseStripTimer);
    clearTimeout(pauseStripSilenceTimer);
    pauseStripTimer = setTimeout(() => activatePauseStrip(), 3000);
  }
  if (action.type === 'TRANSCRIPT_FINAL') {
    deactivatePauseStrip();
  }
  logDecision(action, prevState, state);
  render();
}

// ── BroadcastChannel ───────────────────────────────────────────

const channel = new BroadcastChannel('calllock-hud');
const queueParams = new URLSearchParams(window.location.search);

channel.addEventListener('message', (event) => {
  const msg = event.data;
  if (!msg || !msg.type) return;

  switch (msg.type) {
    case 'CALL_STARTED': {
      // Guard: reject CALL_STARTED without a callSid (prevents poisoning state.callId with undefined)
      if (!msg.callSid) {
        console.warn('[HUD] Ignoring CALL_STARTED — missing callSid');
        break;
      }

      // Guard: ignore duplicate CALL_STARTED for the same call
      if (msg.callSid === state.callId) break;

      // Guard: reject mid-call reset — only allow reset from terminal/idle stages
      const resettableStages = ['IDLE', 'EXIT', 'ENDED', 'BOOKED', 'SEED_EXIT', 'NON_CONNECT'];
      if (state.callId && !resettableStages.includes(state.stage)) {
        console.warn('[HUD] Ignoring CALL_STARTED — active call in stage:', state.stage, 'callId:', state.callId);
        break;
      }

      // Auto-reset
      resetAuditTrail();
      usedProbeLines.clear();
      lastDedupedInput = null;
      lastDedupedOutput = null;
      prospectName = msg.prospectName || '';
      prospectBusiness = msg.businessName || '';
      prospectMetro = msg.metro || '';
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
      renderFaqBox(msg.prospectContext || null);
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
      // Clear prospect context from panes (Amendment 10: prevent stale data in IDLE)
      renderProspectContext(null);
      renderCompactIdentity(null);
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
  const turn = {
    speaker: 'prospect',
    text: msg.text,
    atMs: msg.atMs || Date.now(),
    utteranceId: msg.utteranceId,
  };

  if (isUsableDeterministicResult(result)) {
    // High/medium confidence: commit via reducer
    const stageBeforeDispatch = state.stage;
    dispatch({
      type: 'TRANSCRIPT_FINAL',
      callSid: state.callId,
      turn,
      rule: result,
      seq: msg.seq,
      atMs: msg.atMs || Date.now(),
    });
    // v2: run turn lifecycle after dispatch updates state
    processTurn(msg.text, result, stageBeforeDispatch);
  } else {
    // Low confidence: add transcript but don't change state
    const stageBeforeDispatch = state.stage;
    dispatch({
      type: 'TRANSCRIPT_FINAL',
      callSid: state.callId,
      turn,
      rule: result,
      seq: msg.seq,
      atMs: msg.atMs || Date.now(),
    });
    // v2: run turn lifecycle even for low-confidence (tone/risk still useful)
    processTurn(msg.text, result, stageBeforeDispatch);

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
      // If in live mode and rounds exist, enter history at last round first
      if (roundIndex === -1 && rounds.length > 0) {
        roundIndex = rounds.length - 1;
        const round = rounds[roundIndex];
        $nowLine.textContent = round.source === 'custom' ? '(off-script response)' : round.line;
        $nowWhy.textContent = `Round ${roundIndex + 1} — ${round.source}`;
        renderRoundStrip();
        return;
      }
      // Step back through round history
      if (roundIndex > 0) {
        roundIndex--;
        const round = rounds[roundIndex];
        $nowLine.textContent = round.source === 'custom' ? '(off-script response)' : round.line;
        $nowWhy.textContent = `Round ${roundIndex + 1} — ${round.source}`;
        renderRoundStrip();
        return;
      }
      // At round 0 or no rounds — go back a stage
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

    // 1-4 — Context-sensitive: bridge angles (BRIDGE/OPENER) or objections (any other stage)
    // Objections available everywhere except IDLE/ENDED — trust the operator.
    case e.key === '1' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      if (state.stage === 'IDLE' || state.stage === 'ENDED') break;
      e.preventDefault();
      if (state.stage === 'BRIDGE' || state.stage === 'OPENER') {
        dispatch({ type: 'MANUAL_SET_BRIDGE_ANGLE', callSid: state.callId, angle: 'missed_calls', atMs: now });
      } else {
        dispatch({ type: 'MANUAL_SET_OBJECTION', callSid: state.callId, bucket: 'timing', atMs: now });
      }
      break;
    }

    case e.key === '2' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      if (state.stage === 'IDLE' || state.stage === 'ENDED') break;
      e.preventDefault();
      if (state.stage === 'BRIDGE' || state.stage === 'OPENER') {
        dispatch({ type: 'MANUAL_SET_BRIDGE_ANGLE', callSid: state.callId, angle: 'competition', atMs: now });
      } else {
        dispatch({ type: 'MANUAL_SET_OBJECTION', callSid: state.callId, bucket: 'interest', atMs: now });
      }
      break;
    }

    case e.key === '3' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      if (state.stage === 'IDLE' || state.stage === 'ENDED') break;
      e.preventDefault();
      if (state.stage === 'BRIDGE' || state.stage === 'OPENER') {
        dispatch({ type: 'MANUAL_SET_BRIDGE_ANGLE', callSid: state.callId, angle: 'overwhelmed', atMs: now });
      } else {
        dispatch({ type: 'MANUAL_SET_OBJECTION', callSid: state.callId, bucket: 'info', atMs: now });
      }
      break;
    }

    case e.key === '4' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      if (state.stage === 'IDLE' || state.stage === 'ENDED') break;
      e.preventDefault();
      if (state.stage === 'BRIDGE' || state.stage === 'OPENER') {
        dispatch({ type: 'MANUAL_SET_BRIDGE_ANGLE', callSid: state.callId, angle: 'ad_spend', atMs: now });
      } else {
        dispatch({ type: 'MANUAL_SET_OBJECTION', callSid: state.callId, bucket: 'authority', atMs: now });
      }
      break;
    }

    // 5 — Objection: existing_coverage
    case e.key === '5' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      if (state.stage === 'IDLE' || state.stage === 'ENDED') break;
      e.preventDefault();
      dispatch({ type: 'MANUAL_SET_OBJECTION', callSid: state.callId, bucket: 'existing_coverage', atMs: now });
      break;
    }

    // 6 — Objection: answering_service
    case e.key === '6' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      if (state.stage === 'IDLE' || state.stage === 'ENDED') break;
      e.preventDefault();
      dispatch({ type: 'MANUAL_SET_OBJECTION', callSid: state.callId, bucket: 'answering_service', atMs: now });
      break;
    }

    // 0 — Jump to PRICING stage
    case e.key === '0' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      if (state.stage === 'IDLE' || state.stage === 'ENDED') break;
      e.preventDefault();
      dispatch({ type: 'MANUAL_SET_STAGE', callSid: state.callId, stage: 'PRICING', atMs: now });
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

      // Reset after brief delay
      setTimeout(() => {
        resetAuditTrail();
        rounds = [];
        roundIndex = -1;
        prospectName = '';
        prospectBusiness = '';
        prospectMetro = '';
        prospectId = null;
        manualModeActive = false;
        state = createInitialState(PLAYBOOK);
        stopCallTimer();
        callStartTime = null;
        $callTimer.textContent = '00:00';
        // Clear prospect context (Amendment 10)
        renderProspectContext(null);
        renderCompactIdentity(null);
        render();
      }, 100);
      break;
    }

    // ? — Toggle global nav legend (objection bar is always visible)
    case e.key === '?': {
      e.preventDefault();
      _hotkeyBarVisible = !_hotkeyBarVisible;
      $hotkeyBar.style.display = _hotkeyBarVisible ? '' : 'none';
      break;
    }

    // ` (backtick) — Jump to FAQ box
    case e.key === '`' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      if (document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA')) break;
      e.preventDefault();
      const faqHeader = document.getElementById('faq-header');
      if (faqHeader) {
        faqHeader.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        faqHeader.style.color = '#fff';
        setTimeout(() => { faqHeader.style.color = ''; }, 1500);
      }
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
function processTurn(utterance, classification, stageBeforeDispatch) {
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
  const primaryIntent = classification.detectedIntent || classification.objectionBucket || classification.bridgeAngle || null;
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
  // Guard: don't route back to a stage the reducer just advanced FROM.
  // Example: prospect in MINI_PITCH says "after hours goes to voicemail, what are you selling?"
  // Reducer advances MINI_PITCH → BRIDGE (pain signal), but confusion intent would pull back
  // to MINI_PITCH. The advance should win.
  if (classification.detectedIntent && INTENT_STAGE_MAP[classification.detectedIntent]) {
    const targetStage = INTENT_STAGE_MAP[classification.detectedIntent];
    const justCameFrom = stageBeforeDispatch === targetStage && state.stage !== targetStage;
    if (justCameFrom) {
      // Stage just advanced past targetStage — don't reverse it
    } else if (targetStage === 'PRICING' && state.stage !== 'PRICING') {
      dispatch({ type: 'PRICING_INTERRUPT', callSid: state.callId });
    } else if (targetStage === 'MINI_PITCH' && state.stage !== 'MINI_PITCH') {
      dispatch({ type: 'MANUAL_SET_STAGE', callSid: state.callId, stage: 'MINI_PITCH', atMs: Date.now() });
    } else if (targetStage === 'WRONG_PERSON' && state.stage !== 'WRONG_PERSON') {
      dispatch({ type: 'MANUAL_SET_STAGE', callSid: state.callId, stage: 'WRONG_PERSON', atMs: Date.now() });
    } else if (targetStage === 'EXIT' && state.stage !== 'EXIT') {
      dispatch({ type: 'MANUAL_SET_STAGE', callSid: state.callId, stage: 'EXIT', atMs: Date.now() });
    }
    // Smart highlight: intent-driven FAQ highlight
    const faqTarget = FAQ_HIGHLIGHT_MAP[classification.detectedIntent];
    if (faqTarget) highlightFaqItem(faqTarget);
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

  // Compose active card FIRST (needed by both center panel and side panes)
  const activeCard = composeActiveCard({
    stage: state.stage,
    activeObjection: state.activeObjection,
    tone: state.tone,
    deliveryModifier: state.deliveryModifier,
    stageCards: NATIVE_STAGE_CARDS,
    objectionCards: NATIVE_OBJECTION_CARDS,
  });
  const ctx = currentLineContext();
  if (activeCard.primaryLine) activeCard.primaryLine = fillLineTemplate(activeCard.primaryLine, ctx);
  if (activeCard.backupLine) activeCard.backupLine = fillLineTemplate(activeCard.backupLine, ctx);
  if (activeCard.clarifyingQuestion) activeCard.clarifyingQuestion = fillLineTemplate(activeCard.clarifyingQuestion, ctx);

  // Side panels (stage-aware orchestrators)
  const paneDeps = {
    playbook: PLAYBOOK,
    buildSection: buildSidePanelSection,
    lineContext: ctx,
  };
  renderLeftPane(state.stage, activeCard, state.prospectContext, paneDeps);
  renderRightPane(state.stage, activeCard, paneDeps);
  renderRoundStrip();

  // NOW panel
  $nowPanel.setAttribute('data-stage', state.stage);
  renderObjectionPicker();

  // Smart highlight: check activeObjection for FAQ match
  if (state.activeObjection && FAQ_HIGHLIGHT_MAP[state.activeObjection]) {
    highlightFaqItem(FAQ_HIGHLIGHT_MAP[state.activeObjection]);
  }

  if (roundIndex === -1) {
    const rawLine = state.now?.line || 'Waiting for call...';
    const dedupedLine = dedupProbeLine(rawLine);
    $nowLine.textContent = fillLineTemplate(dedupedLine, currentLineContext());
    $nowWhy.textContent = state.now?.why || '';
  }

  // Confidence badge
  renderConfidenceBadge();

  // v2 center panel render
  renderV2CenterPanel(activeCard, state);

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
// Shows a 3x2 grid of labeled objection cards when in OBJECTION stage
// and no bucket has been selected yet. Replaces the now-line text.

const OBJECTION_CARDS = [
  { key: '1', bucket: 'timing', name: 'Timing', cues: '"busy, bad time, not now, call back"' },
  { key: '2', bucket: 'interest', name: 'Interest', cues: '"not interested, we\'re set, don\'t need"' },
  { key: '3', bucket: 'info', name: 'Info', cues: '"send me info, email me, website"' },
  { key: '4', bucket: 'authority', name: 'Authority', cues: '"not my decision, wife handles, partner"' },
  { key: '5', bucket: 'existing_coverage', name: 'Covered', cues: '"have a receptionist, wife answers, we\'re covered"' },
  { key: '6', bucket: 'answering_service', name: 'Ans. Svc', cues: '"use Smith, use Ruby, answering service"' },
];

const BRIDGE_CARDS = [
  { key: '1', action: 'missed_calls', name: 'Missed', cues: 'voicemail, callback, wife, office' },
  { key: '2', action: 'competition', name: 'Comp', cues: 'slow, growth, competitor, losing' },
  { key: '3', action: 'overwhelmed', name: 'Overwhelm', cues: 'busy, stretched, do it all, rushed' },
  { key: '4', action: 'ad_spend', name: 'Ad $', cues: 'Google, LSA, Angi, Thumbtack, ads, spending' },
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
    location: METRO_CITY[prospectMetro] || 'Detroit',
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
let lastDedupedInput = null;  // Tracks last input to avoid re-dedup on re-renders
let lastDedupedOutput = null;
function dedupProbeLine(line) {
  // Same line as last render — return cached result (avoids re-dedup on re-render)
  if (line === lastDedupedInput) return lastDedupedOutput;

  // Only dedup probe/bridge/reset lines (not openers, closes, pitches, etc.)
  // Probes are the pain-discovery questions that can repeat across stages.
  const isProbe = /what (?:usually )?happens|when .+ calls? (?:come|comes) in/i.test(line);
  if (!isProbe) {
    lastDedupedInput = line;
    lastDedupedOutput = line;
    return line;
  }
  if (!usedProbeLines.has(line)) {
    usedProbeLines.add(line);
    lastDedupedInput = line;
    lastDedupedOutput = line;
    return line;
  }
  // Find an unused variant
  for (const variant of PROBE_VARIANTS) {
    if (!usedProbeLines.has(variant)) {
      usedProbeLines.add(variant);
      lastDedupedInput = line;
      lastDedupedOutput = variant;
      return variant;
    }
  }
  // All variants used (5+ probes in one call is unlikely) — use the line anyway
  lastDedupedInput = line;
  lastDedupedOutput = line;
  return line;
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
