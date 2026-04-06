// dialer/hud/cards.js
// Card schema and normalizeCard adapter — bridges old playbook format to v2 card schema.
// Vanilla JS ES module — no build step, no TypeScript.
// Spec: v2 Sections 4, 21.

import { lineForStage } from './playbook.js';

// ── Card field schema ───────────────────────────────────────────

export const CARD_FIELDS = [
  'id',
  'stage',
  'moveType',
  'deliveryModifier',
  'goal',
  'primaryLine',
  'backupLine',
  'why',
  'listenFor',
  'branchPreview',
  'clarifyingQuestion',
  'valueProp',
  'proofPoint',
  'toneVariants',
];

// ── Stage → move-type mapping ───────────────────────────────────

export const STAGE_MOVE_MAP = {
  IDLE: 'pause',
  OPENER: 'ask',
  PERMISSION_MOMENT: 'ask',
  MINI_PITCH: 'clarify',
  GATEKEEPER: 'ask',
  WRONG_PERSON: 'clarify',
  BRIDGE: 'bridge',
  QUALIFIER: 'ask',
  PRICING: 'reframe',
  CLOSE: 'close',
  SEED_EXIT: 'exit',
  OBJECTION: 'reframe',
  BOOKED: 'close',
  EXIT: 'exit',
  NON_CONNECT: 'pause',
  ENDED: 'pause',
};

// ── Stage → goal mapping ────────────────────────────────────────

export const STAGE_GOAL_MAP = {
  IDLE: 'Wait for call to begin',
  OPENER: 'Land the opening question',
  PERMISSION_MOMENT: 'Earn permission to continue',
  MINI_PITCH: 'Deliver concise value statement',
  GATEKEEPER: 'Get past the gatekeeper',
  WRONG_PERSON: 'Redirect to the right contact',
  BRIDGE: 'Bridge to pain or need',
  QUALIFIER: 'Quantify the pain',
  PRICING: 'Reframe the price conversation',
  CLOSE: 'Book the meeting',
  SEED_EXIT: 'Plant a seed for future follow-up',
  OBJECTION: 'Handle the objection and reset',
  BOOKED: 'Confirm the appointment',
  EXIT: 'End the call gracefully',
  NON_CONNECT: 'Leave voicemail or text',
  ENDED: 'Call complete',
};

// ── Native v2 stage cards ───────────────────────────────────────

export const NATIVE_STAGE_CARDS = {
  OPENER: {
    id: 'OPENER',
    stage: 'OPENER',
    moveType: 'ask',
    deliveryModifier: '',
    goal: 'Earn enough space to ask the first real question.',
    primaryLine: "Hey {NAME}, this is Rashid over in Houston — cold call, quick question: when a call comes in while you're on a job, what happens to it?",
    backupLine: "I know I'm catching you out of the blue — this'll take 20 seconds. When a new customer calls and you can't pick up, what usually happens?",
    why: 'The opener earns the right to continue. No pitch, just a question that makes them think.',
    listenFor: ['permission', 'impatience', 'what is this about', 'instant rejection'],
    branchPreview: {
      engaged: { next: 'PERMISSION_MOMENT' },
      confused: { next: 'MINI_PITCH' },
      pushback: { next: 'OBJECTION' },
    },
    clarifyingQuestion: '',
    valueProp: '',
    proofPoint: '',
    toneVariants: {
      rushed: { primaryLine: "Quick question — when a call comes in and you can't pick up, what happens?" },
      annoyed: { primaryLine: "I know, cold call. One question and I'm gone — when a call comes in on a job, what happens to it?" },
    },
  },

  BRIDGE: {
    id: 'BRIDGE',
    stage: 'BRIDGE',
    moveType: 'bridge',
    deliveryModifier: '',
    goal: 'Bridge to pain or need',
    primaryLine: 'What does it cost you when a call goes to voicemail on a Monday morning?',
    backupLine: "When that happens, does someone usually call them back fast, or do some just fall through?",
    why: 'The bridge makes the problem real. It shifts from hypothetical to personal.',
    listenFor: ['real workflow', 'vague answer', 'defensive answer', 'existing solution'],
    branchPreview: {
      engaged: { next: 'QUALIFIER' },
      pushback: { next: 'OBJECTION' },
      confused: { next: 'MINI_PITCH' },
    },
    clarifyingQuestion: "What tends to happen once that call isn't answered live?",
    valueProp: 'Captures jobs you already paid to generate.',
    proofPoint: 'This matters most when demand already exists and live call handling breaks.',
    toneVariants: {
      rushed: { primaryLine: "Quick one — what happens when a call hits voicemail on a busy morning?" },
      annoyed: { primaryLine: "I get it. Just curious — when a call goes to voicemail, what usually happens next?" },
      curious: { primaryLine: "I'm curious — when a call goes to voicemail on a Monday, does someone follow up or does it just disappear?" },
    },
  },

  QUALIFIER: {
    id: 'QUALIFIER',
    stage: 'QUALIFIER',
    moveType: 'ask',
    deliveryModifier: '',
    goal: 'Quantify the pain',
    primaryLine: 'How many calls a week do you think go unanswered?',
    backupLine: "Would you say that's rare, or does it happen enough to actually matter?",
    why: 'Quantifying the pain makes the problem concrete and creates urgency.',
    listenFor: ['frequency', 'emotional ownership', 'minimization', 'pain signal'],
    branchPreview: {
      engaged: { next: 'CLOSE' },
      pushback: { next: 'OBJECTION' },
      hedge: { next: 'SEED_EXIT' },
    },
    clarifyingQuestion: '',
    valueProp: '',
    proofPoint: '',
    toneVariants: {},
  },

  CLOSE: {
    id: 'CLOSE',
    stage: 'CLOSE',
    moveType: 'close',
    deliveryModifier: '',
    goal: 'Book the meeting',
    primaryLine: 'Worth 15 minutes? Thursday or Friday?',
    backupLine: "Thursday at 2 — 15 minutes. If it's not useful, I'll leave you alone.",
    why: 'A direct close with two options reduces friction and drives commitment.',
    listenFor: ['agreement', 'hedge', 'objection', 'pricing question'],
    branchPreview: {
      engaged: { next: 'BOOKED' },
      pushback: { next: 'OBJECTION' },
      hedge: { action: 'hedge_close' },
    },
    clarifyingQuestion: 'Is that something worth looking at this week?',
    valueProp: '',
    proofPoint: '',
    toneVariants: {},
  },

  OBJECTION: {
    id: 'OBJECTION',
    stage: 'OBJECTION',
    moveType: 'reframe',
    deliveryModifier: '',
    goal: 'Handle the objection and reset',
    primaryLine: "Totally fair. Quick question — when a call comes in while you're on a job, what happens to it?",
    backupLine: 'Got it. When you can\'t get to a new customer call right away, what usually happens?',
    why: 'Acknowledge the objection, then redirect back to the core question.',
    listenFor: ['engagement', 'repeated rejection', 'softening', 'exit signal'],
    branchPreview: {
      engaged: { next: 'QUALIFIER' },
      pushback: { next: 'EXIT' },
    },
    clarifyingQuestion: '',
    valueProp: '',
    proofPoint: '',
    toneVariants: {
      rushed: { primaryLine: "Fair enough — one quick thing: what happens when a call comes in on a job?" },
      annoyed: { primaryLine: "Totally hear you. Just curious — what happens to calls when you're busy?" },
    },
  },

  EXIT: {
    id: 'EXIT',
    stage: 'EXIT',
    moveType: 'exit',
    deliveryModifier: '',
    goal: 'End the call gracefully',
    primaryLine: "No worries. If you ever revisit, we're here.",
    backupLine: "Got it — appreciate you taking the call.",
    why: 'A clean exit preserves the relationship for future outreach.',
    listenFor: ['final goodbye', 'reconsideration', 'question'],
    branchPreview: {},
    clarifyingQuestion: '',
    valueProp: '',
    proofPoint: '',
    toneVariants: {},
  },

  SEED_EXIT: {
    id: 'SEED_EXIT',
    stage: 'SEED_EXIT',
    moveType: 'exit',
    deliveryModifier: 'soften',
    goal: 'Plant a seed for future follow-up',
    primaryLine: "If that ever changes, worth a 15-minute conversation. I'll send you a quick note.",
    backupLine: "No pressure at all. If things shift, we're easy to find.",
    why: 'Leave the door open without pressure so the prospect may return later.',
    listenFor: ['openness', 'final rejection', 'curiosity'],
    branchPreview: {
      engaged: { next: 'CLOSE' },
      exit: { next: 'EXIT' },
    },
    clarifyingQuestion: '',
    valueProp: '',
    proofPoint: '',
    toneVariants: {},
  },

  BOOKED: {
    id: 'BOOKED',
    stage: 'BOOKED',
    moveType: 'close',
    deliveryModifier: '',
    goal: 'Confirm the appointment',
    primaryLine: 'Perfect — invite heading your way. Talk {DAY}!',
    backupLine: "Great — you'll see the invite shortly. Looking forward to it.",
    why: 'Confirm immediately to lock in the commitment.',
    listenFor: ['confirmation', 'reschedule', 'question'],
    branchPreview: {},
    clarifyingQuestion: '',
    valueProp: '',
    proofPoint: '',
    toneVariants: {},
  },

  NON_CONNECT: {
    id: 'NON_CONNECT',
    stage: 'NON_CONNECT',
    moveType: 'pause',
    deliveryModifier: '',
    goal: 'Leave voicemail or text',
    primaryLine: "Hey {NAME}, Rashid calling from Houston — I work with contractors on what happens to their calls when they're tied up on a job. Worth a quick conversation. Call me back at {NUMBER}, or I'll try you again {DAY}.",
    backupLine: "Hey {NAME} — Rashid here. Left you a voicemail. I help {TRADE} contractors handle calls when they're on a job. Worth 2 minutes?",
    why: 'Voicemail plants a seed; the text follow-up creates a second touchpoint.',
    listenFor: ['callback', 'text reply', 'no response'],
    branchPreview: {
      callback: { next: 'OPENER' },
    },
    clarifyingQuestion: '',
    valueProp: '',
    proofPoint: '',
    toneVariants: {},
  },

  PERMISSION_MOMENT: {
    id: 'PERMISSION_MOMENT',
    stage: 'PERMISSION_MOMENT',
    moveType: 'ask',
    deliveryModifier: '',
    goal: 'Determine if there is room to continue.',
    primaryLine: 'Can I ask you a quick question about new customer calls?',
    backupLine: "This'll take 20 seconds — when a new call comes in and you can't grab it, what happens?",
    why: 'Tests whether the prospect will give you space before diving in.',
    listenFor: ['permission', 'impatience', 'confusion', 'rejection'],
    branchPreview: {
      engaged: { next: 'BRIDGE' },
      confused: { next: 'MINI_PITCH' },
      pushback: { next: 'EXIT' },
    },
    clarifyingQuestion: '',
    valueProp: '',
    proofPoint: '',
    toneVariants: {
      rushed: { primaryLine: 'Quick question — 20 seconds: when a new customer calls and nobody can grab it, what happens?' },
    },
  },

  MINI_PITCH: {
    id: 'MINI_PITCH',
    stage: 'MINI_PITCH',
    moveType: 'clarify',
    deliveryModifier: 'compress',
    goal: 'Answer "what is this?" in one sentence, return to question.',
    primaryLine: "We answer your phone and book jobs when you can't — nights, weekends, when you're on a job.",
    backupLine: "When a call comes in and you can't get to it, we pick up, find out what they need, and get them on the schedule.",
    why: 'Answers confusion without overexplaining, then returns to question mode.',
    listenFor: ['curiosity', 'skepticism', 'brush off', 'workflow answer'],
    branchPreview: {
      engaged: { next: 'BRIDGE' },
      pushback: { next: 'OBJECTION' },
    },
    clarifyingQuestion: 'How are you handling that today?',
    valueProp: '',
    proofPoint: '',
    toneVariants: {},
  },

  WRONG_PERSON: {
    id: 'WRONG_PERSON',
    stage: 'WRONG_PERSON',
    moveType: 'clarify',
    deliveryModifier: '',
    goal: 'Identify owner, get referral or transfer.',
    primaryLine: "Makes sense. What's the best way to reach the person who handles that?",
    backupLine: "No worries — is there a good time to catch the owner?",
    why: 'Gets referral intelligence without pushing on wrong person.',
    listenFor: ['referral given', 'callback offered', 'refusal', 'transfer possible'],
    branchPreview: {
      engaged: { next: 'GATEKEEPER' },
      pushback: { next: 'EXIT' },
    },
    clarifyingQuestion: "When's a good time to reach them?",
    valueProp: '',
    proofPoint: '',
    toneVariants: {},
  },

  PRICING: {
    id: 'PRICING',
    stage: 'PRICING',
    moveType: 'reframe',
    deliveryModifier: '',
    goal: 'Handle premature pricing without killing discovery.',
    primaryLine: "Happy to cover that — first I want to make sure this is even a problem worth solving on your side. When calls come in and nobody can grab them, what usually happens?",
    backupLine: "I can cover pricing. I just don't want to throw numbers at you before knowing whether there's actually a problem to solve.",
    why: 'Redirects from pricing to whether the problem is worth fixing.',
    listenFor: ['workflow answer', 'insistence on price', 'curiosity', 'hostility'],
    branchPreview: {
      engaged: { next: 'QUALIFIER' },
      pushback: { next: 'EXIT' },
    },
    clarifyingQuestion: 'How often do you think a good inbound call comes in when nobody can answer it properly?',
    valueProp: 'Captures jobs you already paid to generate.',
    proofPoint: "It's $297 a month. At your ticket size, one booked job covers that. How many are slipping through right now?",
    toneVariants: {
      annoyed: { primaryLine: "Totally — I can cover pricing. Quick thing first: when calls come in and nobody grabs them, is that a real issue?" },
    },
  },

  GATEKEEPER: {
    id: 'GATEKEEPER',
    stage: 'GATEKEEPER',
    moveType: 'ask',
    deliveryModifier: '',
    goal: 'Get past the gatekeeper',
    primaryLine: "Hey, it's Rashid — I was trying to reach {NAME} about their business calls. Is he around?",
    backupLine: "I help contractors handle calls when they're tied up on a job. Just wanted to ask him a quick question.",
    why: 'Keep it casual and brief — gatekeepers respond to confidence and brevity.',
    listenFor: ['transfer', 'screening', 'not available', 'what is this about'],
    branchPreview: {
      transfer: { next: 'OPENER' },
      blocked: { next: 'EXIT' },
    },
    clarifyingQuestion: '',
    valueProp: '',
    proofPoint: '',
    toneVariants: {},
  },

  CALLBACK_CLOSE: {
    id: 'CALLBACK_CLOSE', stage: 'CALLBACK_CLOSE', moveType: 'close',
    deliveryModifier: null,
    goal: 'Schedule callback with right person.',
    primaryLine: "When would be a good time for a quick 15-minute call to walk through how this would work for your shop?",
    backupLine: "Should I try you back Thursday or Friday? Just 15 minutes.",
    why: 'Gets specific callback time instead of vague follow-up.',
    listenFor: ['time offered', 'resistance', 'redirect to email'],
    branchPreview: { engaged: { next: 'BOOKED' }, pushback: { next: 'EXIT' } },
    clarifyingQuestion: "What day works better this week?",
    valueProp: null, proofPoint: null, toneVariants: {},
  },

  TRANSFER_CLOSE: {
    id: 'TRANSFER_CLOSE', stage: 'TRANSFER_CLOSE', moveType: 'close',
    deliveryModifier: null,
    goal: 'Get transferred to decision-maker.',
    primaryLine: "Would you be able to connect me with them now, or should I call back at a specific time?",
    backupLine: "What's the best way to reach them directly?",
    why: 'Asks for transfer or direct contact info.',
    listenFor: ['transfer offered', 'callback time', 'refusal'],
    branchPreview: { engaged: { next: 'OPENER' }, pushback: { next: 'EXIT' } },
    clarifyingQuestion: "Are they usually available in the morning or afternoon?",
    valueProp: null, proofPoint: null, toneVariants: {},
  },

  DIAGNOSTIC_CLOSE: {
    id: 'DIAGNOSTIC_CLOSE', stage: 'DIAGNOSTIC_CLOSE', moveType: 'close',
    deliveryModifier: 'soften',
    goal: 'Offer low-friction audit.',
    primaryLine: "Would it be useful if I sent you a quick 2-minute breakdown of how your calls are being handled right now?",
    backupLine: "No commitment — just a snapshot of what's happening with your inbound calls. Worth a look?",
    why: 'Lowest-friction next step when prospect is interested but not ready to commit.',
    listenFor: ['agreement', 'curiosity', 'still resisting'],
    branchPreview: { engaged: { next: 'BOOKED' }, pushback: { next: 'EXIT' } },
    clarifyingQuestion: "What email should I send that to?",
    valueProp: null, proofPoint: null, toneVariants: {},
  },

  REFERRAL_CLOSE: {
    id: 'REFERRAL_CLOSE', stage: 'REFERRAL_CLOSE', moveType: 'close',
    deliveryModifier: null,
    goal: 'Get referral to right person.',
    primaryLine: "Do you know any other contractors in your area who might be dealing with this same missed-call problem?",
    backupLine: "Even if this isn't the right fit for you, who else comes to mind that's growing and might be missing calls?",
    why: 'Turns a dead end into a warm referral.',
    listenFor: ['name given', 'deflection', 'curiosity'],
    branchPreview: { engaged: { next: 'EXIT' } },
    clarifyingQuestion: "What's their name and what trade are they in?",
    valueProp: null, proofPoint: null, toneVariants: {},
  },

  IDLE: {
    id: 'IDLE',
    stage: 'IDLE',
    moveType: 'pause',
    deliveryModifier: '',
    goal: 'Wait for call to begin',
    primaryLine: 'Press → to start call',
    backupLine: '',
    why: 'Pre-call state. No action needed.',
    listenFor: [],
    branchPreview: {},
    clarifyingQuestion: '',
    valueProp: '',
    proofPoint: '',
    toneVariants: {},
  },
};

// ── Native v2 objection cards ─────────────────────────────────

export const NATIVE_OBJECTION_CARDS = {
  timing: {
    id: 'timing',
    stage: 'OBJECTION',
    moveType: 'reframe',
    deliveryModifier: 'compress',
    goal: 'Respect pressure while preserving a path.',
    primaryLine: "Totally fair. Quick question — when a call comes in while you're on a job, what happens to it?",
    backupLine: "I'll keep it brief — is missed-call coverage something you feel great about right now, or is it still a little messy?",
    why: 'Acknowledges time pressure, redirects to discovery.',
    listenFor: ['workflow answer', 'continued resistance', 'softening'],
    branchPreview: { engaged: { next: 'BRIDGE' }, pushback: { next: 'EXIT' } },
    clarifyingQuestion: 'When a call comes in during peak time, is it always answered live?',
    valueProp: null,
    proofPoint: null,
    toneVariants: { annoyed: { primaryLine: "Totally get it — one quick thing before I let you go: what happens when a call comes in and nobody can answer?" } },
  },

  interest: {
    id: 'interest',
    stage: 'OBJECTION',
    moveType: 'probe',
    deliveryModifier: '',
    goal: 'Earn one last diagnostic beat.',
    primaryLine: 'Totally fair — when you can\'t get to a new customer call right away, what usually happens?',
    backupLine: 'What happens when you\'re already tied up and another call comes in?',
    why: 'Tests for real coverage gap beneath the dismissal.',
    listenFor: ['engagement', 'repeated rejection', 'gap admission'],
    branchPreview: { engaged: { next: 'QUALIFIER' }, pushback: { next: 'EXIT' } },
    clarifyingQuestion: 'After hours or during peak time, are inbound calls always answered live?',
    valueProp: 'Covers missed calls after hours and during busy jobs.',
    proofPoint: "Even a small number of missed high-intent calls can matter if they're good jobs.",
    toneVariants: {},
  },

  info: {
    id: 'info',
    stage: 'OBJECTION',
    moveType: 'probe',
    deliveryModifier: '',
    goal: 'Earn context before sending generic info.',
    primaryLine: "Happy to. What's your email? ... Quick question while I have you — when a call comes in while you're on a job, what happens to it?",
    backupLine: "I can definitely send something. What I don't want to do is send generic info if this isn't even the right fit.",
    why: 'Collects email and redirects to discovery.',
    listenFor: ['email given', 'curiosity', 'continued deflection'],
    branchPreview: { engaged: { next: 'BRIDGE' }, pushback: { next: 'EXIT' } },
    clarifyingQuestion: "Just so I send the right thing — what are you doing today when new calls come in and no one can answer?",
    valueProp: null,
    proofPoint: null,
    toneVariants: {},
  },

  authority: {
    id: 'authority',
    stage: 'OBJECTION',
    moveType: 'clarify',
    deliveryModifier: '',
    goal: 'Get referral path to decision-maker.',
    primaryLine: "Makes sense. What's the best way to loop them in?",
    backupLine: "No worries — is there a good time to catch the person who handles this?",
    why: 'Routes to referral instead of arguing.',
    listenFor: ['referral given', 'callback offered', 'hard refusal'],
    branchPreview: { engaged: { next: 'GATEKEEPER' }, pushback: { next: 'EXIT' } },
    clarifyingQuestion: "When's a good time to reach them?",
    valueProp: null,
    proofPoint: null,
    toneVariants: {},
  },

  existing_coverage: {
    id: 'existing_coverage',
    stage: 'OBJECTION',
    moveType: 'probe',
    deliveryModifier: '',
    goal: 'Test for coverage gaps, not argue.',
    primaryLine: "Makes sense — usually this isn't about replacing whoever answers now. It's about what happens when they're tied up or it's after hours.",
    backupLine: "Totally. The real question is whether coverage still holds when things get busy, someone's at lunch, or the call comes in after hours.",
    why: 'Shifts from claimed solution to failure mode.',
    listenFor: ['gap revealed', 'defensive answer', 'no gap claimed'],
    branchPreview: { engaged: { next: 'QUALIFIER' }, pushback: { next: 'EXIT' } },
    clarifyingQuestion: 'What happens in those moments?',
    valueProp: "Works as backup when staff can't answer.",
    proofPoint: "Usually this isn't about replacing staff — it's about covering the moments they can't answer.",
    toneVariants: { curious: { primaryLine: "Got it — the part I'd be curious about is what happens when coverage breaks, like after hours or during overflow." } },
  },

  answering_service: {
    id: 'answering_service',
    stage: 'OBJECTION',
    moveType: 'probe',
    deliveryModifier: '',
    goal: 'Separate message-taking from real handling.',
    primaryLine: "Got it — and are they actually qualifying and booking those calls live, or mostly just taking messages?",
    backupLine: "Totally fair. A lot of shops I talk to have coverage, but it still turns into message-taking instead of real job capture.",
    why: 'Exposes the gap between answering and actually booking.',
    listenFor: ['message-taking admitted', 'full handling claimed', 'curiosity'],
    branchPreview: { engaged: { next: 'QUALIFIER' }, pushback: { next: 'EXIT' } },
    clarifyingQuestion: 'When a high-intent caller reaches them, does that usually end in a booked job or a callback task?',
    valueProp: 'Books instead of just taking messages.',
    proofPoint: "This works best where ads are already generating inbound demand.",
    toneVariants: {},
  },

  tried_ai: {
    id: 'tried_ai',
    stage: 'OBJECTION',
    moveType: 'probe',
    deliveryModifier: '',
    goal: 'Separate their past AI experience from CallLock.',
    primaryLine: "Totally fair — most of the AI phone stuff out there is pretty rough. What didn't work about it?",
    backupLine: "Yeah, a lot of that early stuff was bad. What happened when you tried it?",
    why: 'Validates their frustration, then probes for the specific failure to address.',
    listenFor: ['quality', 'booking', 'wrong info', 'customers complained', 'robotic'],
    branchPreview: { engaged: { next: 'QUALIFIER' }, pushback: { next: 'EXIT' } },
    clarifyingQuestion: 'Was it the voice quality, the booking, or something else?',
    valueProp: null,
    proofPoint: null,
    toneVariants: {},
  },

  referral_only: {
    id: 'referral_only',
    stage: 'OBJECTION',
    moveType: 'probe',
    deliveryModifier: '',
    goal: 'Pivot from ad-spend pain to referral-call pain.',
    primaryLine: "That's great — referrals are the best leads. When one of those calls comes in and you're on a job, what happens?",
    backupLine: "Referral calls are high-intent. Those are the ones you really can't afford to miss.",
    why: 'Validates referrals as quality leads, then redirects to the missed-call problem.',
    listenFor: ['voicemail', 'call back', 'miss some', 'wife answers', 'covered'],
    branchPreview: { engaged: { next: 'QUALIFIER' }, pushback: { next: 'EXIT' } },
    clarifyingQuestion: 'Do those callers usually leave a voicemail, or just try someone else?',
    valueProp: null,
    proofPoint: null,
    toneVariants: {},
  },

  competitor_comparison: {
    id: 'competitor_comparison',
    stage: 'OBJECTION',
    moveType: 'probe',
    deliveryModifier: '',
    goal: 'Redirect from feature comparison to their specific problem.',
    primaryLine: "Good question. Before I compare — what's not working about what you have now?",
    backupLine: "There are a bunch of options out there. The real question is whether your calls are getting handled the way you want.",
    why: 'Avoids feature wars by redirecting to their pain.',
    listenFor: ['messages', 'slow', 'expensive', 'robotic', "doesn't book", 'satisfied'],
    branchPreview: { engaged: { next: 'QUALIFIER' }, pushback: { next: 'EXIT' } },
    clarifyingQuestion: "Are you happy with how it's working, or are there gaps?",
    valueProp: null,
    proofPoint: null,
    toneVariants: {},
  },
};

// ── Factory functions ───────────────────────────────────────────

/**
 * Create an empty card with all 14 fields populated with defaults.
 * @param {string} stageId
 * @returns {object}
 */
export function makeEmptyCard(stageId) {
  return {
    id: stageId,
    stage: stageId,
    moveType: STAGE_MOVE_MAP[stageId] || 'pause',
    deliveryModifier: '',
    goal: STAGE_GOAL_MAP[stageId] || '',
    primaryLine: '',
    backupLine: '',
    why: '',
    listenFor: [],
    branchPreview: {},
    clarifyingQuestion: null,
    valueProp: null,
    proofPoint: null,
    toneVariants: {},
  };
}

/**
 * Normalize a playbook stage into a v2 card.
 * Creates an empty card and fills primaryLine from the playbook.
 * @param {string} stageId
 * @param {object} playbook
 * @returns {object}
 */
export function normalizeCard(stageId, playbook) {
  const card = makeEmptyCard(stageId);
  card.primaryLine = lineForStage(stageId, playbook);
  return card;
}
