// dialer/hud/study.js
// Standalone pre-call study surface. Reuses playbook.js / taxonomy.js / cards.js
// so it stays in sync with the real HUD, but runs with a fake local state:
// no BroadcastChannel, no reducer, no session log, no Twilio/Deepgram wiring.
//
// Keyboard drills:
//   → / ←   walk stages (same STAGE_TRANSITIONS / NAV_STAGES as ui.js)
//   1-4     trigger objection bucket or bridge angle per HOTKEY_CONFIG[stage]
//   F10     alternate stage branch (same as real HUD f8)
//   `       toggle FAQ drawer
//   n       load next lead from /current-queue
//   Esc     reset stage to IDLE and clear any objection/bridge selection

import { PLAYBOOK, linesForStage, lineForStage, fillLineTemplate } from './playbook.js';
import { NATIVE_STAGE_CARDS } from './cards.js';
import { HOTKEY_CONFIG, GLOBAL_HOTKEYS, OBJECTION_HOTKEYS, BRIDGE_HOTKEYS } from './taxonomy.js';

// ── Navigation tables (mirror ui.js — intentionally small and duplicated to
// keep study mode truly self-contained so a ui.js bug can't leak here) ────

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
  EXIT:              { f7: null,        f8: null },
};

const NAV_STAGES = ['GATEKEEPER', 'OPENER', 'PERMISSION_MOMENT', 'MINI_PITCH', 'WRONG_PERSON', 'BRIDGE', 'QUALIFIER', 'PRICING', 'CLOSE', 'OBJECTION'];

const BACK_MAP = {
  BOOKED:      'CLOSE',
  SEED_EXIT:   'QUALIFIER',
  EXIT:        'CLOSE',
  NON_CONNECT: 'OPENER',
};

const METRO_CITY = {
  TX: 'Houston',
  FL: 'Orlando',
  MI: 'West Bloomfield',
  IL: 'Chicago',
  AZ: 'Phoenix',
};

// Default trade — used only when the loaded lead has no trade field.
const DEFAULT_CONTEXT = {
  name: 'there',
  business: 'there',
  location: 'Detroit',
  trade: 'home service',
  day: 'Thursday',
};

// ── Local state ───────────────────────────────────────────────────

// OPENER splits into two beats: the cold-call greeting, then a focused probe.
// openerPhase tracks which beat is visible while state.stage === 'OPENER'.
const OPENER_PROBE_LINE = "When you can't get to a new customer call right away, what usually happens?";

// Stages that have a primary/backup variant but no NATIVE_STAGE_CARDS entry.
// ← at these stages toggles between the two lines (without leaving the stage).
// Stages NOT in this map fall back to NATIVE_STAGE_CARDS[stage].backupLine.
const STAGE_VARIANT_LINES = {
  PERMISSION_MOMENT: {
    primary: 'Can I ask you a quick question about new customer calls?',
    backup: "This'll take 20 seconds — when a new call comes in and you can't grab it, what happens?",
  },
};

const state = {
  stage: 'IDLE',
  objection: null,    // e.g. 'timing' — set by 1-4 at objection stages
  bridgeAngle: null,  // e.g. 'missed_calls' — set by 1-4 at bridge stages
  openerPhase: 'greeting', // 'greeting' | 'probe' — only meaningful at OPENER
  lineVariant: 'primary', // 'primary' | 'backup' — ← toggles at stages with a backup
};

let leads = [];
let leadIndex = 0;

// ── DOM refs ──────────────────────────────────────────────────────

const $prospectInfo = document.getElementById('prospectInfo');
const $stageBar = document.getElementById('stageBar');
const $linesFeed = document.getElementById('linesFeed');
const $objectionsFeed = document.getElementById('objectionsFeed');
const $nowGoal = document.getElementById('nowGoal');
const $nowLine = document.getElementById('nowLine');
const $nowWhy = document.getElementById('nowWhy');
const $nowListenLabel = document.getElementById('nowListenLabel');
const $nowListen = document.getElementById('nowListen');
const $nowSelection = document.getElementById('nowSelection');
const $hotkeyBar = document.getElementById('hotkey-bar');
const $objHotkeyBar = document.getElementById('objection-hotkey-bar');
const $bridgeHotkeyBar = document.getElementById('bridge-hotkey-bar');
const $faqBox = document.getElementById('faq-box');
const $faqBackdrop = document.getElementById('faq-backdrop');
const $btnNextLead = document.getElementById('btn-next-lead');
const $btnReset = document.getElementById('btn-reset');

// ── Hotkey legends (rendered once) ────────────────────────────────

function renderHotkeyLegend(container, keys) {
  container.replaceChildren();
  for (const h of keys) {
    const span = document.createElement('span');
    span.className = 'hotkey-item';
    const kbd = document.createElement('kbd');
    kbd.textContent = h.key;
    span.appendChild(kbd);
    span.appendChild(document.createTextNode(' ' + h.label));
    container.appendChild(span);
  }
}

renderHotkeyLegend($hotkeyBar, GLOBAL_HOTKEYS);
renderHotkeyLegend($objHotkeyBar, OBJECTION_HOTKEYS);
renderHotkeyLegend($bridgeHotkeyBar, BRIDGE_HOTKEYS);

// ── Lead loading ──────────────────────────────────────────────────

async function loadLeads() {
  try {
    const response = await fetch('/current-queue?block=AM&exclude_dialed=true');
    if (response.ok) {
      const payload = await response.json();
      const prospects = payload?.queue?.prospects || [];
      if (prospects.length > 0) {
        leads = prospects;
        leadIndex = 0;
        return;
      }
    }
  } catch (err) {
    console.warn('[study] /current-queue failed, falling back to /daily-plan', err);
  }

  try {
    const response = await fetch('/daily-plan');
    if (response.ok) {
      const plan = await response.json();
      const fresh = plan?.fresh_leads || [];
      if (fresh.length > 0) {
        leads = fresh;
        leadIndex = 0;
        return;
      }
    }
  } catch (err) {
    console.warn('[study] /daily-plan fallback failed', err);
  }

  // No leads available — renderer will fall back to DEFAULT_CONTEXT placeholders.
  leads = [];
  leadIndex = 0;
}

function currentLead() {
  return leads.length > 0 ? leads[leadIndex % leads.length] : null;
}

function leadContext() {
  const lead = currentLead();
  if (!lead) return { ...DEFAULT_CONTEXT };
  return {
    name: lead.business_name || DEFAULT_CONTEXT.name,
    business: lead.business_name || DEFAULT_CONTEXT.business,
    location: METRO_CITY[lead.metro] || DEFAULT_CONTEXT.location,
    trade: lead.trade || DEFAULT_CONTEXT.trade,
    day: DEFAULT_CONTEXT.day,
    number: lead.phone || lead.phone_normalized || 'the number you have for me',
  };
}

// ── Variant helpers (primary/backup toggle via ← at non-OPENER stages) ──

function getBackupLineFor(stage, card) {
  // Explicit map wins (covers stages with no NATIVE_STAGE_CARDS entry, like PERMISSION_MOMENT)
  const fromMap = STAGE_VARIANT_LINES[stage]?.backup;
  if (fromMap) return fromMap;
  // Fall back to the card's backupLine field
  return card && card.backupLine ? card.backupLine : null;
}

function stageHasBackupVariant(stage, card) {
  return Boolean(getBackupLineFor(stage, card));
}

// ── Render ────────────────────────────────────────────────────────

function render() {
  renderProspectInfo();
  renderStageBar();
  renderNowPanel();
  renderLinesPanel();
  renderObjectionsPanel();
}

function renderProspectInfo() {
  const lead = currentLead();
  if (!lead) {
    $prospectInfo.textContent = 'No lead loaded — press n to retry';
    return;
  }
  const metroCity = METRO_CITY[lead.metro] || lead.metro || '';
  const parts = [lead.business_name];
  if (metroCity) parts.push(metroCity);
  parts.push(`(${leadIndex + 1}/${leads.length})`);
  $prospectInfo.textContent = parts.filter(Boolean).join(' · ');
}

function renderStageBar() {
  const pills = $stageBar.querySelectorAll('.stage-pill');
  pills.forEach((pill) => {
    pill.classList.remove('current', 'past', 'future');
    const pillStage = pill.getAttribute('data-stage');
    if (pillStage === state.stage) {
      pill.classList.add('current');
    } else {
      pill.classList.add('future');
    }
  });
}

function renderNowPanel() {
  const card = NATIVE_STAGE_CARDS[state.stage];
  const ctx = leadContext();

  // Goal — append "· BACKUP" when ← has toggled us onto the backup variant
  const onBackup = state.lineVariant === 'backup' && stageHasBackupVariant(state.stage, card);
  if (card && card.goal) {
    $nowGoal.textContent = onBackup ? `${card.goal} · BACKUP` : card.goal;
    $nowGoal.style.display = '';
  } else if (onBackup) {
    $nowGoal.textContent = 'BACKUP';
    $nowGoal.style.display = '';
  } else {
    $nowGoal.textContent = '';
    $nowGoal.style.display = 'none';
  }

  // Primary line — prefer NATIVE_STAGE_CARDS, fall back to lineForStage().
  // OPENER has a probe sub-state that replaces the greeting with a focused probe.
  // Other stages with a backup variant swap when state.lineVariant === 'backup'.
  let primaryLine = '';
  if (state.stage === 'IDLE') {
    primaryLine = 'Press → to walk the script. ← toggles primary/backup. 1-4 drills. ` opens FAQ.';
  } else if (state.stage === 'OPENER' && state.openerPhase === 'probe') {
    primaryLine = OPENER_PROBE_LINE;
  } else if (onBackup) {
    primaryLine = getBackupLineFor(state.stage, card) || (card && card.primaryLine) || '';
  } else if (STAGE_VARIANT_LINES[state.stage]?.primary) {
    primaryLine = STAGE_VARIANT_LINES[state.stage].primary;
  } else if (card && card.primaryLine) {
    primaryLine = card.primaryLine;
  } else {
    primaryLine = lineForStage(state.stage, PLAYBOOK) || '';
  }
  $nowLine.textContent = fillLineTemplate(primaryLine, ctx);

  // Why
  $nowWhy.textContent = card?.why || '';

  // Listen-for
  if (card && Array.isArray(card.listenFor) && card.listenFor.length > 0) {
    $nowListenLabel.style.display = '';
    $nowListen.textContent = card.listenFor.join(' · ');
  } else {
    $nowListenLabel.style.display = 'none';
    $nowListen.textContent = '';
  }

  // Selection chips (objection or bridge bucket picked this round)
  $nowSelection.replaceChildren();
  if (state.objection) {
    const chip = document.createElement('span');
    chip.className = 'now-selection-chip';
    chip.textContent = `Objection: ${state.objection}`;
    $nowSelection.appendChild(chip);
  }
  if (state.bridgeAngle) {
    const chip = document.createElement('span');
    chip.className = 'now-selection-chip bridge';
    chip.textContent = `Bridge: ${state.bridgeAngle}`;
    $nowSelection.appendChild(chip);
  }
}

function renderLinesPanel() {
  $linesFeed.replaceChildren();
  const ctx = leadContext();

  const stageLines = linesForStage(state.stage, PLAYBOOK);
  if (stageLines.length > 0) {
    $linesFeed.appendChild(buildSection('CURRENT STAGE', stageLines, 'stage', ctx));
  }

  // Bridge angles — shown at BRIDGE/OPENER stages where 1-4 trigger bridge drills
  if (state.stage === 'BRIDGE' || state.stage === 'OPENER') {
    const bridgeRows = [
      { label: '1 · Missed calls', line: PLAYBOOK.bridge.missed_calls.voicemail, key: 'missed_calls' },
      { label: '2 · Competition',  line: PLAYBOOK.bridge.competition.firstResponder, key: 'competition' },
      { label: '3 · Overwhelmed',  line: PLAYBOOK.bridge.overwhelmed.cantKeepUp, key: 'overwhelmed' },
      { label: '4 · Ad spend',     line: PLAYBOOK.bridge.ad_spend.lsa, key: 'ad_spend' },
    ];
    $linesFeed.appendChild(buildSection('BRIDGE DRILLS (1-4)', bridgeRows, 'bridge', ctx, state.bridgeAngle));
  }

  if (PLAYBOOK.powerLines?.length) {
    $linesFeed.appendChild(buildSection('POWER LINES', PLAYBOOK.powerLines, 'stage', ctx));
  }
  if (PLAYBOOK.recoveryLines?.length) {
    $linesFeed.appendChild(buildSection('RECOVERY', PLAYBOOK.recoveryLines, 'stage', ctx));
  }
}

function renderObjectionsPanel() {
  $objectionsFeed.replaceChildren();
  const ctx = leadContext();

  const entries = Object.entries(PLAYBOOK.objections).map(([bucket, data]) => ({
    label: `${bucket.toUpperCase()}`,
    line: data.reset,
    key: bucket,
  }));
  $objectionsFeed.appendChild(buildSection('OBJECTION RESETS', entries, 'objection', ctx, state.objection));
}

function buildSection(title, entries, kind, ctx, activeKey = null) {
  const section = document.createElement('div');
  section.className = 'line-bank-section';

  const heading = document.createElement('div');
  heading.className = 'line-bank-section-title';
  heading.textContent = title;
  section.appendChild(heading);

  for (const entry of entries) {
    const row = document.createElement('div');
    row.className = 'line-bank-row ' + kind;
    if (activeKey && entry.key === activeKey) row.classList.add('active');

    const label = document.createElement('span');
    label.className = 'line-bank-label';
    label.textContent = entry.label || entry.tag || '';

    const text = document.createElement('span');
    text.className = 'line-bank-text';
    text.textContent = fillLineTemplate(entry.line, ctx);

    row.appendChild(label);
    row.appendChild(text);
    section.appendChild(row);
  }

  return section;
}

// ── FAQ drawer ────────────────────────────────────────────────────

function renderFaq() {
  $faqBox.replaceChildren();
  const ctx = leadContext();
  for (const item of PLAYBOOK.faq) {
    const row = document.createElement('div');
    row.className = 'faq-item';

    const q = document.createElement('div');
    q.className = 'faq-question';
    q.textContent = item.question;

    const a = document.createElement('div');
    a.className = 'faq-answer';
    a.textContent = fillLineTemplate(item.answer, ctx);

    row.appendChild(q);
    row.appendChild(a);
    $faqBox.appendChild(row);
  }
}

function toggleFaq(forceState = null) {
  const shouldOpen = forceState !== null ? forceState : !$faqBox.classList.contains('open');
  if (shouldOpen) {
    renderFaq();
    $faqBox.classList.add('open');
    $faqBackdrop.classList.add('active');
  } else {
    $faqBox.classList.remove('open');
    $faqBackdrop.classList.remove('active');
  }
}

$faqBackdrop.addEventListener('click', () => toggleFaq(false));

// ── Keyboard drill handler ────────────────────────────────────────

function advanceStage() {
  // Sub-state: on OPENER, → first advances from greeting to probe before moving on.
  if (state.stage === 'OPENER' && state.openerPhase === 'greeting') {
    state.openerPhase = 'probe';
    return;
  }
  const next = STAGE_TRANSITIONS[state.stage]?.f7;
  if (!next) return;
  state.stage = next;
  state.objection = null;
  state.bridgeAngle = null;
  state.openerPhase = 'greeting';
  state.lineVariant = 'primary';
}

function backStage() {
  // Sub-state: on OPENER probe, ← first steps back to the greeting before leaving the stage.
  if (state.stage === 'OPENER' && state.openerPhase === 'probe') {
    state.openerPhase = 'greeting';
    return;
  }
  if (BACK_MAP[state.stage]) {
    state.stage = BACK_MAP[state.stage];
  } else {
    const idx = NAV_STAGES.indexOf(state.stage);
    if (idx > 0) {
      state.stage = NAV_STAGES[idx - 1];
    } else if (idx === 0) {
      state.stage = 'IDLE';
    } else {
      // Stage not in NAV_STAGES (e.g. IDLE, EXIT, BOOKED) — clamp to IDLE
      return;
    }
  }
  state.objection = null;
  state.bridgeAngle = null;
  // Stepping back into OPENER from a later stage lands on the probe beat,
  // so the sequence going backward is probe → greeting → previous stage.
  state.openerPhase = state.stage === 'OPENER' ? 'probe' : 'greeting';
  state.lineVariant = 'primary';
}

function branchStage() {
  const alt = STAGE_TRANSITIONS[state.stage]?.f8;
  if (!alt) return;
  state.stage = alt;
  state.objection = null;
  state.bridgeAngle = null;
  state.openerPhase = 'greeting';
  state.lineVariant = 'primary';
}

// Toggle primary ↔ backup variant at the current stage without leaving it.
// No-op at stages that don't have a backup line — caller falls back to backStage().
function toggleLineVariant() {
  const card = NATIVE_STAGE_CARDS[state.stage];
  if (!stageHasBackupVariant(state.stage, card)) return false;
  state.lineVariant = state.lineVariant === 'backup' ? 'primary' : 'backup';
  return true;
}

function applyNumericHotkey(keyChar) {
  const config = HOTKEY_CONFIG[state.stage];
  if (!config || config.length === 0) return;
  const hit = config.find((h) => h.key === keyChar);
  if (!hit) return;
  if (hit.type === 'objection') {
    state.objection = hit.value;
    state.bridgeAngle = null;
  } else if (hit.type === 'bridge') {
    state.bridgeAngle = hit.value;
    state.objection = null;
  }
}

function resetDrill() {
  state.stage = 'IDLE';
  state.objection = null;
  state.bridgeAngle = null;
  state.openerPhase = 'greeting';
  state.lineVariant = 'primary';
}

async function loadNextLead() {
  if (leads.length === 0) {
    await loadLeads();
  } else {
    leadIndex = (leadIndex + 1) % leads.length;
  }
  render();
}

document.addEventListener('keydown', (e) => {
  // Ignore if a text input is focused (defensive; study page has none today)
  const tag = e.target?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') return;

  // FAQ drawer: Escape closes it first, before Escape acts as drill reset
  if ($faqBox.classList.contains('open') && e.key === 'Escape') {
    e.preventDefault();
    toggleFaq(false);
    return;
  }

  switch (e.key) {
    case 'ArrowRight':
      e.preventDefault();
      advanceStage();
      render();
      break;
    case 'ArrowLeft':
      e.preventDefault();
      // Shift+← always goes back a stage (escape hatch for the variant toggle).
      // At OPENER the existing probe → greeting sub-state handles everything.
      // Elsewhere, ← first tries to toggle primary/backup at the current stage;
      // if the stage has no backup variant, it falls through to stage-back.
      if (e.shiftKey || state.stage === 'OPENER') {
        backStage();
      } else if (!toggleLineVariant()) {
        backStage();
      }
      render();
      break;
    case 'F10':
      e.preventDefault();
      branchStage();
      render();
      break;
    case '1':
    case '2':
    case '3':
    case '4':
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      e.preventDefault();
      applyNumericHotkey(e.key);
      render();
      break;
    case '`':
      e.preventDefault();
      toggleFaq();
      break;
    case 'n':
    case 'N':
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      e.preventDefault();
      loadNextLead();
      break;
    case 'Escape':
      e.preventDefault();
      resetDrill();
      render();
      break;
  }
});

// ── Buttons ───────────────────────────────────────────────────────

$btnNextLead.addEventListener('click', () => loadNextLead());
$btnReset.addEventListener('click', () => {
  resetDrill();
  render();
});

// ── Init ──────────────────────────────────────────────────────────

(async () => {
  await loadLeads();
  render();
})();
