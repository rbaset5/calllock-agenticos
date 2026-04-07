// dialer/hud/taxonomy.js — Unified intent taxonomy constants (v2 spec Section 26)
// Single source of truth for all intent labels, tone labels, risk levels,
// move types, and NOW summary templates.

// -------------------------
// 17 canonical intent labels
// -------------------------

export const INTENTS = [
  "engaged_answer",
  "existing_coverage",
  "answering_service",
  "pricing_question",
  "pricing_resistance",
  "timing",
  "interest",
  "info",
  "authority",
  "authority_mismatch",
  "confusion",
  "curiosity",
  "pain_reveal",
  "brush_off",
  "time_pressure",
  "hedge",
  "yes",
];

// -------------------------
// 7 tone labels
// -------------------------

export const TONES = [
  "rushed",
  "skeptical",
  "annoyed",
  "curious",
  "guarded",
  "neutral",
  "unknown",
];

// -------------------------
// 4 risk levels (ordered low → call_ending)
// -------------------------

export const RISK_LEVELS = ["low", "medium", "high", "call_ending"];

// -------------------------
// 9 core move types
// -------------------------

export const MOVE_TYPES = [
  "ask",
  "clarify",
  "probe",
  "reframe",
  "bridge",
  "quantify",
  "close",
  "exit",
  "pause",
];

// -------------------------
// 5 delivery modifiers
// -------------------------

export const DELIVERY_MODIFIERS = [
  "compress",
  "soften",
  "hold",
  "escalate",
  "redirect",
];

// -------------------------
// NOW panel summary templates (one per intent, each < 80 chars)
// -------------------------

export const NOW_TEMPLATES = {
  engaged_answer: "Prospect described their call workflow.",
  existing_coverage: "Prospect claims existing staff coverage.",
  answering_service: "Prospect mentions an answering service.",
  pricing_question: "Prospect asked about pricing.",
  pricing_resistance: "Prospect pushed back on cost.",
  timing: "Prospect says it's a bad time.",
  interest: "Prospect says not interested.",
  info: "Prospect asked for info by email.",
  authority: "Prospect says it's not their decision.",
  authority_mismatch: "Prospect says they're not the decision-maker.",
  confusion: "Prospect asked what this is about.",
  curiosity: "Prospect sounds curious.",
  pain_reveal: "Prospect admitted missed calls are a problem.",
  brush_off: "Prospect is trying to end the call.",
  time_pressure: "Prospect sounds rushed.",
  hedge: "Prospect is on the fence.",
  yes: "Prospect gave permission to continue.",
  // Bridge angle keys (from classifier bridgeAngle field)
  missed_calls: "Prospect mentioned missed calls or voicemail.",
  competition: "Prospect mentioned competitive pressure.",
  overwhelmed: "Prospect sounds overwhelmed or stretched thin.",
  fallback: "Prospect responded — listening for pain signal.",
  // Qualifier reads
  pain: "Prospect confirmed they're losing calls.",
  no_pain: "Prospect says they don't miss calls.",
  unknown_pain: "Prospect isn't sure how many calls they miss.",
};

// -------------------------
// Routing precedence (cross-family conflict resolution order)
// -------------------------

export const ROUTING_PRECEDENCE = [
  "engaged_answer",
  "curiosity",
  "pain_reveal",
  "hedge",
  "yes",
  "interest",
  "info",
  "timing",
  "authority",
  "existing_coverage",
  "answering_service",
  "pricing_question",
  "pricing_resistance",
  "confusion",
  "authority_mismatch",
  "brush_off",
  "time_pressure",
];

// -------------------------
// Intent → stage overrides
// -------------------------

export const INTENT_STAGE_MAP = {
  pricing_question: "PRICING",
  pricing_resistance: "PRICING",
  authority_mismatch: "WRONG_PERSON",
  confusion: "MINI_PITCH",
  time_pressure: "MINI_PITCH",
  brush_off: "EXIT",
};

// -------------------------
// Intent families
// -------------------------

export const OBJECTION_INTENTS = ["timing", "interest", "info", "authority"];

export const OVERLAY_INTENTS = ["existing_coverage", "answering_service"];

// -------------------------
// Bridge stages (stages that show bridge angle hotkeys)
// -------------------------

export const BRIDGE_STAGES = ["BRIDGE", "OPENER"];

// -------------------------
// Hotkey config — single source of truth for legend, handler, telemetry, replay.
// Each stage maps to an array of available hotkey actions.
// -------------------------

export const HOTKEY_CONFIG = {
  // Stages with bridge angle keys (1-3)
  BRIDGE: [
    { key: "1", label: "Missed", action: "MANUAL_SET_BRIDGE_ANGLE", value: "missed_calls", type: "bridge", cues: "voicemail, callback, wife, office" },
    { key: "2", label: "Comp", action: "MANUAL_SET_BRIDGE_ANGLE", value: "competition", type: "bridge", cues: "slow, growth, competitor, losing" },
    { key: "3", label: "Overwhelm", action: "MANUAL_SET_BRIDGE_ANGLE", value: "overwhelmed", type: "bridge", cues: "busy, stretched, do it all, rushed" },
  ],
  OPENER: [
    { key: "1", label: "Missed", action: "MANUAL_SET_BRIDGE_ANGLE", value: "missed_calls", type: "bridge", cues: "voicemail, callback, wife, office" },
    { key: "2", label: "Comp", action: "MANUAL_SET_BRIDGE_ANGLE", value: "competition", type: "bridge", cues: "slow, growth, competitor, losing" },
    { key: "3", label: "Overwhelm", action: "MANUAL_SET_BRIDGE_ANGLE", value: "overwhelmed", type: "bridge", cues: "busy, stretched, do it all, rushed" },
  ],
  // Stages with objection keys (1-4)
  CLOSE: [
    { key: "1", label: "Timing", action: "MANUAL_SET_OBJECTION", value: "timing", type: "objection", cues: "busy, bad time, not now, call back" },
    { key: "2", label: "Interest", action: "MANUAL_SET_OBJECTION", value: "interest", type: "objection", cues: "not interested, we're set, don't need" },
    { key: "3", label: "Info", action: "MANUAL_SET_OBJECTION", value: "info", type: "objection", cues: "send me info, email me, website" },
    { key: "4", label: "Authority", action: "MANUAL_SET_OBJECTION", value: "authority", type: "objection", cues: "not my decision, wife handles, partner" },
  ],
  OBJECTION: [
    { key: "1", label: "Timing", action: "MANUAL_SET_OBJECTION", value: "timing", type: "objection", cues: "busy, bad time, not now, call back" },
    { key: "2", label: "Interest", action: "MANUAL_SET_OBJECTION", value: "interest", type: "objection", cues: "not interested, we're set, don't need" },
    { key: "3", label: "Info", action: "MANUAL_SET_OBJECTION", value: "info", type: "objection", cues: "send me info, email me, website" },
    { key: "4", label: "Authority", action: "MANUAL_SET_OBJECTION", value: "authority", type: "objection", cues: "not my decision, wife handles, partner" },
  ],
  GATEKEEPER: [
    { key: "1", label: "Timing", action: "MANUAL_SET_OBJECTION", value: "timing", type: "objection", cues: "busy, bad time, not now" },
    { key: "2", label: "Interest", action: "MANUAL_SET_OBJECTION", value: "interest", type: "objection", cues: "not interested" },
    { key: "3", label: "Info", action: "MANUAL_SET_OBJECTION", value: "info", type: "objection", cues: "send info, email" },
    { key: "4", label: "Authority", action: "MANUAL_SET_OBJECTION", value: "authority", type: "objection", cues: "not my decision" },
  ],
  QUALIFIER: [
    { key: "1", label: "Timing", action: "MANUAL_SET_OBJECTION", value: "timing", type: "objection", cues: "busy, bad time" },
    { key: "2", label: "Interest", action: "MANUAL_SET_OBJECTION", value: "interest", type: "objection", cues: "not interested" },
    { key: "3", label: "Info", action: "MANUAL_SET_OBJECTION", value: "info", type: "objection", cues: "send info" },
    { key: "4", label: "Authority", action: "MANUAL_SET_OBJECTION", value: "authority", type: "objection", cues: "not my decision" },
  ],
  SEED_EXIT: [
    { key: "1", label: "Timing", action: "MANUAL_SET_OBJECTION", value: "timing", type: "objection", cues: "busy, bad time" },
    { key: "2", label: "Interest", action: "MANUAL_SET_OBJECTION", value: "interest", type: "objection", cues: "not interested" },
    { key: "3", label: "Info", action: "MANUAL_SET_OBJECTION", value: "info", type: "objection", cues: "send info" },
    { key: "4", label: "Authority", action: "MANUAL_SET_OBJECTION", value: "authority", type: "objection", cues: "not my decision" },
  ],
  // Blocked stages — no numeric keys
  PRICING: [],
  MINI_PITCH: [],
  WRONG_PERSON: [],
  PERMISSION_MOMENT: [],
  // Terminal/idle stages — no numeric keys
  IDLE: [],
  EXIT: [],
  ENDED: [],
  BOOKED: [],
  NON_CONNECT: [],
};

// -------------------------
// Global hotkeys (always available, not stage-dependent)
// -------------------------

export const GLOBAL_HOTKEYS = [
  { key: "\u2192", label: "Next", description: "Advance stage" },
  { key: "\u2190", label: "Back", description: "Previous round/stage" },
  { key: "F9", label: "No-connect", description: "Mark non-connect" },
  { key: "F10", label: "Branch", description: "Alternate path" },
  { key: "Space", label: "Off-script", description: "Bookmark custom response" },
  { key: "Shift", label: "Hedge", description: "Request hedge (CLOSE/OBJ)" },
  { key: "Shift+F1", label: "End", description: "End call + reset" },
  { key: "?", label: "Legend", description: "Toggle hotkey bar" },
  { key: "`", label: "FAQ", description: "Jump to quick answers" },
];

// Bridge angle hotkeys (shown at BRIDGE/OPENER stages, keys 1-4 do these instead of objections)
export const BRIDGE_HOTKEYS = [
  { key: "1", label: "Missed calls", description: "Missed calls bridge angle" },
  { key: "2", label: "Competition", description: "Competition bridge angle" },
  { key: "3", label: "Overwhelmed", description: "Overwhelmed bridge angle" },
  { key: "4", label: "Ad spend", description: "Ad spend bridge angle" },
];

// Objection hotkeys (rendered in their own bar above the nav legend)
export const OBJECTION_HOTKEYS = [
  { key: "0", label: "Pricing", description: "Jump to pricing stage" },
  { key: "1", label: "Timing", description: "Timing objection reset" },
  { key: "2", label: "Interest", description: "Interest objection reset" },
  { key: "3", label: "Info", description: "Send info objection reset" },
  { key: "4", label: "Authority", description: "Authority objection reset" },
  { key: "5", label: "Coverage", description: "Existing coverage objection" },
  { key: "6", label: "Ans. Svc", description: "Answering service objection" },
];

// -------------------------
// Keypress event schema for telemetry (session audit trail)
// -------------------------

export const KEYPRESS_EVENT_FIELDS = [
  "ts",
  "stage",
  "key",
  "action",
  "value",
  "isOverride",
  "source",
];
