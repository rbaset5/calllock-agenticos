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
  tried_ai: "Prospect says they tried AI before.",
  referral_only: "Prospect says all business is referrals.",
  competitor_comparison: "Prospect asks how this is different from a competitor.",
  missed_calls: "Bridge: discussing missed calls.",
  competition: "Bridge: discussing competitor speed.",
  overwhelmed: "Bridge: discussing owner being stretched.",
  ad_spend: "Bridge: discussing wasted ad spend.",
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

export const OBJECTION_INTENTS = ["timing", "interest", "info", "authority", "existing_coverage", "answering_service"];

export const OVERLAY_INTENTS = [];
