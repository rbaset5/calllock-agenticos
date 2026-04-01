// dialer/hud/ui.js — DOM rendering, hotkeys, BroadcastChannel listener
// Vanilla JS ES module — no build step, no TypeScript.

import { PLAYBOOK, fillLineTemplate, linesForStage } from './playbook.js';
import { createInitialState, hudReducer, bandFromScore } from './reducer.js';
import { classifyUtterance, shouldCallLlmFallback, isUsableDeterministicResult } from './classifier.js';
import { captureSession, resetAuditTrail, logDecision, saveSession } from './session.js';
import { classifyWithLlm } from './llm.js';

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
let lineBankOpen = false;
let sprintContext = null;
let sprintContextStale = false;
let sprintContextCachedAt = null;
let sprintContextTimer = null;

// Decision tree navigation: F7 = primary path, F8 = alternate path
const STAGE_TRANSITIONS = {
  IDLE:        { f7: 'OPENER',    f8: null },
  GATEKEEPER:  { f7: 'OPENER',    f8: 'EXIT' },
  OPENER:      { f7: 'BRIDGE',    f8: 'EXIT' },
  BRIDGE:      { f7: 'QUALIFIER', f8: 'SEED_EXIT' },
  QUALIFIER:   { f7: 'CLOSE',     f8: 'SEED_EXIT' },
  CLOSE:       { f7: 'BOOKED',    f8: 'OBJECTION' },
  OBJECTION:   { f7: 'CLOSE',     f8: 'EXIT' },
  SEED_EXIT:   { f7: 'EXIT',      f8: null },
  BOOKED:      { f7: 'EXIT',      f8: null },
  NON_CONNECT: { f7: 'EXIT',      f8: null },
  EXIT:        { f7: null,         f8: null },
};

// Stage hints shown in the why text after manual navigation
const STAGE_HINTS = {
  IDLE:        'F7 to start call',
  GATEKEEPER:  'F7 got owner · F8 not available',
  OPENER:      'F7 when they respond · F8 dead end',
  BRIDGE:      'F7 after bridge line · F8 no pain → seed exit',
  QUALIFIER:   'F7 pain → close · F8 no pain → exit',
  CLOSE:       'F7 yes! → booked · F8 objection · H hedge',
  OBJECTION:   'F7 try close · F8 give up · 1-4 new objection',
  SEED_EXIT:   'F7 wrap up',
  BOOKED:      'F7 call done',
  NON_CONNECT: 'F7 after voicemail',
  EXIT:        'Call complete',
};

// Linear ordering for F6 (back) only — IDLE excluded (F7 from IDLE → OPENER is one-way)
const NAV_STAGES = ['GATEKEEPER', 'OPENER', 'BRIDGE', 'QUALIFIER', 'CLOSE', 'OBJECTION'];

// Stage display labels for the pill bar
const STAGE_DISPLAY = [
  { key: 'IDLE', label: 'IDLE' },
  { key: 'GATEKEEPER', label: 'GK' },
  { key: 'OPENER', label: 'OPEN' },
  { key: 'BRIDGE', label: 'BRIDGE' },
  { key: 'QUALIFIER', label: 'QUAL' },
  { key: 'CLOSE', label: 'CLOSE' },
  { key: 'OBJECTION', label: 'OBJ' },
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
const $transcriptFeed = document.getElementById('transcriptFeed');

// ── Dispatch ───────────────────────────────────────────────────

function dispatch(action) {
  const prevState = state;
  state = hudReducer(state, action, PLAYBOOK);
  if (state.stage !== prevState.stage || state.stage === 'IDLE') {
    lineBankOpen = false;
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
      // Auto-reset
      resetAuditTrail();
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
      break;
    }

    case 'TRANSCRIPT': {
      // Validate callSid to prevent cross-call bleed
      if (msg.callSid && state.callId && msg.callSid !== state.callId) break;
      if (!msg.isFinal) {
        handleInterimTranscript(msg);
      } else if (msg.speaker === 'prospect') {
        handleFinalProspectTranscript(msg);
      } else {
        addTranscriptTurn('REP', msg.text, msg.atMs);
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
      dispatch({
        type: 'END_CALL',
        callSid: state.callId,
        atMs: Date.now(),
      });
      const endedState = state;
      const endedProspectId = prospectId;
      const endedSession = captureSession(endedState);
      stopCallTimer();
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
  addTranscriptTurn('PROSPECT', msg.text, msg.atMs);

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
    dispatch({
      type: 'TRANSCRIPT_FINAL',
      callSid: state.callId,
      turn,
      rule: result,
      seq: msg.seq,
      atMs: msg.atMs || Date.now(),
    });
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

    // Try LLM fallback
    if (shouldCallLlmFallback(result)) {
      triggerLlmFallback(msg.text, msg.utteranceId, msg.seq);
    }
  }
}

async function triggerLlmFallback(utterance, utteranceId, seq) {
  const result = await classifyWithLlm(
    utterance,
    state.stage,
    {
      bridgeAngle: state.bridgeAngle,
      lastObjectionBucket: state.lastObjectionBucket,
    },
    utteranceId,
  );

  if (result) {
    dispatch({
      type: 'LLM_RESULT',
      callSid: state.callId,
      utteranceId,
      seq,
      result: {
        ...result,
        band: bandFromScore(result.confidence ?? 0.7),
        why: result.why || 'LLM classification',
        utterance,
      },
      atMs: Date.now(),
    });
  } else {
    dispatch({
      type: 'LLM_FAILED',
      callSid: state.callId,
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

// ── Transcript feed ────────────────────────────────────────────

function addTranscriptTurn(speaker, text, atMs) {
  const el = document.createElement('div');
  el.className = 'transcript-turn';

  const speakerEl = document.createElement('span');
  speakerEl.className = 'speaker ' + (speaker === 'PROSPECT' ? 'prospect' : 'rep');
  speakerEl.textContent = speaker;

  const textEl = document.createElement('span');
  textEl.className = 'text' + (speaker === 'PROSPECT' ? ' prospect-text' : '');
  textEl.textContent = text;

  const tsEl = document.createElement('span');
  tsEl.className = 'ts';
  tsEl.textContent = atMs ? formatTimestamp(atMs) : '';

  el.appendChild(speakerEl);
  el.appendChild(document.createTextNode(' '));
  el.appendChild(textEl);
  el.appendChild(tsEl);

  $transcriptFeed.appendChild(el);
  $transcriptFeed.scrollTop = $transcriptFeed.scrollHeight;
}

function formatTimestamp(atMs) {
  if (!callStartTime) return '';
  const elapsed = Math.floor((atMs - callStartTime) / 1000);
  if (elapsed < 0) return '';
  const m = Math.floor(elapsed / 60);
  const s = elapsed % 60;
  return m + ':' + String(s).padStart(2, '0');
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

  switch (true) {
    // Escape — Close line bank
    case e.key === 'Escape': {
      if (!lineBankOpen) return;
      e.preventDefault();
      lineBankOpen = false;
      render();
      break;
    }

    // Tab — Toggle line bank
    case e.key === 'Tab': {
      const pickerVisible = state.stage === 'OBJECTION' && !state.lastObjectionBucket;
      if (state.stage === 'IDLE' || pickerVisible) return;
      e.preventDefault();
      const stageLines = linesForStage(state.stage, PLAYBOOK);
      if (!stageLines.length) return;
      lineBankOpen = !lineBankOpen;
      render();
      break;
    }

    // F4 — Non-connect
    case e.key === 'F4': {
      e.preventDefault();
      lineBankOpen = false;
      dispatch({
        type: 'MANUAL_NON_CONNECT',
        callSid: state.callId,
        atMs: now,
      });
      break;
    }

    // F6 — Stage back (for corrections)
    case e.key === 'F6': {
      e.preventDefault();
      lineBankOpen = false;
      // For stages in NAV_STAGES, go to previous index.
      // For terminal/branch stages, go to their logical parent:
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

    // F7 — Primary path forward (follows decision tree)
    case e.key === 'F7': {
      e.preventDefault();
      lineBankOpen = false;
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

    // F8 — Alternate path (branch in decision tree)
    case e.key === 'F8': {
      e.preventDefault();
      lineBankOpen = false;
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

    // 1-3 — Context-sensitive: bridge angles (BRIDGE/OPENER) or objections (CLOSE/OBJECTION)
    case e.key === '1' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      e.preventDefault();
      lineBankOpen = false;
      if (state.stage === 'BRIDGE' || state.stage === 'OPENER') {
        dispatch({ type: 'MANUAL_SET_BRIDGE_ANGLE', callSid: state.callId, angle: 'missed_calls', atMs: now });
      } else {
        dispatch({ type: 'MANUAL_SET_OBJECTION', callSid: state.callId, bucket: 'timing', atMs: now });
      }
      break;
    }

    case e.key === '2' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      e.preventDefault();
      lineBankOpen = false;
      if (state.stage === 'BRIDGE' || state.stage === 'OPENER') {
        dispatch({ type: 'MANUAL_SET_BRIDGE_ANGLE', callSid: state.callId, angle: 'competition', atMs: now });
      } else {
        dispatch({ type: 'MANUAL_SET_OBJECTION', callSid: state.callId, bucket: 'interest', atMs: now });
      }
      break;
    }

    case e.key === '3' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      e.preventDefault();
      lineBankOpen = false;
      if (state.stage === 'BRIDGE' || state.stage === 'OPENER') {
        dispatch({ type: 'MANUAL_SET_BRIDGE_ANGLE', callSid: state.callId, angle: 'overwhelmed', atMs: now });
      } else {
        dispatch({ type: 'MANUAL_SET_OBJECTION', callSid: state.callId, bucket: 'info', atMs: now });
      }
      break;
    }

    // 4 — Objection: authority (only in CLOSE/OBJECTION)
    case e.key === '4' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      e.preventDefault();
      lineBankOpen = false;
      dispatch({ type: 'MANUAL_SET_OBJECTION', callSid: state.callId, bucket: 'authority', atMs: now });
      break;
    }

    // Shift+F11 — Reset
    case e.key === 'F11' && e.shiftKey: {
      e.preventDefault();
      lineBankOpen = false;
      dispatch({
        type: 'END_CALL',
        callSid: state.callId,
        atMs: now,
      });
      saveSession(state, prospectId);

      // Reset after brief delay
      setTimeout(() => {
        resetAuditTrail();
        $transcriptFeed.textContent = '';
        prospectName = '';
        prospectBusiness = '';
        prospectId = null;
        manualModeActive = false;
        state = createInitialState(PLAYBOOK);
        stopCallTimer();
        callStartTime = null;
        $callTimer.textContent = '00:00';
        render();
      }, 100);
      break;
    }

    // H — Hedge (CLOSE or OBJECTION stage)
    case (e.key === 'h' || e.key === 'H') && !e.ctrlKey && !e.altKey && !e.metaKey: {
      if (state.stage !== 'CLOSE' && state.stage !== 'OBJECTION') return;
      e.preventDefault();
      lineBankOpen = false;
      dispatch({
        type: 'HEDGE_REQUESTED',
        callSid: state.callId,
        atMs: now,
      });
      break;
    }
  }
});

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

  // NOW panel
  $nowPanel.setAttribute('data-stage', state.stage);
  renderObjectionPicker();
  $nowLine.textContent = state.now?.line || 'Waiting for call...';
  $nowWhy.textContent = state.now?.why || '';
  renderLineBank();

  // Confidence badge
  renderConfidenceBadge();

  // Dynamic hotkey labels: 1-3 change meaning at BRIDGE/OPENER vs CLOSE/OBJECTION
  const isBridge = state.stage === 'BRIDGE' || state.stage === 'OPENER';
  const $hk1 = document.getElementById('hk1');
  const $hk2 = document.getElementById('hk2');
  const $hk3 = document.getElementById('hk3');
  const $hk4 = document.getElementById('hk4');
  if ($hk1) $hk1.innerHTML = `<kbd>1</kbd> ${isBridge ? 'Missed' : 'Timing'}`;
  if ($hk2) $hk2.innerHTML = `<kbd>2</kbd> ${isBridge ? 'Comp' : 'Interest'}`;
  if ($hk3) $hk3.innerHTML = `<kbd>3</kbd> ${isBridge ? 'Overwhelm' : 'Info'}`;
  if ($hk4) $hk4.style.opacity = isBridge ? '0.3' : '1';
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
let $lineBank = null;

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

function renderLineBank() {
  const pickerVisible = state.stage === 'OBJECTION' && !state.lastObjectionBucket;
  const stageLines = linesForStage(state.stage, PLAYBOOK);
  const showLineBank = lineBankOpen && state.stage !== 'IDLE' && !pickerVisible && stageLines.length > 0;

  if (!showLineBank) {
    if ($lineBank) {
      $lineBank.remove();
      $lineBank = null;
    }
    return;
  }

  if ($lineBank) {
    $lineBank.remove();
    $lineBank = null;
  }

  $lineBank = document.createElement('div');
  $lineBank.className = 'line-bank';

  $lineBank.appendChild(buildLineBankSection('CURRENT STAGE', stageLines, 'stage'));
  if (PLAYBOOK.powerLines?.length) {
    $lineBank.appendChild(buildLineBankSection('POWER LINES', PLAYBOOK.powerLines, 'power'));
  }

  $nowPanel.appendChild($lineBank);
}

function buildLineBankSection(title, entries, kind) {
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
      lineBankOpen = false;
      dispatch({
        type: 'LINE_BANK_SELECT',
        callSid: state.callId,
        line: fillLineTemplate(entry.line, currentLineContext()),
        atMs: Date.now(),
      });
    });
    section.appendChild(row);
  }

  return section;
}

function currentLineContext() {
  return {
    name: prospectName,
    business: prospectBusiness,
    day: state.scheduledDay,
  };
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
    case 'BOOKED': return 'CLOSE';
    case 'EXIT': return 'CLOSE';
    case 'NON_CONNECT': return 'IDLE';
    case 'ENDED': return 'IDLE';
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
