// dialer/hud/render-v2.js
// v2 render functions for the center panel, left rail, and right rail.
// Separated from ui.js per eng review Amendment 2.

import { linesForStage } from './playbook.js';

// ── Stage Pane Config ─────────────────────────────────────────────
// Data-driven map: stage → { left: [...components], right: [...components], leftHeader, rightHeader }
// Each component key maps to a renderer in renderLeftPane/renderRightPane.

export const STAGE_PANE_CONFIG = {
  IDLE:              { left: ['compactId'],                             right: [],                           leftHeader: null,         rightHeader: null },
  OPENER:            { left: ['compactId', 'prospectFull', 'briefing'], right: ['tactical', 'powerLines'],   leftHeader: 'PROSPECT',   rightHeader: 'SUPPORT' },
  GATEKEEPER:        { left: ['compactId', 'briefing', 'lines'],       right: ['tactical'],                 leftHeader: 'PLAYBOOK',   rightHeader: 'SUPPORT' },
  PERMISSION_MOMENT: { left: ['compactId', 'briefing', 'lines'],       right: ['tactical'],                 leftHeader: 'PLAYBOOK',   rightHeader: 'SUPPORT' },
  MINI_PITCH:        { left: ['compactId', 'briefing', 'lines'],       right: ['tactical'],                 leftHeader: 'PLAYBOOK',   rightHeader: 'SUPPORT' },
  WRONG_PERSON:      { left: ['compactId', 'briefing', 'lines'],       right: ['tactical'],                 leftHeader: 'PLAYBOOK',   rightHeader: 'SUPPORT' },
  BRIDGE:            { left: ['compactId', 'briefing', 'lines'],       right: ['tactical', 'bridgeAngles'], leftHeader: 'PLAYBOOK',   rightHeader: 'ANGLES' },
  QUALIFIER:         { left: ['compactId', 'briefing', 'lines'],       right: ['tactical', 'pitchLines'],   leftHeader: 'PLAYBOOK',   rightHeader: 'SUPPORT' },
  PRICING:           { left: ['compactId', 'briefing', 'lines'],       right: ['tactical'],                 leftHeader: 'PLAYBOOK',   rightHeader: 'SUPPORT' },
  CLOSE:             { left: ['compactId', 'briefing', 'lines'],       right: ['tactical', 'objectionPicks'], leftHeader: 'PLAYBOOK', rightHeader: 'TACTICS' },
  OBJECTION:         { left: ['compactId', 'briefing', 'lines'],       right: ['tactical', 'recoveryLines'], leftHeader: 'PLAYBOOK',  rightHeader: 'OBJECTIONS' },
  SEED_EXIT:         { left: ['compactId', 'briefing', 'lines'],       right: [],                           leftHeader: 'PLAYBOOK',   rightHeader: null },
  BOOKED:            { left: ['compactId', 'briefing', 'lines'],       right: [],                           leftHeader: null,         rightHeader: null },
  NON_CONNECT:       { left: ['compactId', 'briefing', 'lines'],       right: [],                           leftHeader: 'PLAYBOOK',   rightHeader: null },
  EXIT:              { left: ['compactId', 'briefing', 'lines'],       right: [],                           leftHeader: null,         rightHeader: null },
  ENDED:             { left: ['compactId'],                             right: [],                           leftHeader: null,         rightHeader: null },
};

// ── Compact Identity ──────────────────────────────────────────────

export function renderCompactIdentity(ctx) {
  const el = document.getElementById('v2-prospect-identity');
  if (!el) return;
  el.textContent = '';
  if (!ctx) {
    const fallback = document.createElement('div');
    fallback.className = 'v2-compact-id-fallback';
    fallback.textContent = 'Incoming call...';
    el.appendChild(fallback);
    return;
  }
  const parts = [ctx.name, ctx.company].filter(Boolean);
  if (parts.length === 0) return;
  const line = document.createElement('div');
  line.className = 'v2-compact-id';
  line.textContent = parts.join(' \u00B7 ');
  el.appendChild(line);
}

// ── Stage Briefing ────────────────────────────────────────────────

export function renderStageBriefing(card) {
  const el = document.getElementById('v2-stage-briefing');
  if (!el) return;
  el.textContent = '';
  if (!card || card.stage === 'IDLE' || card.stage === 'ENDED') {
    el.style.display = 'none';
    return;
  }
  el.style.display = '';

  if (card.goal) {
    const goalLabel = document.createElement('div');
    goalLabel.className = 'v2-ctx-label';
    goalLabel.textContent = 'GOAL';
    el.appendChild(goalLabel);
    const goalVal = document.createElement('div');
    goalVal.className = 'v2-briefing-goal';
    goalVal.textContent = card.goal;
    el.appendChild(goalVal);
  }

  if (card.listenFor && card.listenFor.length > 0) {
    const listenLabel = document.createElement('div');
    listenLabel.className = 'v2-ctx-label';
    listenLabel.style.marginTop = '6px';
    listenLabel.textContent = 'LISTEN FOR';
    el.appendChild(listenLabel);
    card.listenFor.forEach(item => {
      const span = document.createElement('div');
      span.className = 'v2-briefing-listen';
      span.textContent = '\u2022 ' + item;
      el.appendChild(span);
    });
  }
}

// ── Left Pane Orchestrator ────────────────────────────────────────

/**
 * Orchestrate left pane rendering based on STAGE_PANE_CONFIG.
 * @param {string} stage
 * @param {object} activeCard - from composeActiveCard() (Amendment 9: use activeCard for briefing)
 * @param {object|null} prospectCtx - from state.prospectContext
 * @param {object} deps - { playbook, buildSection, lineContext }
 */
export function renderLeftPane(stage, activeCard, prospectCtx, deps) {
  const config = STAGE_PANE_CONFIG[stage] || STAGE_PANE_CONFIG['IDLE'];
  const components = config.left;

  // Clear dynamic sections
  const briefing = document.getElementById('v2-stage-briefing');
  const linesFeed = document.getElementById('linesFeed');
  if (briefing) { briefing.textContent = ''; briefing.style.display = 'none'; }
  if (linesFeed) linesFeed.replaceChildren();

  // Toggle prospect context visibility (Amendment 8: visibility toggle, not rebuild)
  const prospectWhy = document.getElementById('v2-prospect-why');
  const prospectOutreach = document.getElementById('v2-prospect-outreach');
  const prospectFit = document.getElementById('v2-prospect-fit');
  const showFull = components.includes('prospectFull');
  [prospectWhy, prospectOutreach, prospectFit].forEach(el => {
    if (el) el.style.display = showFull ? '' : 'none';
  });

  // Dynamic header
  const headerEl = document.querySelector('.lines-panel .side-panel-header');
  if (headerEl) {
    if (config.leftHeader) {
      headerEl.textContent = config.leftHeader;
      headerEl.style.display = '';
    } else {
      headerEl.style.display = 'none';
    }
  }

  for (const comp of components) {
    switch (comp) {
      case 'compactId':
        renderCompactIdentity(prospectCtx);
        break;
      case 'prospectFull':
        // Handled above via visibility toggle
        break;
      case 'briefing':
        renderStageBriefing(activeCard);
        break;
      case 'lines':
        if (linesFeed && deps.buildSection) {
          const stageLines = linesForStage(stage, deps.playbook);
          if (stageLines.length) {
            linesFeed.appendChild(deps.buildSection('CURRENT STAGE', stageLines, 'stage', 'lines'));
          }
        }
        break;
    }
  }
}

// ── Right Pane Orchestrator ───────────────────────────────────────

/**
 * Orchestrate right pane rendering based on STAGE_PANE_CONFIG.
 * Uses a single renderRightPaneLinesSection for all line types (Amendment 5: DRY).
 * @param {string} stage
 * @param {object} activeCard - from composeActiveCard()
 * @param {object} deps - { playbook, buildSection, lineContext }
 */
export function renderRightPane(stage, activeCard, deps) {
  const config = STAGE_PANE_CONFIG[stage] || STAGE_PANE_CONFIG['IDLE'];
  const components = config.right;

  // Clear right pane
  const objFeed = document.getElementById('objectionsFeed');
  if (objFeed) objFeed.replaceChildren();

  // Clear tactical card sections when right rail is empty
  if (components.length === 0) {
    ['v2-tac-ask', 'v2-tac-rebuttal', 'v2-tac-value', 'v2-tac-proof', 'v2-tac-ifthen'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = '';
    });
  }

  // Dynamic header
  const headerEl = document.querySelector('.objections-panel .side-panel-header');
  if (headerEl) {
    if (config.rightHeader) {
      headerEl.textContent = config.rightHeader;
      headerEl.style.display = '';
    } else {
      headerEl.style.display = 'none';
    }
  }

  for (const comp of components) {
    switch (comp) {
      case 'tactical':
        renderTacticalCard(activeCard);
        break;
      case 'powerLines':
        if (objFeed && deps.buildSection && deps.playbook.powerLines?.length) {
          objFeed.appendChild(deps.buildSection('POWER LINES', deps.playbook.powerLines, 'power', 'lines'));
        }
        break;
      case 'recoveryLines':
        if (objFeed && deps.buildSection && deps.playbook.recoveryLines?.length) {
          objFeed.appendChild(deps.buildSection('RECOVERY', deps.playbook.recoveryLines, 'recovery', 'lines'));
        }
        break;
      case 'pitchLines':
        if (objFeed && deps.buildSection) {
          const pitchItems = [
            { label: 'Elevator pitch', line: deps.playbook.pitchLines.elevator },
            { label: 'How it works', line: deps.playbook.pitchLines.howItWorks },
            { label: 'Why you need it', line: deps.playbook.pitchLines.whyYouNeed },
          ];
          objFeed.appendChild(deps.buildSection('PITCH', pitchItems, 'stage', 'lines'));
        }
        break;
      case 'bridgeAngles':
        if (objFeed && deps.buildSection) {
          const bridgeItems = [
            { label: 'Missed calls', line: deps.playbook.bridge.fallback },
            { label: 'Competition', line: deps.playbook.bridge.competition.firstResponder },
            { label: 'Overwhelmed', line: deps.playbook.bridge.overwhelmed.cantKeepUp },
            { label: 'Ad spend', line: deps.playbook.bridge.ad_spend.lsa },
          ];
          objFeed.appendChild(deps.buildSection('BRIDGE ANGLES', bridgeItems, 'stage', 'lines'));
        }
        break;
      case 'objectionPicks':
        if (objFeed && deps.buildSection) {
          const objItems = Object.entries(deps.playbook.objections).slice(0, 4).map(([bucket, data]) => ({
            label: bucket.toUpperCase(),
            line: data.reset,
          }));
          objFeed.appendChild(deps.buildSection('ANTICIPATE', objItems, 'objection', 'objection'));
        }
        break;
    }
  }
}

/**
 * Escape HTML to prevent XSS. Matches the existing _esc() pattern in ui.js.
 */
function _esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Render the move type pill (e.g., "BRIDGE ▸ probe" or "ask · compress")
 */
export function renderMoveTypePill(moveType, deliveryModifier, secondaryIntent) {
  const el = document.getElementById('v2-move-type');
  if (!el) return;
  let label = deliveryModifier ? `${moveType} · ${deliveryModifier}` : (moveType || '');
  if (secondaryIntent) {
    label += ` · also: ${secondaryIntent}`;
  }
  el.textContent = label;
}

/**
 * Render the one-line NOW summary
 */
export function renderNowSummary(summary) {
  const el = document.getElementById('v2-now-summary');
  if (!el) return;
  el.textContent = summary || '';
}

/**
 * Render the backup/alternate line
 */
export function renderBackupLine(backupLine) {
  const el = document.getElementById('v2-backup-line');
  if (!el) return;
  if (backupLine) {
    el.textContent = backupLine;
    el.style.display = 'block';
  } else {
    el.textContent = '';
    el.style.display = 'none';
  }
}

/**
 * Render "also heard" badge when recent burst contains signals not reflected
 * in the current card. Shows prior signals that arrived within the buffer window.
 * @param {Array<{signal: string, seq: number, atMs: number}>} recentSignals
 * @param {string|null} currentSignal - the signal driving the active card
 */
export function renderAlsoHeard(recentSignals, currentSignal) {
  const el = document.getElementById('v2-also-heard');
  if (!el) return;
  // Filter to signals that differ from the current card's driving signal
  const others = recentSignals.filter(s => s.signal !== currentSignal);
  if (others.length === 0) {
    el.style.display = 'none';
    el.textContent = '';
    return;
  }
  // Deduplicate signal names
  const unique = [...new Set(others.map(s => s.signal))];
  el.style.display = 'block';
  el.textContent = '\u21B3 also heard: ' + unique.join(', ');
}

/**
 * Render the pause strip
 */
export function renderPauseStrip(visible, message) {
  const el = document.getElementById('v2-pause-strip');
  if (!el) return;
  if (visible) {
    el.textContent = message || '\u23F8 PAUSE \u00B7 Let them answer \u00B7 Classify their response type';
    el.style.display = 'block';
    el.classList.remove('dimmed');
  } else {
    el.classList.add('dimmed');
  }
}

/**
 * Render listen-for cues (max 4 items)
 */
export function renderListenFor(items) {
  const el = document.getElementById('v2-listen-for');
  if (!el) return;
  if (!items || items.length === 0) {
    el.style.display = 'none';
    return;
  }
  el.style.display = 'block';
  // Build listen-for display using escaped content
  const label = document.createElement('div');
  label.className = 'v2-listen-label';
  label.textContent = 'LISTEN FOR';
  el.textContent = '';
  el.appendChild(label);
  items.slice(0, 4).forEach(i => {
    const span = document.createElement('span');
    span.style.marginRight = '12px';
    span.textContent = '\u2022 ' + i;
    el.appendChild(span);
  });
}

/**
 * Render branch preview (max 3 routes)
 */
// Human-friendly stage labels for branch preview
const STAGE_LABELS = {
  OPENER: 'opener', BRIDGE: 'bridge', QUALIFIER: 'qualify',
  CLOSE: 'close', OBJECTION: 'objection', EXIT: 'exit',
  BOOKED: 'booked', SEED_EXIT: 'seed exit', MINI_PITCH: 'mini pitch',
  WRONG_PERSON: 'wrong person', PRICING: 'pricing',
  PERMISSION_MOMENT: 'permission', GATEKEEPER: 'gatekeeper',
  NON_CONNECT: 'voicemail',
};

function friendlyTarget(raw) {
  return STAGE_LABELS[raw] || raw.toLowerCase().replace(/_/g, ' ');
}

export function renderBranchPreview(branchPreview) {
  const el = document.getElementById('v2-branch-preview');
  if (!el) return;
  const entries = Object.entries(branchPreview || {}).slice(0, 3);
  if (entries.length === 0) {
    el.style.display = 'none';
    return;
  }
  el.style.display = 'block';
  const label = document.createElement('div');
  label.className = 'v2-next-label';
  label.textContent = 'NEXT';
  el.textContent = '';
  el.appendChild(label);
  entries.forEach(([cond, route]) => {
    const target = route.next || route.action || '';
    const span = document.createElement('span');
    span.style.marginRight = '12px';
    span.textContent = `${cond} \u2192 ${friendlyTarget(target)}`;
    el.appendChild(span);
  });
}

/**
 * Render conditional DO NOT warning strip
 */
export function renderConditionalDoNot(warning) {
  const el = document.getElementById('v2-do-not');
  if (!el) return;
  if (warning) {
    el.textContent = warning;
    el.style.display = 'block';
  } else {
    el.style.display = 'none';
  }
}

// ── Left Rail: Prospect Context ─────────────────────────────────

/**
 * Render prospect context in the left rail.
 * Gracefully degrades — hides sections with missing fields.
 */
export function renderProspectContext(ctx) {
  const identity = document.getElementById('v2-prospect-identity');
  const why = document.getElementById('v2-prospect-why');
  const outreach = document.getElementById('v2-prospect-outreach');
  const fit = document.getElementById('v2-prospect-fit');

  if (!ctx) {
    [identity, why, outreach, fit].forEach(el => { if (el) el.textContent = ''; });
    return;
  }

  if (identity) {
    identity.textContent = '';
    if (ctx.name) {
      const nameEl = document.createElement('div');
      nameEl.className = 'v2-ctx-value';
      nameEl.style.fontSize = '16px';
      nameEl.style.fontWeight = '600';
      nameEl.textContent = ctx.name;
      identity.appendChild(nameEl);
    }
    if (ctx.title || ctx.company) {
      const metaEl = document.createElement('div');
      metaEl.className = 'v2-ctx-value';
      metaEl.textContent = [ctx.title, ctx.company].filter(Boolean).join(' \u00B7 ');
      identity.appendChild(metaEl);
    }
    if (ctx.location) {
      const locEl = document.createElement('div');
      locEl.className = 'v2-ctx-value';
      locEl.style.color = '#71717a';
      locEl.textContent = ctx.location;
      identity.appendChild(locEl);
    }
  }

  if (why) {
    why.textContent = '';
    if (ctx.fit_reason || ctx.trigger_reason) {
      const label = document.createElement('div');
      label.className = 'v2-ctx-label';
      label.textContent = 'Why this account';
      why.appendChild(label);
      if (ctx.fit_reason) {
        const el = document.createElement('div');
        el.className = 'v2-ctx-value';
        el.textContent = ctx.fit_reason;
        why.appendChild(el);
      }
      if (ctx.trigger_reason) {
        const el = document.createElement('div');
        el.className = 'v2-ctx-inferred';
        el.textContent = ctx.trigger_reason;
        why.appendChild(el);
      }
    }
  }

  if (outreach) {
    outreach.textContent = '';
    const meta = [];
    if (ctx.sequence_step != null) meta.push('Step ' + ctx.sequence_step);
    if (ctx.calls_made != null) meta.push(ctx.calls_made + ' calls');
    if (ctx.emails_sent != null) meta.push(ctx.emails_sent + ' emails');
    const signals = [];
    if (ctx.email_opens) signals.push('Opened ' + ctx.email_opens + 'x');
    if (ctx.link_clicks) signals.push('Clicked ' + ctx.link_clicks + 'x');
    if (ctx.last_touch_date) signals.push('Last: ' + ctx.last_touch_date);
    if (meta.length || signals.length) {
      const label = document.createElement('div');
      label.className = 'v2-ctx-label';
      label.textContent = 'Outreach';
      outreach.appendChild(label);
      if (meta.length) {
        const el = document.createElement('div');
        el.className = 'v2-ctx-value';
        el.textContent = meta.join(' \u00B7 ');
        outreach.appendChild(el);
      }
      if (signals.length) {
        const el = document.createElement('div');
        el.className = 'v2-ctx-inferred';
        el.textContent = signals.join(' \u00B7 ');
        outreach.appendChild(el);
      }
    }
  }

  if (fit) {
    fit.textContent = '';
    const parts = [];
    if (ctx.priority_score != null) parts.push('Priority: ' + ctx.priority_score);
    if (ctx.paid_demand) parts.push('Paid demand: \u2713');
    if (ctx.coverage_gap_likely) parts.push('Coverage gap likely: \u2713');
    if (parts.length) {
      const label = document.createElement('div');
      label.className = 'v2-ctx-label';
      label.textContent = 'Fit';
      fit.appendChild(label);
      parts.forEach(p => {
        const el = document.createElement('div');
        el.className = 'v2-ctx-value';
        el.style.fontSize = '11px';
        el.textContent = p;
        fit.appendChild(el);
      });
    }
  }
}

// ── Right Rail: Tactical Support Card ───────────────────────────

/**
 * Render tactical support card in the right rail.
 * Order: ASK → REBUTTAL → VALUE → PROOF → IF/THEN
 * Hides empty sections. IF/THEN capped at 3.
 */
export function renderTacticalCard(card) {
  const ask = document.getElementById('v2-tac-ask');
  const rebuttal = document.getElementById('v2-tac-rebuttal');
  const value = document.getElementById('v2-tac-value');
  const proof = document.getElementById('v2-tac-proof');
  const ifthen = document.getElementById('v2-tac-ifthen');

  if (ask) {
    ask.textContent = '';
    if (card.clarifyingQuestion) {
      const label = document.createElement('div');
      label.className = 'v2-tac-label';
      label.textContent = 'Ask';
      const val = document.createElement('div');
      val.className = 'v2-tac-value';
      val.textContent = card.clarifyingQuestion;
      ask.appendChild(label);
      ask.appendChild(val);
    }
  }

  if (rebuttal) {
    rebuttal.textContent = '';
    const rebText = card.why && card.stage === 'OBJECTION' ? card.why : null;
    if (rebText) {
      const label = document.createElement('div');
      label.className = 'v2-tac-label';
      label.textContent = 'Rebuttal';
      const val = document.createElement('div');
      val.className = 'v2-tac-value';
      val.textContent = rebText;
      rebuttal.appendChild(label);
      rebuttal.appendChild(val);
    }
  }

  if (value) {
    value.textContent = '';
    if (card.valueProp) {
      const label = document.createElement('div');
      label.className = 'v2-tac-label';
      label.textContent = 'Value';
      const val = document.createElement('div');
      val.className = 'v2-tac-value';
      val.textContent = card.valueProp;
      value.appendChild(label);
      value.appendChild(val);
    }
  }

  if (proof) {
    proof.textContent = '';
    if (card.proofPoint) {
      const label = document.createElement('div');
      label.className = 'v2-tac-label';
      label.textContent = 'Proof';
      const val = document.createElement('div');
      val.className = 'v2-tac-value';
      val.textContent = card.proofPoint;
      proof.appendChild(label);
      proof.appendChild(val);
    }
  }

  if (ifthen) {
    ifthen.textContent = '';
    const entries = Object.entries(card.branchPreview || {}).slice(0, 3);
    if (entries.length > 0) {
      const label = document.createElement('div');
      label.className = 'v2-tac-label';
      label.textContent = 'If / Then';
      ifthen.appendChild(label);
      entries.forEach(([c, r]) => {
        const el = document.createElement('div');
        el.className = 'v2-tac-value';
        el.textContent = c + ' \u2192 ' + friendlyTarget(r.next || r.action || '');
        ifthen.appendChild(el);
      });
    }
  }
}

// ── Center Panel Orchestrator ───────────────────────────────────

/**
 * Render the full v2 center panel from a composed active card and state.
 */
export function renderV2CenterPanel(activeCard, state) {
  if (!activeCard) return;
  renderMoveTypePill(activeCard.moveType, activeCard.deliveryModifier, state.compound ? state._secondaryIntent : null);
  renderNowSummary(state.nowSummary);
  renderBackupLine(activeCard.backupLine);
  renderListenFor(activeCard.listenFor);
  renderBranchPreview(activeCard.branchPreview);
  // DO NOT strip is not triggered by default — only when specific conditions are met
  renderConditionalDoNot(null);
}
