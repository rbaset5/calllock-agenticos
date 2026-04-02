// dialer/hud/playbook.js
// Canonical v2 playbook data + line resolution helpers.
// Vanilla JS ES module — no build step, no TypeScript.

export const PLAYBOOK = {
  version: '3.0-founder-final',

  doctrine: {
    core_principle: 'One response. Then shut up.',
    goal: 'Classify the moment, select the approved line, then wait.',
  },

  // ── Scripted lines ──────────────────────────────────────────────

  opener:
    'Hey {NAME}, this is Rashid over in Houston — cold call, quick question: when a call comes in while you\'re on a job, what happens to it?',

  qualifier: 'How many calls a week do you think go unanswered?',

  close: 'Worth 15 minutes? Thursday or Friday?',

  hedge:
    'Thursday at 2 — 15 minutes. If it\'s not useful, I\'ll leave you alone.',

  yesFollowup:
    'Great. Thursday at 2 work? ... Perfect. What\'s the best email for a calendar invite?',

  seedExit:
    'If that ever changes, worth a 15-minute conversation. I\'ll send you a quick note.',

  exit: 'No worries. If you ever revisit, we\'re here.',

  booked: 'Perfect — invite heading your way. Talk {DAY}!',

  voicemail:
    'Hey {NAME}, Rashid calling from Houston — I work with contractors on what happens to their calls when they\'re tied up on a job. Worth a quick conversation. Call me back at {NUMBER}, or I\'ll try you again {DAY}.',

  textA:
    'Hey {NAME} — Rashid here. Left you a voicemail. I help {TRADE} contractors handle calls when they\'re on a job. Worth 2 minutes?',

  textB:
    'Hey {NAME} — quick question: when a call comes in while you\'re on a job, what happens to it?',

  // ── Pitch lines (what CallLock does — any stage) ────────────────

  pitchLines: {
    elevator:
      'We built an AI that answers your phones when you\'re on a job — qualifies the caller, and books the appointment directly to your calendar.',
    howItWorks:
      'When a call comes in and you can\'t pick up, it answers live — not voicemail. It asks them what they need, where they\'re located, gets their info, and books them in. You see it in your calendar. Customer got taken care of. You never knew you missed a call.',
    whyYouNeed:
      'Most of my guys tell me they\'re losing 2-3 calls a week they never call back in time. At your average ticket that\'s a few thousand dollars a month just disappearing. This is the fix for that.',
  },

  // ── Bridge angles ───────────────────────────────────────────────

  bridge: {
    missed_calls: {
      voicemail:
        'Yeah... that caller already dialed your competitor while they were waiting.',
      staff:
        'Yeah... what about nights and weekends? Those callers don\'t wait.',
      covered:
        'Yeah... what happens when two calls come in at once?',
    },
    competition: {
      slow:
        'Yeah... the contractors picking up market share right now are the ones available when everyone else isn\'t.',
      competitor:
        'Yeah... most jobs go to whoever responds first. Not whoever\'s cheapest.',
    },
    overwhelmed: {
      everything:
        'Yeah... every call you answer personally is time you\'re not on the job.',
      cantKeepUp:
        'Yeah... the call you miss today is a review you didn\'t get next month.',
    },
    fallback:
      'What does it cost you when a call goes to voicemail on a Monday morning?',
  },

  // ── Qualifier reads ─────────────────────────────────────────────

  qualifierReads: {
    pain: {
      keywords: ['more than', 'too many', 'losing', 'frustrating', 'frustrated', 'a lot'],
      patterns: ['\\b[0-9]+\\b'],
      next_state: 'CLOSE',
    },
    no_pain: {
      keywords: ['a few', 'not many', 'pretty covered', "we're good", 'not really'],
      next_state: 'SEED_EXIT',
    },
    unknown_pain: {
      keywords: ["don't know", 'not sure', "haven't tracked", 'no idea'],
      bridge_line: "That's usually where the problem hides.",
      next_state: 'CLOSE',
    },
  },

  // ── Objection buckets ───────────────────────────────────────────

  objections: {
    timing: {
      keywords: ['busy', 'bad time', 'not now', 'call back', 'in the middle of'],
      reset:
        'Totally fair. Quick question — when a call comes in while you\'re on a job, what happens to it?',
    },
    interest: {
      keywords: ['not interested', "we're set", "don't need", 'all good', 'no thanks'],
      reset:
        'Got it. What happens when two calls come in at once?',
    },
    info: {
      keywords: ['send me info', 'email me', 'send something', 'website'],
      reset:
        'Happy to. What\'s your email? ... Quick question while I have you — when a call comes in while you\'re on a job, what happens to it?',
    },
    authority: {
      keywords: ["don't handle that", 'not my decision', 'talk to my', 'wife handles', 'partner handles'],
      reset:
        'Makes sense. What\'s the best way to loop them in?',
    },
  },

  // ── Gatekeeper lines ────────────────────────────────────────────

  gatekeeper: {
    reach:
      'Hey, it\'s Rashid — I was trying to reach {NAME} about their business calls. Is he around?',
    whatsThisAbout:
      'I help contractors handle calls when they\'re tied up on a job. Just wanted to ask him a quick question.',
    notAvailable:
      'No worries. When\'s a good time to catch him?',
  },

  powerLines: [
    { tag: 'silence', line: '(pause — let them fill the silence)' },
    {
      tag: 'reframe',
      line: 'Let me ask it differently — if you lost two jobs this week because nobody picked up, would you know?',
    },
    { tag: 'pattern-interrupt', line: 'Can I be honest with you for a second?' },
    { tag: 'validate', line: 'That makes total sense.' },
    {
      tag: 'curiosity',
      line: 'What would have to be true for this to be worth 15 minutes?',
    },
  ],

  recoveryLines: [
    { tag: 'buy-time', line: "That's a great question." },
    { tag: 'acknowledge', line: 'I hear you.' },
    { tag: 'validate', line: 'Totally fair.' },
    { tag: 'social-proof', line: 'Most guys I talk to say the same thing at first.' },
    { tag: 'redirect', line: "What would make this worth your time?" },
    { tag: 'reframe', line: 'Let me ask you this—' },
  ],
};

// ── Line resolution helpers ─────────────────────────────────────

/**
 * Pick the right bridge variant based on a classification result.
 * @param {object} classification  – must have `.bridgeAngle` and `.utterance`
 * @param {object} playbook
 * @returns {string}
 */
export function resolveBridgeLine(classification, playbook) {
  const pb = playbook.bridge;

  switch (classification.bridgeAngle) {
    case 'missed_calls':
      if (/voicemail|callback/i.test(classification.utterance)) return pb.missed_calls.voicemail;
      if (/wife|office|staff|receptionist/i.test(classification.utterance)) return pb.missed_calls.staff;
      return pb.missed_calls.covered;

    case 'competition':
      if (/slow|season/i.test(classification.utterance)) return pb.competition.slow;
      return pb.competition.competitor;

    case 'overwhelmed':
      if (/everything|myself|do it all/i.test(classification.utterance)) return pb.overwhelmed.everything;
      return pb.overwhelmed.cantKeepUp;

    case 'fallback':
    case 'unknown':
    default:
      return pb.fallback;
  }
}

/**
 * Return the default line for a given stage (used by manual override).
 * @param {string} stage
 * @param {object} playbook
 * @returns {string}
 */
export function lineForStage(stage, playbook) {
  switch (stage) {
    case 'GATEKEEPER':  return playbook.gatekeeper.reach;
    case 'OPENER':      return playbook.opener;
    case 'BRIDGE':      return playbook.bridge.fallback;
    case 'QUALIFIER':   return playbook.qualifier;
    case 'SEED_EXIT':   return playbook.seedExit;
    case 'CLOSE':       return playbook.close;
    case 'BOOKED':      return playbook.booked;
    case 'EXIT':        return playbook.exit;
    case 'NON_CONNECT': return playbook.voicemail;
    default:            return '';
  }
}

/**
 * Return all quick-access lines for a stage.
 * @param {string} stage
 * @param {object} playbook
 * @returns {Array<{label: string, line: string}>}
 */
// Pitch lines available at any stage (P key toggles)
export function pitchLines(playbook) {
  return [
    { label: '🎯 Elevator pitch', line: playbook.pitchLines.elevator },
    { label: '🔧 How it works', line: playbook.pitchLines.howItWorks },
    { label: '💰 Why you need it', line: playbook.pitchLines.whyYouNeed },
  ];
}

export function linesForStage(stage, playbook) {
  switch (stage) {
    case 'GATEKEEPER':
      return [
        { label: 'reach', line: playbook.gatekeeper.reach },
        { label: 'whatsThisAbout', line: playbook.gatekeeper.whatsThisAbout },
        { label: 'notAvailable', line: playbook.gatekeeper.notAvailable },
      ];
    case 'OPENER':
      return [
        { label: '📞 Opener', line: playbook.opener },
        { label: '🎯 Elevator pitch', line: playbook.pitchLines.elevator },
        { label: '🔧 How it works', line: playbook.pitchLines.howItWorks },
        { label: '💰 Why you need it', line: playbook.pitchLines.whyYouNeed },
      ];
    case 'BRIDGE':
      return [
        { label: '❌ Missed/voicemail', line: playbook.bridge.missed_calls.voicemail },
        { label: '❌ Missed/staff', line: playbook.bridge.missed_calls.staff },
        { label: '❌ Missed/covered', line: playbook.bridge.missed_calls.covered },
        { label: '📊 Comp/slow', line: playbook.bridge.competition.slow },
        { label: '📊 Comp/first', line: playbook.bridge.competition.competitor },
        { label: '🔥 Overwhelm/everything', line: playbook.bridge.overwhelmed.everything },
        { label: '🔥 Overwhelm/keep up', line: playbook.bridge.overwhelmed.cantKeepUp },
        { label: '❓ Fallback', line: playbook.bridge.fallback },
      ];
    case 'QUALIFIER':
      return [
        { label: '📞 Ask the question', line: playbook.qualifier },
        { label: '🔍 Unknown pain bridge', line: playbook.qualifierReads.unknown_pain.bridge_line },
        { label: '🎯 Elevator pitch', line: playbook.pitchLines.elevator },
        { label: '🔧 How it works', line: playbook.pitchLines.howItWorks },
        { label: '💰 Why you need it', line: playbook.pitchLines.whyYouNeed },
      ];
    case 'CLOSE':
      return [
        { label: '🤝 Close', line: playbook.close },
        { label: '🛡️ Hedge', line: playbook.hedge },
        { label: '✅ Yes followup', line: playbook.yesFollowup },
        { label: '🎯 Elevator pitch', line: playbook.pitchLines.elevator },
        { label: '💰 Why you need it', line: playbook.pitchLines.whyYouNeed },
      ];
    case 'SEED_EXIT':
      return [
        { label: 'seedExit', line: playbook.seedExit },
        { label: '🎯 Elevator pitch', line: playbook.pitchLines.elevator },
      ];
    case 'OBJECTION':
      return [
        { label: '⏰ Timing reset', line: playbook.objections.timing.reset },
        { label: '🚫 Interest reset', line: playbook.objections.interest.reset },
        { label: '📧 Info reset', line: playbook.objections.info.reset },
        { label: '👤 Authority reset', line: playbook.objections.authority.reset },
        { label: '🎯 Elevator pitch', line: playbook.pitchLines.elevator },
        { label: '💰 Why you need it', line: playbook.pitchLines.whyYouNeed },
      ];
    case 'NON_CONNECT':
      return [
        { label: 'voicemail', line: playbook.voicemail },
        { label: 'textA', line: playbook.textA },
        { label: 'textB', line: playbook.textB },
      ];
    case 'BOOKED':
      return [{ label: 'booked', line: playbook.booked }];
    case 'EXIT':
      return [{ label: 'exit', line: playbook.exit }];
    default:
      return [];
  }
}

/**
 * Fill playbook template placeholders with available prospect context.
 * @param {string} line
 * @param {object} context
 * @returns {string}
 */
export function fillLineTemplate(line, context = {}) {
  const replacements = {
    NAME: context.name || context.business || 'there',
    NUMBER: context.number || context.phone || 'the number you have for me',
    DAY: context.day || 'later this week',
    TRADE: context.trade || 'HVAC',
  };

  return line.replace(/\{([A-Z]+)\}/g, (match, token) => replacements[token] || match);
}
