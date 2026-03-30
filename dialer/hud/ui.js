// dialer/hud/ui.js — DOM rendering, hotkeys, BroadcastChannel listener
// Vanilla JS ES module — no build step, no TypeScript.

import { PLAYBOOK } from './playbook.js';
import { createInitialState, hudReducer, bandFromScore } from './reducer.js';
import { classifyUtterance, shouldCallLlmFallback, isUsableDeterministicResult } from './classifier.js';
import { captureSession, resetAuditTrail, logDecision, saveSession } from './session.js';
import { classifyWithLlm } from './llm.js';

// ── State ──────────────────────────────────────────────────────

let state = createInitialState(PLAYBOOK);
let manualModeActive = false;
let prospectName = '';
let prospectBusiness = '';
let prospectId = null;
let callTimerInterval = null;
let callStartTime = null;

// Stage ordering for navigation (navigable subset)
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
  logDecision(action, prevState, state);
  render();
}

// ── BroadcastChannel ───────────────────────────────────────────

const channel = new BroadcastChannel('calllock-hud');

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
        state = { ...state, outcome: msg.outcome };
        // Re-save session with updated outcome
        saveSession(state, prospectId);
        render();
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
      atMs: msg.atMs || Date.now(),
    });
  } else {
    // Low confidence: add transcript but don't change state
    dispatch({
      type: 'TRANSCRIPT_FINAL',
      callSid: state.callId,
      turn,
      rule: result,
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
    // F4 — Non-connect
    case e.key === 'F4': {
      e.preventDefault();
      dispatch({
        type: 'MANUAL_NON_CONNECT',
        callSid: state.callId,
        atMs: now,
      });
      break;
    }

    // F6 — Stage back
    case e.key === 'F6': {
      e.preventDefault();
      const currentIdx = NAV_STAGES.indexOf(state.stage);
      const prevIdx = currentIdx > 0 ? currentIdx - 1 : 0;
      dispatch({
        type: 'MANUAL_SET_STAGE',
        callSid: state.callId,
        stage: NAV_STAGES[prevIdx],
        atMs: now,
      });
      break;
    }

    // F7 — Stage forward
    case e.key === 'F7': {
      e.preventDefault();
      const currentIdx2 = NAV_STAGES.indexOf(state.stage);
      const nextIdx = currentIdx2 < NAV_STAGES.length - 1 ? currentIdx2 + 1 : NAV_STAGES.length - 1;
      dispatch({
        type: 'MANUAL_SET_STAGE',
        callSid: state.callId,
        stage: NAV_STAGES[nextIdx],
        atMs: now,
      });
      break;
    }

    // 1 — Objection: timing
    case e.key === '1' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      e.preventDefault();
      dispatch({
        type: 'MANUAL_SET_OBJECTION',
        callSid: state.callId,
        bucket: 'timing',
        atMs: now,
      });
      break;
    }

    // 2 — Objection: interest
    case e.key === '2' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      e.preventDefault();
      dispatch({
        type: 'MANUAL_SET_OBJECTION',
        callSid: state.callId,
        bucket: 'interest',
        atMs: now,
      });
      break;
    }

    // 3 — Objection: info
    case e.key === '3' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      e.preventDefault();
      dispatch({
        type: 'MANUAL_SET_OBJECTION',
        callSid: state.callId,
        bucket: 'info',
        atMs: now,
      });
      break;
    }

    // 4 — Objection: authority
    case e.key === '4' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      e.preventDefault();
      dispatch({
        type: 'MANUAL_SET_OBJECTION',
        callSid: state.callId,
        bucket: 'authority',
        atMs: now,
      });
      break;
    }

    // Shift+F11 — Reset
    case e.key === 'F11' && e.shiftKey: {
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

    // H — Hedge (only in CLOSE stage)
    case e.key === 'h' && !e.ctrlKey && !e.altKey && !e.metaKey: {
      if (state.stage !== 'CLOSE') return;
      e.preventDefault();
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

  // NOW panel
  $nowPanel.setAttribute('data-stage', state.stage);
  $nowLine.textContent = state.now?.line || 'Waiting for call...';
  $nowWhy.textContent = state.now?.why || '';

  // Confidence badge
  renderConfidenceBadge();
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

render();

console.log('[hud/ui] Sales HUD initialized. Listening on BroadcastChannel "calllock-hud".');
