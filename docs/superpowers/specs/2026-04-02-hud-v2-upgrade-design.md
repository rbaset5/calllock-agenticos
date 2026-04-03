# HUD v2 Upgrade — Design Spec

**Date:** 2026-04-02
**Status:** Draft
**Scope:** Upgrade the Sales HUD from a v1 script routing system to a v2 live decision-support system

---

## 1. Problem

The current HUD picks the right line for the stage, but lacks the deeper layers needed for real cold-call coaching: moment interpretation, move-type selection, tone awareness, backup lines, branch previews, tactical support, and timing guidance. The gap analysis scored it ~5/10 against the full v2 spec.

## 2. Goals

After this upgrade, the HUD should answer in real time:

1. What is happening? (NOW summary)
2. What kind of move is needed? (move type + delivery modifier)
3. What should I say? (primary line + backup line)
4. Why this move? (strategic reasoning)
5. What do I listen for next? (response classification cues)
6. Where does this go? (branch preview)
7. Am I making a timing mistake? (pause/timing guidance)

## 3. Out of Scope

- Full rep-coaching system (talked too long, skipped discovery, premature pitching, missed buying signal)
- Post-call review analytics
- Full emotional state tracking beyond 6 tone labels

**In scope but constrained:** A small rule-based conditional warning strip (e.g., "Don't answer pricing directly yet") — this is NOT a full rep-coaching system. It fires on explicit, high-confidence triggers only (see Section 8).

---

## 4. Stage Card Schema

Every stage and objection branch becomes a self-contained card object. The playbook is restructured into two namespaces: `stages` and `objections`.

```javascript
{
  id: 'PATTERN_DISCOVERY',
  stage: 'PATTERN_DISCOVERY',
  moveType: 'ask',                    // core move type
  deliveryModifier: null,             // optional: compress, soften, hold, escalate, redirect
  goal: 'Get them talking about current call-handling reality',
  primaryLine: "When a new customer calls and you can't pick up, what usually happens?",
  backupLine: "Is that call usually answered live, sent to voicemail, forwarded, or called back later?",
  why: 'Moves from opener into real workflow instead of abstract claims.',
  listenFor: [
    'real workflow',
    'vague answer',
    'defensive answer',
    'existing solution claim'
  ],
  branchPreview: {
    engaged: { next: 'WORKFLOW_DISCOVERY' },
    pushback: { next: 'OBJECTION' },
    confused: { next: 'MINI_PITCH' },
    rushed: { action: 'compress_question' }
  },
  clarifyingQuestion: "What tends to happen once that call isn't answered live?",
  valueProp: null,
  proofPoint: null,
  toneVariants: {
    rushed: {
      primaryLine: "Quick thing — when a new customer calls and nobody can grab it, what usually happens?"
    },
    annoyed: {
      primaryLine: "Totally understood — one quick question before I let you go: what happens when a new call comes in and no one can answer live?"
    },
    curious: {
      primaryLine: "Got it — the part I'd be curious about is what happens when a new call comes in and the team's tied up."
    }
  }
}
```

### Core Move Types
ask, clarify, probe, reframe, bridge, quantify, close, exit, pause

### Delivery Modifiers (optional, shown as pill suffix)
compress, soften, hold, escalate, redirect

### Playbook Structure
```javascript
playbook = {
  doctrine: { ... },
  stages: {
    IDLE: { ... },
    OPENER: { ... },
    PERMISSION_MOMENT: { ... },
    MINI_PITCH: { ... },
    GATEKEEPER: { ... },
    WRONG_PERSON: { ... },
    BRIDGE: { ... },
    QUALIFIER: { ... },
    PRICING: { ... },
    CLOSE: { ... },
    SEED_EXIT: { ... },
    OBJECTION: { ... },
    BOOKED: { ... },
    EXIT: { ... },
    NON_CONNECT: { ... },
    ENDED: { ... }
  },
  objections: {
    timing: { ... },
    interest: { ... },
    info: { ... },
    authority: { ... },
    pricing_question: { ... },
    pricing_resistance: { ... },
    existing_coverage: { ... },
    answering_service: { ... }
  },
  power: [ ... ],       // any-stage power lines (existing)
  recovery: [ ... ],    // any-stage recovery lines (existing)
  pitch: [ ... ]        // any-stage pitch lines (existing)
}
```

### Constraints
- `listenFor` capped at 3-4 items max
- `branchPreview` capped at 2-3 routes (most likely, most dangerous, one alternate)
- `toneVariants` optional per card — only where tone materially changes delivery
- `valueProp` and `proofPoint` optional — not every stage needs them
- `MINI_PITCH` doctrine: 1 sentence max, no feature stack, return to question fast

---

## 5. New Stages

### Added Stages

| Stage | Purpose | Entry | Exit |
|---|---|---|---|
| `PERMISSION_MOMENT` | Do I have room to continue? | OPENER | MINI_PITCH, BRIDGE, EXIT |
| `MINI_PITCH` | Answer "what is this about?" in 1 sentence | OPENER, GATEKEEPER, PERMISSION_MOMENT, BRIDGE | BRIDGE, OBJECTION, EXIT |
| `WRONG_PERSON` | Authority mismatch / referral path | GATEKEEPER, OPENER, any stage on authority detection | EXIT, GATEKEEPER (callback), referral capture action |
| `PRICING` | Handle premature pricing questions | QUALIFIER, CLOSE, BRIDGE | Return to `previousStage`, EXIT |

### Stage-Aware Routing

New stages are NOT triggered by global keyword matching alone. Transition logic uses:

1. Keyword match (dictionaries in classifier)
2. Current stage weighting (same keyword means different things in different stages)
3. Confidence threshold (low-confidence matches don't trigger stage jumps)

Examples:
- "what is this" in OPENER = high-confidence MINI_PITCH
- "what is this" in QUALIFIER = probably confusion, not MINI_PITCH
- "how much" in QUALIFIER = high-confidence PRICING
- "expensive" in OBJECTION = could be pricing or skepticism, depends on context

### PRICING as Interrupt Branch

PRICING preserves `previousStage` in state. After handling, it routes back:
```javascript
// In reducer
case 'PRICING':
  state.previousStage = state.stage  // save return point
  state.stage = 'PRICING'
```

### WRONG_PERSON Exits (not exit-only)
- EXIT (clean end)
- GATEKEEPER (callback to right person)
- Referral capture action (log contact intelligence, continue)

### Full Stage List (16 stages)
IDLE, OPENER, PERMISSION_MOMENT, MINI_PITCH, GATEKEEPER, WRONG_PERSON, BRIDGE, QUALIFIER, PRICING, CLOSE, SEED_EXIT, OBJECTION, BOOKED, EXIT, NON_CONNECT, ENDED

### Stage Bar Display
Linear pills show the primary flow: IDLE → GK → OPEN → PERM → BRIDGE → QUAL → CLOSE
Branch stages (MINI_PITCH, WRONG_PERSON, PRICING, OBJECTION) appear contextually when active, not as permanent pills.

---

## 6. Compound Objection Handling

### Classifier Return Shape

```javascript
{
  primary: { intent: 'interest', score: 4.5 },
  secondary: { intent: 'timing', score: 2.8 },  // null if single signal
  tone: 'rushed',
  risk: 'high',
  compound: true,
  signalCount: 2,
  recommendedActionBias: 'compress'
}
```

### Intent Labels
timing, interest, info, authority, pricing_question, pricing_resistance, existing_coverage, answering_service, confusion, curiosity

### Tone Labels (6 + unknown)
rushed, skeptical, annoyed, curious, guarded, neutral, unknown

### Risk Levels
- `low`: hedge/soft pushback, single signal
- `medium`: single objection with moderate confidence
- `high`: compound objection, repeated same intent
- `call_ending`: explicit dismissal + time pressure, repeated resistance after salvage, authority mismatch + refusal to redirect, obvious exit language

### Risk Triggers for `call_ending` (behavioral, not count-based)
- Explicit dismissal combined with time pressure
- Repeated rejection after salvage attempt
- Authority mismatch with refusal to redirect
- Obvious exit language ("gotta go", "don't call back")
- Severe interruption / cut-off behavior

### Priority Order (when scores are close, margin < 1.5)
1. authority (can't sell to wrong person)
2. timing (call-ending threat)
3. pricing (conversation-shaping)
4. info (deflection)
5. interest (diagnosable resistance)

### Recommended Action Bias Values
compress, clarify, diagnose, diagnose_briefly, exit, exit_or_redirect, soften

### Backup Line Rule
Backup line = safest alternate move for the compound moment. NOT automatically the secondary intent handler. The backup addresses the best fallback given primary + secondary + risk together.

---

## 7. Tone Layer

### Architecture: Hybrid (rules baseline + LLM refinement)

**Step 1 — Rules assign default tone every turn:**
```javascript
{
  tone_label: 'rushed',
  tone_confidence: 0.65,
  tone_source: 'rules'
}
```

**Rule heuristics:**
- Very short response + objection = `rushed`
- Repeated rejection phrases = `annoyed`
- Genuine follow-up question = `curious`
- Neutral existing-solution statement = `guarded`
- Premise challenge / disbelief = `skeptical`
- None of the above = `neutral`

**Step 2 — LLM refines (only when already firing for low-confidence classification):**

The existing Groq fallback call is extended to also return:
```javascript
{
  primary_intent: '...',
  secondary_intent: '...',
  tone: 'annoyed',
  tone_confidence: 0.82
}
```

Override rules:
- LLM tone replaces rules tone ONLY if LLM tone_confidence > rules tone_confidence by meaningful margin (>0.15)
- Set `tone_source: 'llm_refined'`
- No separate LLM call for tone in v1

### Tone Effect on Lines
Tone adjusts delivery (wording tightness, softness, pacing), not routing. Same branch, different line.

### Tone Stability
Do not churn tone turn-to-turn on minor differences. Only update tone when it materially changes (different label, not just different confidence for same label).

---

## 8. Center Panel — Full Stack

### Visual Priority (top to bottom)

1. **Stage + Move Type pill** — `BRIDGE ▸ probe` or `QUALIFIER ▸ ask · compress`
2. **NOW** — one-line plain-English summary of current moment
3. **Primary Line** — large, readable, the main recommended line
4. **ALT** — backup line, smaller, secondary visual weight
5. **PAUSE strip** — timing guidance, event-based behavior
6. **WHY** — one-line strategic reasoning (no classifier jargon)
7. **LISTEN FOR** — 3-4 response classification cues
8. **NEXT** — 2-3 branch preview routes
9. **Confidence badge** — RULE/LLM/MANUAL/FALLBACK, visually secondary
10. **Conditional DO NOT strip** — appears only when triggered (e.g., "Don't answer pricing directly yet")

### Pause Strip Behavior

**Event definitions:**
- "Prospect speech resumes" = a new `TRANSCRIPT_FINAL` message with `speaker: 'prospect'` arrives
- "Rep speaks again" = a new `TRANSCRIPT_FINAL` message with `speaker: 'agent'` arrives
- Partial ASR tokens (interim transcripts) do NOT count — only final segments trigger state change
- Silence timer does NOT reset on transcript fragments

**Behavior:**
- **Bright** immediately after line selection / stage transition
- **Stay bright** until prospect speech resumes or rep speaks again (event-based first)
- **Dim** after speech event received
- **Time-based fallback**: if no speech event after 5s, dim anyway
- **Extended silence nudge**: if silence > 8s, show subtle "Hold. Let them answer."
- More prominent in OPENER, BRIDGE, CLOSE stages

### Move Type Display
The pill shows core move type, optionally suffixed with delivery modifier:
- `probe` (no modifier)
- `ask · compress` (with modifier)
- `clarify · soften` (with modifier)

---

## 9. Left Rail — Prospect Context

### Purpose
Stable context that rarely changes during the call. Anchors the rep: "I know who this is and why they're worth the interruption."

### Data Source
Optional `prospectContext` object on `CALL_STARTED` BroadcastChannel message. Fields are individually optional — render what's available, hide what's missing.

### Sections (rendered if data present)

**Prospect Identity:**
- name, title, company, location, industry/segment

**Why This Account:**
- fit_reason (one line)
- trigger_reason (one line)

**Outreach History:**
- sequence_step, calls_made, emails_sent
- engagement signals (opens, clicks, replies)
- last_touch_date

**Fit Snapshot:**
- priority_score
- paid_demand (boolean)
- coverage_gap_likely (boolean)
- after_hours_relevant (boolean)

### Graceful Degradation
- Missing fields: section hidden entirely (no empty placeholders)
- Heuristic/inferred fields: dimmer text or "likely" prefix (e.g., "Likely after-hours leakage")
- If entire `prospectContext` is null: left rail shows only name + business from top bar, no fake context

---

## 10. Right Rail — Tactical Support Card

### Purpose
Support the current move. NOT "center part two."

### Visual Priority (top to bottom)

1. **ASK** — clarifying question that keeps the call moving
2. **REBUTTAL** — matched to detected objection/topic
3. **VALUE** — one value prop for this moment
4. **PROOF** — one proof point
5. **IF/THEN** — 2-3 most likely next branches (capped, not a full tree)

### Data Source
Fields from the current active stage card: `clarifyingQuestion`, active rebuttal from objection card, `valueProp`, `proofPoint`, `branchPreview` (top 2-3 entries).

### Fallback (constrained)
If card has null tactical fields, show fewer modules — not more generic ones. Empty is better than misleading.
- No generic proof unless it matches the current stage family
- No generic rebuttal unless an objection is actively detected
- If data is weak, hide the module entirely rather than filling it with vague copy

### Previous Content
The existing LINES panel and full OBJECTIONS list move to an expandable drawer/tab — accessible but not primary real estate.

---

## 11. Classifier Changes

### New Keyword Dictionaries

**MINI_PITCH triggers:**
"what is this", "what do you do", "what's this about", "who are you", "what company", "what are you selling"

**WRONG_PERSON triggers:**
"I don't handle that", "talk to my wife", "talk to my partner", "talk to dispatcher", "wrong person", "I'm the tech", "I'm the helper", "not my decision", "owner isn't here"

**PRICING triggers (split):**
- `pricing_question`: "how much", "what's the cost", "pricing", "what do you charge", "price range"
- `pricing_resistance`: "expensive", "can't afford", "too much", "not worth it", "out of budget"

### Multi-Label Detection
`classifyObjection()` returns primary + secondary intent, scored independently. Secondary is null if only one signal detected.

### Tone Assignment (rules-based)
New function `assignTone(utterance, classification, stage)`:
- Returns `{ tone_label, tone_confidence, tone_source: 'rules' }`
- Heuristics based on utterance length, keyword patterns, stage context, classification result

### Stage-Aware Routing
`classifyUtterance()` weighs keyword matches against current stage:
- Stage-appropriate matches get full score
- Cross-stage matches get reduced confidence
- Below threshold = no stage jump, just log the signal

### LLM Fallback Extension
The Groq request body gains:
```javascript
{
  utterance,
  stage,
  bridgeAngle,
  lastObjectionBucket,
  utteranceId,
  // NEW:
  requestTone: true,
  requestSecondaryIntent: true
}
```

LLM response gains `tone`, `tone_confidence`, `secondary_intent` fields.

---

## 12. Reducer Changes

### New State Fields
```javascript
{
  // existing fields preserved...

  // NEW:
  tone: 'neutral',
  toneSource: 'rules',
  risk: 'low',
  compound: false,
  signalCount: 0,
  recommendedActionBias: null,
  previousStage: null,           // for PRICING interrupt return
  moveType: 'pause',             // current move type
  deliveryModifier: null,        // current delivery modifier
  nowSummary: '',                // plain-English moment summary
  prospectContext: null,         // left rail data
  activeCard: null,              // current stage card reference
}
```

### New Action Types
- `SET_TONE`: Update tone from rules or LLM
- `SET_PROSPECT_CONTEXT`: Populate left rail data from CALL_STARTED
- `PRICING_INTERRUPT`: Save previousStage, enter PRICING
- `RETURN_FROM_PRICING`: Restore previousStage

### Stage Transition Updates
- OPENER → PERMISSION_MOMENT (new intermediate)
- PERMISSION_MOMENT → MINI_PITCH / BRIDGE / EXIT
- Any stage + pricing detection → PRICING (interrupt, saves previousStage)
- Any stage + wrong-person detection → WRONG_PERSON
- WRONG_PERSON → EXIT / GATEKEEPER / referral action

---

## 13. UI Changes (ui.js + index.html)

### Layout Restructure
- **Left rail**: Prospect context (new), replaces LINES panel
- **Center**: Full command stack (stage+move, NOW, lines, pause, WHY, listen-for, next)
- **Right rail**: Tactical support card (new), replaces OBJECTIONS list
- **Drawer/tab**: LINES panel + OBJECTIONS list (moved from main view)

### New Render Functions
- `renderProspectContext(prospectContext)`: Left rail sections with graceful degradation
- `renderTacticalCard(activeCard)`: Right rail support card
- `renderMoveTypePill(moveType, deliveryModifier)`: Stage banner pill
- `renderNowSummary(nowSummary)`: One-line moment summary
- `renderBackupLine(backupLine)`: Secondary line display
- `renderPauseStrip(stage)`: Event-based pause/timing guidance
- `renderListenFor(listenFor)`: Response classification cues
- `renderBranchPreview(branchPreview)`: Next routes (2-3 items)
- `renderConditionalDoNot(warning)`: Conditional correction strip
- `renderDrawer(linesPanel, objectionsPanel)`: Expandable secondary content

### Hotkey Updates
- Existing hotkeys preserved
- No new hotkeys required (new content is display-only, not interactive)

### BroadcastChannel Updates
- `CALL_STARTED` gains optional `prospectContext` field
- Existing message types unchanged

---

## 14. Session/Logging Changes

### Audit Trail Extension
Each logged decision gains:
```javascript
{
  // existing fields...
  tone,
  toneSource,
  risk,
  compound,
  signalCount,
  recommendedActionBias,
  moveType,
  deliveryModifier
}
```

No new API endpoints. The existing `/hud/session-log` POST carries the richer audit trail.

---

## 15. File Impact Summary

| File | Change Type | Scope |
|---|---|---|
| `playbook.js` | **Major refactor** | Restructure into stage cards + objection cards |
| `classifier.js` | **Major extension** | Multi-label, tone, new dictionaries, stage-aware routing |
| `reducer.js` | **Moderate extension** | New state fields, new actions, new stages |
| `ui.js` | **Major refactor** | New render functions, layout restructure |
| `index.html` | **Major refactor** | New DOM structure for 3-column redesign |
| `llm.js` | **Minor extension** | Extended request/response for tone + secondary intent |
| `session.js` | **Minor extension** | Richer audit trail fields |

---

## 16. Active Card Composition Precedence

When the HUD renders a moment, multiple data sources may contribute. The `activeCard` is assembled in this exact order:

1. **Start with current stage card** — `playbook.stages[state.stage]`
2. **If objection active**, select and overlay the objection card:
   - **Selection rule**: prefer the most specific overlay over generic buckets. `existing_coverage` and `answering_service` win over generic `interest`. `pricing_question`/`pricing_resistance` route to PRICING stage instead (see Section 19). Primary intent decides routing; if primary is generic but secondary is specific and above confidence threshold (≥0.6), use the specific overlay.
   - Override: `primaryLine`, `backupLine`, `why`, `clarifyingQuestion`, `valueProp`, `proofPoint`
   - Preserve from stage card: `moveType`, `goal`, `listenFor`, `branchPreview` (unless objection card provides its own)
3. **If tone variant exists** for current `state.tone`, override line fields only:
   - `toneVariants[tone].primaryLine` replaces `primaryLine`
   - `toneVariants[tone].backupLine` replaces `backupLine` (if provided)
   - All other fields unchanged
4. **If delivery modifier exists** (`state.deliveryModifier`), adjust presentation only:
   - Move type pill shows `moveType · deliveryModifier`
   - No line content changes
5. **If PRICING interrupt active**, use `playbook.stages.PRICING` as the active card entirely. `previousStage` is preserved in state for return routing.

This means: stage card is the base, objection overlays content, tone adjusts delivery, modifier adjusts framing. No split-brain.

---

## 17. NOW Summary Generation

### Source
`nowSummary` is generated by a rules-based template system in the reducer, NOT by the LLM.

### Inputs
- Current stage
- Latest classification result (primary intent, secondary intent, tone)
- Whether the classification source is rules, LLM, or manual

### Template Patterns (one sentence max, ~60 chars)
```
"Prospect [verb] [object]."
```

Examples by classification:
- `engaged_answer` → "Prospect described their call workflow."
- `existing_solution` → "Prospect claims existing staff coverage."
- `pricing_question` → "Prospect asked about pricing."
- `pricing_resistance` → "Prospect pushed back on cost."
- `brush_off` → "Prospect is trying to end the call."
- `confusion` → "Prospect asked what this is about."
- `curiosity` → "Prospect sounds curious."
- `time_pressure` → "Prospect sounds rushed."
- `authority_mismatch` → "Prospect says they're not the decision-maker."
- `pain_reveal` → "Prospect admitted missed calls are a problem."

### Tone inclusion
If tone is non-neutral and confidence is medium+, append tone context:
- "Prospect claims existing coverage. Sounds guarded."
- "Prospect asked about pricing. Sounds curious."

### Constraints
- Max 1 sentence
- No classifier jargon (no "bridge angle: missed_calls")
- No confidence numbers visible to rep
- Falls back to stage-based default if no classification: "Waiting for prospect response."

---

## 18. PRICING Interrupt Guardrails

### State management
```javascript
// On PRICING entry:
if (state.previousStage === null) {
  state.previousStage = state.stage
}
state.stage = 'PRICING'

// On RETURN_FROM_PRICING:
state.stage = state.previousStage || 'QUALIFIER'  // safe fallback
state.previousStage = null
```

### Rules
- `previousStage` is only set on first PRICING entry (if currently null)
- `RETURN_FROM_PRICING` always clears `previousStage` after restore
- Nested interrupts disallowed in v1: if already in PRICING, a second pricing signal is ignored
- If `previousStage` was a branch stage itself (e.g., OBJECTION), return there — do not skip to a "safe" stage
- Manual stage override (`MANUAL_SET_STAGE`) also clears `previousStage`

---

## 19. OBJECTION vs Dedicated Stage Boundaries

### Clear rule
- **`OBJECTION`** = generic resistance state for the 4 core buckets: timing, interest, info, authority
- **`PRICING`** = dedicated interrupt branch — NOT an objection. Pricing signals route to the PRICING stage, not into OBJECTION with a pricing subtype.
- **`WRONG_PERSON`** = dedicated branch stage — NOT an objection. Authority mismatch routes here, not to OBJECTION with authority bucket.
- **`MINI_PITCH`** = dedicated clarification stage — confusion/identity signals route here, not into OBJECTION.

### Intent → Stage routing
| Detected Intent | Routes To |
|---|---|
| timing | OBJECTION (timing bucket) |
| interest | OBJECTION (interest bucket) |
| info | OBJECTION (info bucket) |
| authority (generic resistance) | OBJECTION (authority bucket) |
| authority_mismatch (wrong person) | WRONG_PERSON stage |
| pricing_question | PRICING stage |
| pricing_resistance | PRICING stage |
| confusion | MINI_PITCH stage |
| existing_coverage | OBJECTION (with existing_coverage card overlay) |
| answering_service | OBJECTION (with answering_service card overlay) |

### Disambiguation
- "not my decision" + resistance tone → OBJECTION (authority bucket)
- "I don't handle that, talk to my wife" + referral language → WRONG_PERSON stage
- "how much is it?" → PRICING stage (not OBJECTION)
- "sounds expensive" in OBJECTION stage → stays in OBJECTION, pricing_resistance logged as secondary intent

---

## 20. Tone Stability (Hysteresis)

### Rules
- Tone only changes if the new label's confidence exceeds the current label's confidence by ≥0.15 threshold
- OR the same new label persists across 2 consecutive turns
- **Exception**: strong interruptive signals (`annoyed`, `rushed`) can override immediately if confidence ≥0.7
- Tone never changes more than once per turn

### Effect
This prevents the HUD from flickering between `neutral` and `guarded` on minor signal variations. The rep sees a calm, stable tone indicator.

---

## 21. Migration Adapter Layer

### Strategy
Do NOT refactor all files in one pass. Use an adapter to normalize the old playbook format into the new card schema incrementally.

### `normalizeCard(stage, playbook)` function
- Input: stage name + old-format playbook
- Output: a complete card object in the new schema
- Fills missing fields with sensible defaults:
  - `backupLine`: null (rendered as empty)
  - `listenFor`: [] (section hidden)
  - `branchPreview`: {} (section hidden)
  - `toneVariants`: {} (no tone adjustment)
  - `clarifyingQuestion`: null
  - `valueProp`: null
  - `proofPoint`: null
  - `moveType`: inferred from stage (OPENER→'ask', CLOSE→'close', EXIT→'exit', etc.)
  - `goal`: inferred from stage name
  - `why`: existing `now.why` value if available

### Migration order
1. Ship `normalizeCard()` adapter first — all existing playbook content works through the adapter
2. Gradually replace normalized stages with full card definitions
3. Remove adapter once all stages are native cards

---

## 22. Build Sequence

Ordered to reduce risk and deliver usable value early:

| Step | What | Files | Value |
|---|---|---|---|
| 1 | Normalize playbook into card schema + adapter | `playbook.js` | Foundation for all other changes |
| 2 | Center panel: stage + move type + primary/backup + WHY | `ui.js`, `index.html`, `reducer.js` | Backup lines and move types visible |
| 3 | Center panel: NOW + listen-for + next + pause strip | `ui.js`, `index.html`, `reducer.js` | Full center stack complete |
| 4 | Left rail: prospect context | `ui.js`, `index.html` | Context rail replaces lines panel |
| 5 | Right rail: tactical support card | `ui.js`, `index.html` | Support rail replaces objections list |
| 6 | New stages + stage-aware routing | `reducer.js`, `classifier.js`, `playbook.js` | MINI_PITCH, WRONG_PERSON, PRICING, PERMISSION_MOMENT |
| 7 | Compound objection result shape | `classifier.js`, `reducer.js` | Multi-label detection live |
| 8 | Rules-based tone layer | `classifier.js`, `reducer.js`, `playbook.js` | Tone-adjusted lines |
| 9 | LLM fallback extension (tone + secondary intent) | `llm.js`, `reducer.js` | LLM refines tone + compound |
| 10 | Audit trail enrichment | `session.js` | Richer logging |

Each step is independently shippable and testable.

---

## 23. Confidence-Adjusted UI Behavior

Classification confidence affects what the center and right rails display:

| Confidence | Center Panel | Right Rail |
|---|---|---|
| **High** (≥0.8) | Full stack: NOW, primary, ALT, listen-for (3-4), next (2-3) | Full card: ASK, REBUTTAL, VALUE, PROOF, IF/THEN |
| **Medium** (≥0.6) | Full stack: NOW, primary, ALT, listen-for (2-3), next (2) | Partial card: ASK, REBUTTAL, VALUE. Hide PROOF and IF/THEN. |
| **Low** (<0.6) | Reduced: NOW shows "Unclear response — clarify.", primary line becomes a clarifying question, ALT hidden, listen-for (1-2), next (1 route) | Minimal: ASK only. Everything else hidden. |

This ensures the HUD does not project false precision when the classifier is uncertain. Low confidence biases toward clarifying behavior rather than assertive recommendations.

---

## 24. Close Variants (Scoped)

### In scope for v2
- **Soft close** (meeting): "Worth 15 minutes? Thursday or Friday?"
- **Hedge close**: "Thursday at 2 — 15 minutes. If it's not useful, I'll leave you alone."
- **Seed exit**: "If that ever changes, worth a 15-minute conversation."
- **Info close** (via OBJECTION info bucket): email collection + follow-up question

### Deferred to v3
- Callback close (schedule future call with right person)
- Right-person transfer close
- Low-friction diagnostic close ("let me send you a 2-minute audit")
- Referral close

The existing CLOSE, SEED_EXIT, and BOOKED stages handle the in-scope variants. Deferred variants will become additional close-path cards when needed.

---

## 25. Testing Checklist

Each build step should pass these acceptance tests before moving to the next:

### Step 1: Card Schema + Adapter
- [ ] `normalizeCard()` returns valid card for every existing stage
- [ ] Normalized cards have all required fields (even if null/empty)
- [ ] Old playbook consumers (`resolveBridgeLine`, `lineForStage`, `linesForStage`) still work through adapter
- [ ] Card schema matches Section 4 shape exactly

### Step 2: Center Panel (stage + move type + lines)
- [ ] Stage pill shows current stage name
- [ ] Move type pill renders next to stage (e.g., `BRIDGE ▸ probe`)
- [ ] Delivery modifier appends correctly (e.g., `ask · compress`)
- [ ] Primary line renders large and readable
- [ ] Backup line renders smaller, secondary
- [ ] WHY shows strategic text, no classifier jargon

### Step 3: Center Panel (NOW + listen-for + next + pause)
- [ ] NOW summary is one line, plain English, updates on classification
- [ ] NOW falls back to "Waiting for prospect response." when no classification
- [ ] Listen-for shows 3-4 items max
- [ ] Branch preview shows 2-3 routes max
- [ ] Pause strip goes bright on stage transition
- [ ] Pause strip dims on next `TRANSCRIPT_FINAL` event
- [ ] Pause strip dims after 5s fallback if no speech event
- [ ] Extended silence nudge appears after 8s

### Step 4: Left Rail
- [ ] Renders prospect context when `prospectContext` provided in CALL_STARTED
- [ ] Hides sections with missing fields (no empty placeholders)
- [ ] Dims heuristic/inferred fields
- [ ] Falls back to name-only when `prospectContext` is null

### Step 5: Right Rail
- [ ] Shows single tactical card, not list
- [ ] Order: ASK → REBUTTAL → VALUE → PROOF → IF/THEN
- [ ] IF/THEN capped at 2-3 items
- [ ] Empty modules hidden, not filled with generic copy
- [ ] Falls back to fewer modules rather than generic sludge

### Step 6: New Stages
- [ ] PERMISSION_MOMENT reachable from OPENER
- [ ] MINI_PITCH triggers on "what is this" variants
- [ ] WRONG_PERSON triggers on authority mismatch + referral language
- [ ] PRICING interrupt saves `previousStage` and restores on return
- [ ] Nested PRICING interrupts are ignored
- [ ] Stage-aware routing: same keyword weighted differently by current stage

### Step 7: Compound Objections
- [ ] Classifier returns primary + secondary intent
- [ ] Secondary is null when only one signal detected
- [ ] Risk calculated from content + trajectory, not just count
- [ ] `call_ending` requires explicit exit signals, not just 3+ objections
- [ ] Priority order: authority > timing > pricing > info > interest
- [ ] `recommendedActionBias` populated on compound results

### Step 8: Tone Layer
- [ ] Rules assign tone on every utterance
- [ ] 6 labels + unknown only
- [ ] Tone variants override primary line when available
- [ ] Tone hysteresis: no change unless ≥0.15 confidence delta or 2-turn persistence
- [ ] `annoyed`/`rushed` can override immediately at ≥0.7 confidence

### Step 9: LLM Extension
- [ ] Groq request includes `requestTone` and `requestSecondaryIntent`
- [ ] LLM tone overrides rules tone only when confidence delta > 0.15
- [ ] LLM secondary intent populates compound result
- [ ] No separate LLM call for tone

### Step 10: Audit Trail
- [ ] Session log includes tone, risk, compound, signalCount, moveType, deliveryModifier
- [ ] Existing `/hud/session-log` POST still works with enriched payload
- [ ] No new API endpoints needed

---

## 26. Unified Intent Taxonomy

All system components (classifier, reducer, nowSummary, UI, session log) MUST use the same intent labels. This is the canonical list:

### Primary Intent Labels
| Label | Meaning | Used In |
|---|---|---|
| `engaged_answer` | Prospect answered the question substantively | classifier, nowSummary, reducer |
| `existing_coverage` | Claims staff/receptionist/service | classifier, objection overlay, nowSummary |
| `answering_service` | Claims answering service specifically | classifier, objection overlay |
| `pricing_question` | Asks "how much" | classifier, PRICING stage routing |
| `pricing_resistance` | Says "too expensive" / "can't afford" | classifier, PRICING stage routing |
| `timing` | "I'm busy" / "bad time" / "on a job" | classifier, OBJECTION bucket |
| `interest` | "Not interested" / "we're set" | classifier, OBJECTION bucket |
| `info` | "Send me info" / "email me" | classifier, OBJECTION bucket |
| `authority` | "Not my decision" (generic resistance) | classifier, OBJECTION bucket |
| `authority_mismatch` | "Talk to my wife/partner" (wrong person) | classifier, WRONG_PERSON routing |
| `confusion` | "What is this?" / "Who are you?" | classifier, MINI_PITCH routing |
| `curiosity` | Follow-up question showing interest | classifier, nowSummary |
| `pain_reveal` | Admits missed calls / leakage problem | classifier, nowSummary |
| `brush_off` | "Not interested" + polite exit attempt | classifier, nowSummary |
| `time_pressure` | Short/rushed response, impatient signals | classifier, nowSummary, tone input |
| `hedge` | "Maybe" / "let me think" / "not sure" | classifier |
| `yes` | Agreement / permission granted | classifier |

### Mapping: nowSummary templates use intent labels directly
```javascript
const NOW_TEMPLATES = {
  engaged_answer:    "Prospect described their call workflow.",
  existing_coverage: "Prospect claims existing staff coverage.",
  answering_service: "Prospect mentions an answering service.",
  pricing_question:  "Prospect asked about pricing.",
  pricing_resistance:"Prospect pushed back on cost.",
  timing:            "Prospect says it's a bad time.",
  interest:          "Prospect says not interested.",
  info:              "Prospect asked for info by email.",
  authority:         "Prospect says it's not their decision.",
  authority_mismatch:"Prospect says they're not the decision-maker.",
  confusion:         "Prospect asked what this is about.",
  curiosity:         "Prospect sounds curious.",
  pain_reveal:       "Prospect admitted missed calls are a problem.",
  brush_off:         "Prospect is trying to end the call.",
  time_pressure:     "Prospect sounds rushed.",
  hedge:             "Prospect is on the fence.",
  yes:               "Prospect gave permission to continue.",
}
```

No aliases, no synonyms. One label, one meaning, everywhere.

---

## 27. Turn Lifecycle

A "turn" is one complete cycle from prospect utterance to HUD update. Every turn follows this exact sequence:

```
TRANSCRIPT_FINAL received (prospect utterance)
  │
  ├─ 1. Classify utterance
  │    └─ classifyUtterance(utterance, { stage }) → classification result
  │
  ├─ 2. Assign tone (rules-based)
  │    └─ assignTone(utterance, classification, stage) → tone result
  │    └─ Apply hysteresis check (Section 20)
  │    └─ Update state.tone only if hysteresis passes
  │
  ├─ 3. Compute compound result (if in OBJECTION-eligible stage)
  │    └─ primary + secondary intent, risk, signalCount, actionBias
  │    └─ Update trajectory state (Section 28)
  │
  ├─ 4. Determine stage transition
  │    └─ Apply stage-aware routing (Section 5)
  │    └─ Check manual override suppression window (4s)
  │    └─ If transition: update state.stage, state.moveType, state.deliveryModifier
  │
  ├─ 5. Generate nowSummary
  │    └─ Template lookup from classification intent label (Section 17/26)
  │    └─ Append tone context if non-neutral + medium+ confidence
  │
  ├─ 6. Compose activeCard
  │    └─ Follow precedence: stage → objection overlay → tone variant → modifier (Section 16)
  │
  ├─ 7. Render UI
  │    └─ Update center panel, right rail, pause strip
  │    └─ Left rail unchanged (stable context)
  │
  └─ 8. Log decision
       └─ session.logDecision(action, prevState, newState)
```

### Timing constraints
- Steps 1-6 MUST complete synchronously (no async in the render path)
- Step 7 fires exactly once per turn (no intermediate flickers)
- If LLM fallback triggers (low confidence at step 1), steps 2-7 run immediately with rules result. When LLM returns later, steps 2-7 re-run as a second micro-turn with `LLM_RESULT` action.
- Manual override (`MANUAL_SET_STAGE`, hotkeys) creates a synthetic turn that skips steps 1-3 and enters at step 4.

### UI stability rule
The UI updates exactly once per turn completion. No partial renders between steps 1-6. This prevents flicker.

---

## 28. Manual Override / Pin Semantics

### Core rule
When the rep manually selects a stage, objection, or bridge angle via hotkey, the HUD pins to that selection and suppresses auto-classification for a defined window.

### Pin behavior
| Action | Pin Duration | What's Pinned | What Clears It |
|---|---|---|---|
| `MANUAL_SET_STAGE` (F7/→/←/F10) | 4 seconds | stage, activeCard | Timer expiry, or next manual action |
| `MANUAL_SET_BRIDGE_ANGLE` (1-3 in BRIDGE) | 4 seconds | bridgeAngle, activeCard lines | Timer expiry, or next manual action |
| `MANUAL_SET_OBJECTION` (1-4 in CLOSE/OBJECTION) | 4 seconds | objectionBucket, activeCard overlay | Timer expiry, or next manual action |
| `LINE_BANK_SELECT` | No pin | Records selection in round history | Immediately (informational only) |

### During pin window
- `TRANSCRIPT_FINAL` events are still logged to transcript and audit trail
- Classification still runs (for logging and LLM fallback tracking)
- But classification results DO NOT trigger stage transitions or card recomposition
- The UI stays on the manually selected card
- `autoClassifySuppressedUntilMs` field (already exists in reducer) controls this

### After pin expires
- Next `TRANSCRIPT_FINAL` event resumes normal turn lifecycle
- If a high-confidence classification fired during the pin window, it is evaluated fresh (not replayed from cache)

### Pin + PRICING interaction
- Manual stage override clears `previousStage` (prevents stale return routing)
- If rep manually exits PRICING, no auto-return happens

### Trust principle
The rep's manual selection ALWAYS wins over AI classification for the pin duration. The HUD must never yank the rep off a manually selected card mid-thought. This is non-negotiable for live trust.

---

## 29. Global Routing Precedence (Cross-Family)

When a single utterance triggers signals from multiple families (dedicated stages + objection buckets + confusion + pricing), resolve with this priority:

### Priority order (highest wins)
1. **Exit signals** — explicit "gotta go", "don't call back", hostile rejection → EXIT
2. **Authority mismatch** — "talk to my wife", "wrong person" → WRONG_PERSON
3. **Confusion** — "what is this?", "who are you?" → MINI_PITCH
4. **Pricing** — "how much?", "too expensive" → PRICING interrupt
5. **Objection buckets** — timing > authority > info > interest → OBJECTION
6. **Engaged signals** — workflow answer, curiosity, pain reveal → stay in current stage or advance

### Mixed-moment examples
| Utterance | Signals | Resolution |
|---|---|---|
| "What is this, and how much is it?" | confusion + pricing_question | MINI_PITCH first (answer what this is before pricing makes sense) |
| "I'm not the right person, just send me info" | authority_mismatch + info | WRONG_PERSON (can't sell to wrong person; info is secondary) |
| "We already have someone, and I'm busy" | existing_coverage + timing | OBJECTION with existing_coverage overlay (primary), timing as secondary intent |
| "Sounds expensive, not interested" | pricing_resistance + interest | PRICING stage (pricing is more conversation-shaping than generic disinterest) |
| "Yeah, we do lose some calls after hours" | pain_reveal + engaged_answer | Stay in current stage, advance to next (positive signals don't re-route) |

### Rule
Primary intent from the classifier drives routing. Global precedence only overrides when two signals from different families conflict. Within the same family (e.g., two objection buckets), use the objection priority order from Section 6.

---

## 30. Trajectory State for Risk Computation

Risk assessment requires memory of what happened earlier in the call. These fields track trajectory:

### New state fields
```javascript
{
  // existing fields...

  // Trajectory state for risk:
  salvageAttemptCount: 0,       // how many times we tried to recover after objection
  consecutiveSameIntent: 0,     // count of repeated same primary intent
  lastPrimaryIntent: null,      // previous turn's primary intent
  rescueMoveFailed: false,      // true if last move was rescue/salvage and prospect rejected again
  prospectQuestionCount: 0,     // how many questions prospect has asked (engagement signal)
  turnsInCurrentStage: 0,       // how long we've been in this stage
}
```

### Update rules (in turn lifecycle step 3)
- `salvageAttemptCount` increments when stage is OBJECTION and we transition back from a rescue line
- `consecutiveSameIntent` increments when `primary.intent === lastPrimaryIntent`; resets to 1 on different intent
- `rescueMoveFailed` = true when previous turn was in OBJECTION + salvage line, and current turn detects same or escalated objection
- `prospectQuestionCount` increments when classification detects `curiosity` or `confusion`
- `turnsInCurrentStage` increments each turn; resets to 0 on stage change

### Risk computation
```javascript
function computeRisk(state, classification) {
  if (isExplicitExitLanguage(classification)) return 'call_ending'
  if (state.rescueMoveFailed && classification.primary.intent === state.lastPrimaryIntent) return 'call_ending'
  if (state.consecutiveSameIntent >= 3) return 'call_ending'
  if (classification.compound) return 'high'
  if (state.salvageAttemptCount >= 2) return 'high'
  if (state.consecutiveSameIntent >= 2) return 'medium'
  return 'low'
}
```

This makes "trajectory-aware risk" computable, not aspirational.

---

## 31. Confidence Source for UI Behavior

Section 23's confidence-adjusted UI uses **primary intent confidence** as the source of truth.

### Rule
```javascript
const uiConfidence = classification.primary.score >= 0.8 ? 'high'
                   : classification.primary.score >= 0.6 ? 'medium'
                   : 'low'
```

### Why primary intent confidence
- It is the signal that drives routing and card selection
- It is always present (unlike secondary or tone)
- It is what the rep is trusting when they follow the recommended line

### Edge case
- If classification source is `manual` (hotkey override), treat as `high` confidence always — the rep made the decision, show full stack
- If classification source is `llm`, use the LLM's returned confidence score
- If no classification has occurred yet (call just started), treat as `low` — show minimal stack with "Waiting for prospect response."

---

## 32. Transcript Degradation Fallback

When transcript quality drops, the HUD must degrade safely rather than project false precision.

### Failure modes and responses

| Condition | Detection | HUD Response |
|---|---|---|
| **Transcript lag** (>3s since last expected event) | Timer since last `TRANSCRIPT_FINAL` | Show amber indicator next to confidence badge. Keep last known card stable. Do not update NOW summary. |
| **Missing TRANSCRIPT_FINAL** (interim received but no final) | Interim without matching final within 5s | Treat as no-event. Do not classify. Keep current card. |
| **Duplicate transcript fragments** | Same `utteranceId` received twice | Ignore second instance. Already guarded by `latestTranscriptSeq` check. |
| **LLM fallback latency** (>4s response) | Timer on LLM request | Proceed with rules-only classification. If LLM responds later, apply as micro-turn only if still relevant (seq check). |
| **Complete transcript failure** (no events for >15s during connected call) | Timer since last any transcript event | Show red "TRANSCRIPT OFFLINE" badge. Lock HUD to manual-only mode. Hide NOW summary. Keep current card visible but dim. |

### Principle
When data quality is uncertain, show less rather than guess more. The rep should see that the system is uncertain, not receive confidently wrong guidance.
