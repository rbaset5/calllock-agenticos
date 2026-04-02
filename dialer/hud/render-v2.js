// dialer/hud/render-v2.js
// v2 render functions for the center panel, left rail, and right rail.
// Separated from ui.js per eng review Amendment 2.

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
export function renderMoveTypePill(moveType, deliveryModifier) {
  const el = document.getElementById('v2-move-type');
  if (!el) return;
  const label = deliveryModifier ? `${moveType} · ${deliveryModifier}` : (moveType || '');
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
        el.textContent = c + ' \u2192 ' + (r.next || r.action || '');
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
  renderMoveTypePill(activeCard.moveType, activeCard.deliveryModifier);
  renderNowSummary(state.nowSummary);
  renderBackupLine(activeCard.backupLine);
  renderListenFor(activeCard.listenFor);
  renderBranchPreview(activeCard.branchPreview);
  // DO NOT strip is not triggered by default — only when specific conditions are met
  renderConditionalDoNot(null);
}
