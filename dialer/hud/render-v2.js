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
export function renderBranchPreview(branchPreview) {
  const el = document.getElementById('v2-branch-preview');
  if (!el) return;
  const entries = Object.entries(branchPreview || {}).slice(0, 3);
  if (entries.length === 0) {
    el.style.display = 'none';
    return;
  }
  el.style.display = 'block';
  // Build branch preview display using safe DOM methods
  const label = document.createElement('div');
  label.className = 'v2-next-label';
  label.textContent = 'NEXT';
  el.textContent = '';
  el.appendChild(label);
  entries.forEach(([cond, route]) => {
    const target = route.next || route.action || '';
    const span = document.createElement('span');
    span.style.marginRight = '12px';
    span.textContent = `${cond} \u2192 ${target}`;
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
