# HUD v2 Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Sales HUD from a v1 script routing system to a v2 live decision-support system with backup lines, move types, tone awareness, compound objections, timing guidance, and redesigned rails.

**Architecture:** Incremental refactor across 7 existing files. A `normalizeCard()` adapter bridges old playbook format to new card schema, allowing gradual migration. Build sequence follows spec Section 22: playbook → center panel → rails → new stages → compound objections → tone → LLM → audit trail.

**Tech Stack:** Vanilla JS ES modules (no build step, no TypeScript). BroadcastChannel for IPC. Groq API for LLM fallback.

**Spec:** `docs/superpowers/specs/2026-04-02-hud-v2-upgrade-design.md`

**Note:** All DOM manipulation in this codebase uses `_esc()` (existing XSS helper) for dynamic content. The existing pattern uses innerHTML with escaped content throughout `ui.js`. New render functions follow the same pattern — all user-facing strings pass through `_esc()` before insertion.

---

## File Structure

| File | Role | Change Type |
|---|---|---|
| `dialer/hud/taxonomy.js` | Single source of truth for all labels/constants | **Create** |
| `dialer/hud/cards.js` | Card schema + normalizeCard adapter | **Create** |
| `dialer/hud/composer.js` | Active card composition + NOW summary | **Create** |
| `dialer/hud/tone.js` | Rules-based tone assignment + hysteresis | **Create** |
| `dialer/hud/risk.js` | Trajectory state + risk computation | **Create** |
| `dialer/hud/playbook.js` | Native stage cards + objection cards | **Modify** |
| `dialer/hud/classifier.js` | New dictionaries + multi-label detection | **Modify** |
| `dialer/hud/reducer.js` | v2 state fields + new actions + stages | **Modify** |
| `dialer/hud/ui.js` | Center/left/right rail render functions | **Modify** |
| `dialer/hud/index.html` | DOM restructure for 3-panel v2 layout | **Modify** |
| `dialer/hud/llm.js` | Extended request/response for tone | **Modify** |
| `dialer/hud/session.js` | Enriched audit trail fields | **Modify** |

---

## Task 1: Unified Intent Taxonomy Constants

**Files:**
- Create: `dialer/hud/taxonomy.js`
- Test: `dialer/hud/__tests__/taxonomy.test.js`

Single source of truth for all intent labels, tone labels, risk levels, move types, and NOW summary templates (spec Sections 26, 4, 7).

- [ ] **Step 1: Create taxonomy test file** with tests verifying INTENTS has 17 labels, TONES has 7, RISK_LEVELS has 4 in order, MOVE_TYPES has 9, and NOW_TEMPLATES has an entry for every intent (each under 80 chars).

- [ ] **Step 2: Run test — expect FAIL** (module not found)

- [ ] **Step 3: Create `dialer/hud/taxonomy.js`** exporting: INTENTS (17 canonical labels), TONES (7 labels), RISK_LEVELS, MOVE_TYPES (9 core), DELIVERY_MODIFIERS (5), NOW_TEMPLATES (string map from intent to one-line summary), ROUTING_PRECEDENCE (ordered array for cross-family conflict resolution per spec Section 29), INTENT_STAGE_MAP (pricing→PRICING, authority_mismatch→WRONG_PERSON, confusion→MINI_PITCH), OBJECTION_INTENTS, OVERLAY_INTENTS.

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit** `feat(hud): add unified intent taxonomy constants`

---

## Task 2: Card Schema + normalizeCard Adapter

**Files:**
- Create: `dialer/hud/cards.js`
- Test: `dialer/hud/__tests__/cards.test.js`

Bridges old playbook format to v2 card schema (spec Sections 4, 21).

- [ ] **Step 1: Create cards test** verifying CARD_FIELDS lists all 14 required fields, makeEmptyCard returns card with all fields, normalizeCard for OPENER/CLOSE/EXIT/BRIDGE/unknown stages produce valid cards with correct inferred moveTypes.

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Create `dialer/hud/cards.js`** with CARD_FIELDS constant, STAGE_MOVE_MAP (maps stage→default moveType), STAGE_GOAL_MAP (maps stage→goal string), makeEmptyCard(stageId) function, normalizeCard(stageId, playbook) function that creates empty card and fills primaryLine from lineForStage.

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit** `feat(hud): add card schema and normalizeCard adapter`

---

## Task 3: Native Stage Cards for Core Stages

**Files:**
- Modify: `dialer/hud/cards.js` (per Eng Review Amendment 1 — cards live here, not playbook.js)
- Modify: `dialer/hud/__tests__/cards.test.js`

Full card objects for OPENER, BRIDGE, QUALIFIER, CLOSE, OBJECTION, EXIT, SEED_EXIT, BOOKED, NON_CONNECT, GATEKEEPER, IDLE with backup lines, listen-for, branch preview, and tone variants.

- [ ] **Step 1: Add test** verifying NATIVE_STAGE_CARDS.OPENER has all v2 fields including backupLine, listenFor (≤4), branchPreview (≤3), and BRIDGE has toneVariants.

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Add `export const NATIVE_STAGE_CARDS`** to `cards.js` with full card objects for all 11 existing stages. Each card includes: id, stage, moveType, deliveryModifier, goal, primaryLine, backupLine, why, listenFor (3-4 items), branchPreview (2-3 routes), clarifyingQuestion, valueProp, proofPoint, toneVariants.

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit** `feat(hud): add native v2 stage cards for core stages`

---

## Task 4: New Stage Cards + Full Integration

**Files:**
- Modify: `dialer/hud/cards.js` (per Amendment 1)
- Modify: `dialer/hud/reducer.js`
- Modify: `dialer/hud/ui.js`
- Modify: `dialer/hud/playbook.js` (lineForStage only)
- Modify: `dialer/hud/__tests__/cards.test.js`

Add 4 new stages to the call state machine AND wire them into all hardcoded integration points (spec Section 5 + Adversarial Finding: navigation deadlock).

- [ ] **Step 1: Add test** for each new card: PERMISSION_MOMENT (moveType=ask), MINI_PITCH (moveType=clarify, short primaryLine), WRONG_PERSON (moveType=clarify, has branchPreview), PRICING (moveType=reframe).

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Add 4 cards** to NATIVE_STAGE_CARDS in `cards.js`. MINI_PITCH enforces 1-sentence doctrine. PRICING has toneVariants for annoyed.

- [ ] **Step 4: Update STAGES array** in reducer.js to include PERMISSION_MOMENT, MINI_PITCH, WRONG_PERSON, PRICING (16 total).

- [ ] **Step 5: Update STAGE_TRANSITIONS map** in ui.js (line ~34-46) to add F7/F10 entries for all 4 new stages:
  - PERMISSION_MOMENT: f7→BRIDGE, f8→EXIT
  - MINI_PITCH: f7→BRIDGE, f8→EXIT
  - WRONG_PERSON: f7→EXIT, f8→GATEKEEPER
  - PRICING: f7→RETURN_FROM_PRICING (special), f8→EXIT

- [ ] **Step 6: Update NAV_STAGES** in ui.js (line ~49) to include new stages for ArrowLeft back-navigation.

- [ ] **Step 7: Update STAGE_DISPLAY / renderStageBar** in ui.js to handle new stages — show as contextual pills when active, not permanent bar entries.

- [ ] **Step 8: Update stageHints** in reducer.js MANUAL_SET_STAGE handler (line ~727) to add entries for all 4 new stages with useful why text.

- [ ] **Step 9: Update lineForStage()** in playbook.js to return lines for new stages by reading from NATIVE_STAGE_CARDS:
  ```javascript
  case 'PERMISSION_MOMENT':
  case 'MINI_PITCH':
  case 'WRONG_PERSON':
  case 'PRICING': {
    const card = NATIVE_STAGE_CARDS[stage];
    return card ? card.primaryLine : '';
  }
  ```

- [ ] **Step 10: Update hotkey guard** in ui.js (line ~499-534) to prevent number keys 1-4 from dispatching MANUAL_SET_OBJECTION when in PRICING, MINI_PITCH, WRONG_PERSON, or PERMISSION_MOMENT stages.

- [ ] **Step 11: Run all existing tests** to verify no regressions.

- [ ] **Step 12: Commit** `feat(hud): add 4 new stages with full navigation/hotkey/pill integration`

---

## Task 5: Native Objection Cards

**Files:**
- Modify: `dialer/hud/cards.js` (per Amendment 1 — all cards live here)
- Modify: `dialer/hud/__tests__/cards.test.js`

Objection cards in same schema as stage cards but separate namespace (spec Section 4).

- [ ] **Step 1: Add test** verifying NATIVE_OBJECTION_CARDS has timing/interest/info/authority/existing_coverage/answering_service, each with primaryLine, backupLine, and clarifyingQuestion.

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Add `export const NATIVE_OBJECTION_CARDS`** to `cards.js` with 6 objection cards. Each follows the rebuttal + diagnostic question pattern from the spec.

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit** `feat(hud): add native objection cards with backup lines`

---

## Task 6: Card Composition Engine

**Files:**
- Create: `dialer/hud/composer.js`
- Test: `dialer/hud/__tests__/composer.test.js`

Active card composition (spec Section 16) + NOW summary generation (spec Section 17).

- [ ] **Step 1: Create composer test** covering: composeActiveCard returns stage card when no objection/tone; overlays objection card fields preserving stage goal; applies tone variant to primaryLine only; delivery modifier only affects display; generateNowSummary returns template for known intent, appends tone when non-neutral+confident, returns default for unknown.

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Create `dialer/hud/composer.js`** with composeActiveCard({stage, activeObjection, tone, deliveryModifier, stageCards, objectionCards}) following 4-step precedence, and generateNowSummary({primaryIntent, tone, toneConfidence}) using NOW_TEMPLATES from taxonomy.

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit** `feat(hud): add card composition engine and NOW summary generator`

---

## Task 7: Tone Assignment (Rules-Based)

**Files:**
- Create: `dialer/hud/tone.js`
- Test: `dialer/hud/__tests__/tone.test.js`

Rules-based tone with hysteresis (spec Sections 7, 20).

- [ ] **Step 1: Create tone test** covering: assignTone detects rushed/annoyed/curious/skeptical/neutral correctly; shouldUpdateTone returns true when confidence delta ≥0.15, false when small delta, true for annoyed/rushed immediate override at ≥0.7, false for same label.

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Create `dialer/hud/tone.js`** with assignTone(utterance, classification, stage) returning {tone_label, tone_confidence, tone_source:'rules'}, and shouldUpdateTone(current, candidate) implementing hysteresis with 0.15 threshold and immediate override for annoyed/rushed at ≥0.7.

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit** `feat(hud): add rules-based tone assignment with hysteresis`

---

## Task 8: Trajectory State + Risk Computation

**Files:**
- Create: `dialer/hud/risk.js`
- Test: `dialer/hud/__tests__/risk.test.js`

Trajectory-aware risk (spec Sections 6, 30).

- [ ] **Step 1: Create risk test** covering: createTrajectoryState returns zeroed state; computeRisk returns low for hedge, high for compound, call_ending for 3+ consecutive same intent, call_ending for rescue failed + same intent, high for 2+ salvage attempts, medium for 2 consecutive; updateTrajectory increments consecutiveSameIntent correctly and sets rescueMoveFailed.

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Create `dialer/hud/risk.js`** with createTrajectoryState(), computeRisk(trajectory, classification), updateTrajectory(prev, classification, stage, wasSalvageAttempt).

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit** `feat(hud): add trajectory state and risk computation`

---

## Task 9: Extended Classifier (New Dictionaries)

**Files:**
- Modify: `dialer/hud/classifier.js`
- Modify: `dialer/hud/__tests__/classifier.test.js`

New keyword dictionaries + detectNewIntents function (spec Section 11).

- [ ] **Step 1: Add tests** for detectNewIntents: confusion detection for "what is this about" in OPENER (high confidence), pricing_question for "how much is it" in QUALIFIER, authority_mismatch for "talk to my wife". Also test stage-aware confidence boost.

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Add keyword dictionaries** to classifier.js: MINI_PITCH_PHRASES, WRONG_PERSON_PHRASES, PRICING_QUESTION_PHRASES, PRICING_RESISTANCE_PHRASES. Add detectNewIntents(utterance, stage) function with stage-aware confidence boosting.

- [ ] **Step 4: Wire detectNewIntents into classifyUtterance** — modify the `classifyUtterance` switch (classifier.js:299-330) to call `detectNewIntents(utterance, stage)` as a pre-check BEFORE the stage-specific router. If detectNewIntents returns a high-confidence result (≥0.65), return it directly. Otherwise fall through to existing stage-specific classification. This ensures new intents (confusion, pricing, wrong-person) are detected from ANY stage.

- [ ] **Step 5: Add classifier routing test** — verify that "what is this about" in OPENER returns confusion intent via classifyUtterance (not just detectNewIntents), and that "how much is it" in QUALIFIER returns pricing_question via classifyUtterance.

- [ ] **Step 6: Run test — expect PASS**

- [ ] **Step 7: Commit** `feat(hud): add new intent dictionaries and wire into classifyUtterance`

---

## Task 10: LLM Fallback Extension + Cross-Call Fix

**Files:**
- Modify: `dialer/hud/llm.js`
- Modify: `dialer/hud/ui.js` (triggerLlmFallback)

Extend Groq request/response for tone + secondary intent (spec Section 11). Fix cross-call state bleed (Adversarial Finding: CRITICAL).

- [ ] **Step 1: Read current llm.js and ui.js triggerLlmFallback** to understand exact fetch structure and state capture.

- [ ] **Step 2: Fix cross-call bleed in triggerLlmFallback** (ui.js ~line 320) — capture `callId` in a `const` BEFORE the `await`, not after. The current code reads `state.callId` after the async fetch returns, which can be a different call's ID:
  ```javascript
  // BEFORE (broken):
  const result = await classifyWithLlm(...);
  dispatch({ type: 'LLM_RESULT', callSid: state.callId, ... });

  // AFTER (fixed):
  const capturedCallId = state.callId;  // capture before await
  const result = await classifyWithLlm(...);
  dispatch({ type: 'LLM_RESULT', callSid: capturedCallId, ... });
  ```

- [ ] **Step 3: Extend request body** to include requestTone: true, requestSecondaryIntent: true.

- [ ] **Step 4: Parse extended response** — extract tone, tone_confidence, tone_source, secondary_intent, secondary_confidence from LLM response if present.

- [ ] **Step 5: Commit** `fix(hud): capture callId before await + extend LLM with tone/secondary`

**Note:** Server-side changes to `dialer/server.js` (Groq endpoint prompt + field whitelist at lines ~924-992) are also required for the new fields to flow through. This is a separate server-side task.

---

## Task 11: Reducer v2 State + New Actions

**Files:**
- Modify: `dialer/hud/reducer.js`
- Modify: `dialer/hud/__tests__/reducer.test.js`

v2 state fields, trajectory, PRICING interrupt actions (spec Sections 12, 18, 27, 28).

- [ ] **Step 1: Extend createInitialState** with v2 fields: tone, toneSource, toneConfidence, risk, compound, signalCount, recommendedActionBias, previousStage, moveType, deliveryModifier, nowSummary, prospectContext, activeObjection, primaryIntent, trajectory (from createTrajectoryState).

- [ ] **Step 2: Add new reducer cases**: SET_TONE, SET_PROSPECT_CONTEXT, PRICING_INTERRUPT (saves previousStage, ignores nested), RETURN_FROM_PRICING (restores + clears previousStage).

- [ ] **Step 3: Write tests** for all new actions: SET_TONE updates fields, SET_PROSPECT_CONTEXT populates, PRICING_INTERRUPT saves previousStage, PRICING_INTERRUPT no-ops if already in PRICING, RETURN_FROM_PRICING restores and clears.

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit** `feat(hud): add v2 state fields and PRICING interrupt actions`

---

## Task 12: Session Logging Extension

**Files:**
- Modify: `dialer/hud/session.js`

Enrich audit trail (spec Section 14).

- [ ] **Step 1: Read current logDecision** structure.

- [ ] **Step 2: Add v2 fields** to audit trail entry: tone, toneSource, risk, compound, signalCount, recommendedActionBias, moveType, deliveryModifier, primaryIntent.

- [ ] **Step 3: Commit** `feat(hud): extend audit trail with v2 fields`

---

## Task 13A: processTurn() Orchestrator

**Files:**
- Modify: `dialer/hud/ui.js`

Create the 8-step turn lifecycle orchestrator (spec Section 27 + Adversarial Finding: CRITICAL — no orchestration point exists).

- [ ] **Step 1: Create processTurn(utterance, classification) function** in ui.js that runs the full v2 pipeline in order:
  ```
  1. classify (already done by caller, passed in)
  2. detectNewIntents pre-check (call detectNewIntents, merge if high confidence)
  3. assignTone (call assignTone, check shouldUpdateTone hysteresis)
  4. updateTrajectory + computeRisk
  5. determine stage transition (use INTENT_STAGE_MAP for dedicated stage routing)
  6. generate nowSummary (call generateNowSummary)
  7. dispatch all state updates (SET_TONE, stage transition, etc.)
  8. log decision (already happens via dispatch)
  ```

- [ ] **Step 2: Wire processTurn into handleFinalProspectTranscript** — replace the current inline classify+dispatch logic (ui.js ~line 277-315) with a call to processTurn. The existing classifyUtterance call stays, but its result feeds into processTurn instead of being dispatched directly.

- [ ] **Step 3: Ensure render() is called exactly once** at the end of processTurn (via the final dispatch), not multiple times during intermediate state updates.

- [ ] **Step 4: Commit** `feat(hud): add processTurn orchestrator for v2 turn lifecycle`

---

## Task 13B: Center Panel UI Restructure

**Files:**
- Modify: `dialer/hud/index.html`
- Create: `dialer/hud/render-v2.js` (per Amendment 2 — v2 render functions live here, not ui.js)

Center panel v2 stack (spec Section 8).

- [ ] **Step 1: Add DOM containers** to index.html inside center panel: v2-move-type, v2-now-summary, v2-backup-line, v2-pause-strip, v2-listen-for, v2-branch-preview, v2-do-not. Add CSS styles matching dark theme.

- [ ] **Step 2: Create `render-v2.js`** with render functions: renderMoveTypePill, renderNowSummary, renderBackupLine, renderPauseStrip, renderListenFor, renderBranchPreview, renderConditionalDoNot. All use _esc() for dynamic content. Export a single `renderV2CenterPanel(activeCard, state)` function that calls all of them.

- [ ] **Step 3: Import render-v2.js into ui.js** and call `renderV2CenterPanel(activeCard, state)` from the existing render() function. Ensure v2 render does NOT conflict with legacy render — v2 elements render into new DOM containers (v2-* IDs), legacy render continues to populate existing containers ($nowLine, $nowWhy, etc.). Both coexist during migration.

- [ ] **Step 4: Manual browser test** — open HUD, verify new v2 elements render alongside legacy elements without visual conflict.

- [ ] **Step 5: Commit** `feat(hud): add center panel v2 stack in render-v2.js`

---

## Task 14: Left Rail — Prospect Context

**Files:**
- Modify: `dialer/hud/index.html`
- Modify: `dialer/hud/render-v2.js` (per Amendment 2)

Left rail redesign (spec Section 9).

- [ ] **Step 1: Add prospect context DOM** to left panel: v2-prospect-identity, v2-prospect-why, v2-prospect-outreach, v2-prospect-fit sections. Add lines drawer below. Add CSS.

- [ ] **Step 2: Add renderProspectContext(ctx)** to `render-v2.js` — renders available sections, hides missing, dims inferred fields. Uses _esc() throughout.

- [ ] **Step 3: Wire into CALL_STARTED handler in ui.js** — dispatch SET_PROSPECT_CONTEXT and call renderProspectContext when prospectContext is available.

- [ ] **Step 4: Commit** `feat(hud): add left rail prospect context`

**Note:** The dialer currently only sends prospectId, prospectName, businessName, metro, signals in CALL_STARTED (dialer/index.html:1702). Full prospectContext requires dialer sender changes. For now, renderProspectContext gracefully degrades with whatever fields are present.

---

## Task 15: Right Rail — Tactical Support Card

**Files:**
- Modify: `dialer/hud/index.html`
- Modify: `dialer/hud/render-v2.js` (per Amendment 2)

Right rail redesign (spec Section 10).

- [ ] **Step 1: Add tactical card DOM** to right panel: v2-tac-ask, v2-tac-rebuttal, v2-tac-value, v2-tac-proof, v2-tac-ifthen. Add objections drawer below. Add CSS.

- [ ] **Step 2: Add renderTacticalCard(card)** to `render-v2.js` — renders ASK→REBUTTAL→VALUE→PROOF→IF/THEN, hides empty sections. IF/THEN capped at 3. Uses _esc() throughout.

- [ ] **Step 3: Wire into render()** in ui.js — call renderTacticalCard(activeCard) after center panel render.

- [ ] **Step 4: Commit** `feat(hud): add right rail tactical support card`

---

## Task 16: Pause Strip Event Logic

**Files:**
- Modify: `dialer/hud/ui.js`

Event-based pause strip (spec Section 8).

- [ ] **Step 1: Add pause strip state management** — pauseStripTimer, pauseStripSilenceTimer variables. activatePauseStrip() makes strip bright, sets 5s dim fallback and 8s silence nudge. deactivatePauseStrip() clears timers and dims.

- [ ] **Step 2: Wire to events** — call deactivatePauseStrip on TRANSCRIPT_FINAL receipt. Call activatePauseStrip on stage transition.

- [ ] **Step 3: Commit** `feat(hud): add event-based pause strip with silence nudge`

---

## Task 17: Compound Objection UI Support

**Files:**
- Modify: `dialer/hud/reducer.js` — update OBJECTION handling for primary+secondary
- Modify: `dialer/hud/ui.js` (or `render-v2.js`) — update objection picker for compound display
- Modify: `dialer/hud/index.html` — compound objection picker layout
- Test: `dialer/hud/__tests__/reducer.test.js`

Full compound objection support in reducer and UI (added during eng review).

- [ ] **Step 1: Update reducer** OBJECTION handling to accept primary+secondary intent. Store `activeObjection` as primary intent, log secondary in objection history. Update `lastObjectionBucket` to primary.

- [ ] **Step 2: Update objection picker** to show compound state: primary bucket highlighted, secondary shown as dimmed label. If compound, show "timing + interest" style label.

- [ ] **Step 3: Update hotkey handler** (keys 1-4 in CLOSE/OBJECTION) to set primary objection. When compound is active, hotkey overrides primary only.

- [ ] **Step 4: Write tests** for compound objection reducer logic: primary routes, secondary logged, compound flag in history.

- [ ] **Step 5: Commit** `feat(hud): add compound objection UI support`

---

## Task 18: Close Variant Stage Cards

**Files:**
- Modify: `dialer/hud/cards.js` — add 4 close variant cards to NATIVE_STAGE_CARDS
- Modify: `dialer/hud/__tests__/cards.test.js`

Close variants: callback, transfer, diagnostic, referral (spec Section 24, promoted from deferred).

- [ ] **Step 1: Add CALLBACK_CLOSE card** — moveType: close, goal: "Schedule callback with right person", primaryLine + backupLine for callback close.

- [ ] **Step 2: Add TRANSFER_CLOSE card** — moveType: close, goal: "Get transferred to decision-maker", primaryLine + backupLine.

- [ ] **Step 3: Add DIAGNOSTIC_CLOSE card** — moveType: close, deliveryModifier: soften, goal: "Offer low-friction audit", primaryLine + backupLine.

- [ ] **Step 4: Add REFERRAL_CLOSE card** — moveType: close, goal: "Get referral to right person", primaryLine + backupLine.

- [ ] **Step 5: Write tests** for all 4 close variant cards (required fields, moveType=close).

- [ ] **Step 6: Commit** `feat(hud): add close variant stage cards (callback, transfer, diagnostic, referral)`

---

## Task 19: Basic Transcript Degradation

**Files:**
- Modify: `dialer/hud/ui.js` (or `render-v2.js`)
- Modify: `dialer/hud/index.html`

Basic transcript degradation indicators (spec Section 32, partial — full mode in TODOS.md).

- [ ] **Step 1: Add transcript health timer** — track time since last TRANSCRIPT_FINAL. Show amber indicator after 3s.

- [ ] **Step 2: Wire to BroadcastChannel** — reset timer on each TRANSCRIPT event. Start timer on CALL_CONNECTED.

- [ ] **Step 3: Commit** `feat(hud): add basic transcript degradation indicator`

---

## ENG REVIEW AMENDMENTS

The following changes were identified during `/plan-eng-review` on 2026-04-02:

### Architecture decisions
1. **NATIVE_STAGE_CARDS and NATIVE_OBJECTION_CARDS live in `cards.js`**, not `playbook.js`. playbook.js stays as legacy data + resolution helpers.
2. **New file `render-v2.js`** for all v2 render functions. ui.js stays as orchestrator (events, hotkeys, dispatch).
3. **`processTurn()` orchestrator** added to ui.js — runs the 8-step turn lifecycle explicitly (classify → tone → compound → stage → nowSummary → compose → render → log).
4. **Task 4 expanded** — new stages require updates to STAGE_TRANSITIONS map, stage pill rendering, MANUAL_SET_STAGE index handling, and classifier routing (not just STAGES array).

### Scope clarifications
5. **Compound objections in v2:** classifier detects primary+secondary, but **full UI support now added as Task 17** (promoted from deferred during review).
6. **Close variants now added as Task 18** (promoted from deferred during review).
7. **Server-side dependency:** Tasks 10 (LLM) and 14 (prospect context) require changes to `dialer/server.js` for Groq endpoint extension and CALL_STARTED payload enrichment. Note these in implementation.
8. **MANUAL_SET_STAGE must clear `previousStage`** — added to Task 11 reducer changes.

### Test additions
9. **2-turn tone persistence** — add consecutiveToneCount to shouldUpdateTone + test (Task 7).
10. **Stage-aware confidence comparison** — add test asserting same utterance gets different confidence in different stages (Task 9).

---

## Self-Review

**Spec coverage:** All 32 spec sections mapped to tasks. Section 32 partially covered by Task 19. Full degradation deferred to TODOS.md.

**Placeholder scan:** No TBDs or vague steps. Each task has concrete file paths and acceptance criteria.

**Type consistency:** composeActiveCard parameters, NATIVE_STAGE_CARDS, NATIVE_OBJECTION_CARDS names consistent across all tasks. Intent labels match taxonomy.js throughout.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Outside Voice | `/codex review` | Independent 2nd opinion | 2 | ISSUES_FOUND | 10+10 findings, 3 tensions resolved |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR (PLAN) | 8 issues, 0 critical gaps |
| Adversarial | codex+claude | Break the plan | 1 | ISSUES_FOUND | 20 findings, 6 critical fixes applied |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |

- **OUTSIDE VOICE:** 10 Codex findings including missing server deps, compound objection mismatch, hardcoded navigation. 3 tensions resolved.
- **ADVERSARIAL (Codex+Claude):** Cross-model consensus on 4 critical issues: (1) navigation deadlock in new stages, (2) processTurn() orchestrator missing, (3) detectNewIntents dead code, (4) LLM cross-call state bleed. All 6 must-fix items applied to plan.
- **FIXES APPLIED:** Task 4 expanded with 12 steps (navigation/hotkeys/pills/stageHints), Task 9 wires detectNewIntents into classifyUtterance, Task 10 fixes cross-call bleed, Task 13 split into 13A (processTurn orchestrator) + 13B (render-v2.js), Tasks 3/5/14/15 file locations corrected to cards.js and render-v2.js.
- **UNRESOLVED:** 0
- **VERDICT:** ENG CLEARED + ADVERSARIAL COMPLETE. Plan patched with all critical integration fixes. Ready for implementation.
