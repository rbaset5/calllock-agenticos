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
      'When you can\'t get to the phone, we answer it, find out what the customer needs, and get them on your schedule.',
    howItWorks:
      'When a call comes in and you can\'t pick up, it answers live — not voicemail. It asks them what they need, where they\'re located, gets their info, and books them in. You see it in your calendar. Customer got taken care of. You never knew you missed a call.',
    whyYouNeed:
      'How many calls a week do you think slip through? At your ticket size, even one or two a month adds up fast.',
  },


  // ── Bridge angles ───────────────────────────────────────────────

  bridge: {
    missed_calls: {
      voicemail:
        'Yeah... that caller already dialed your competitor while they were waiting.',
      staff:
        'Yeah... what about nights and weekends? Those callers don\'t wait.',
      covered:
        'Yeah... what happens when you\'re already tied up and another call comes in?',
      afterHours:
        'Most guys I talk to have it covered during the day. It\'s the 6 PM call on a Tuesday that disappears.',
    },
    competition: {
      slow:
        'Yeah... the contractors picking up market share right now are the ones available when everyone else isn\'t.',
      firstResponder:
        'Half the time, the job goes to whoever picks up first. Not whoever\'s cheapest, not whoever\'s best — whoever answers.',
      shared:
        'On Angi and Thumbtack, that same lead goes to 3-5 other guys. First one to answer gets the job.',
    },
    overwhelmed: {
      everything:
        'Yeah... every call you answer personally is time you\'re not on the job.',
      cantKeepUp:
        'Yeah... every missed call is a job your competitor books instead.',
    },
    ad_spend: {
      lsa:
        'You\'re spending a couple thousand a month on Google ads that ring your phone. How many of those go to voicemail after 5?',
      wasted:
        'At $50-$100 per lead from Google, every missed call is money you already spent — just gone.',
    },
    fallback:
      'What does it cost you when one of those calls slips through the cracks?',
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
        'Totally fair — when you can\'t get to a new customer call right away, what usually happens?',
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
    existing_coverage: {
      keywords: ['receptionist', 'wife answers', "we're covered", 'someone answers'],
      reset:
        "Makes sense — usually this isn't about replacing whoever answers now. It's about what happens when they're tied up or it's after hours.",
    },
    answering_service: {
      keywords: ['answering service', 'smith', 'ruby', 'nexa'],
      reset:
        'Got it — and are they actually qualifying and booking those calls live, or mostly just taking messages?',
    },
    tried_ai: {
      keywords: ['tried ai', 'used ai', 'robot', 'chatbot'],
      reset:
        "Totally fair — most of the AI phone stuff out there is pretty rough. What didn't work about it?",
    },
    referral_only: {
      keywords: ['referrals', 'word of mouth', 'no ads'],
      reset:
        "That's great — referrals are the best leads. When one of those calls comes in and you're on a job, what happens?",
    },
    competitor_comparison: {
      keywords: ['sameday', 'servicetitan', 'different', 'why you'],
      reset:
        "Good question. Before I compare — what's not working about what you have now?",
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
    { tag: 'pattern-interrupt', line: 'What would have to change for this to be worth a look?' },
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
    { tag: 'social-proof', line: "That's what I'd say too if I were in your shoes." },
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
      if (/angi|thumbtack|shared/i.test(classification.utterance)) return pb.competition.shared;
      return pb.competition.firstResponder;

    case 'overwhelmed':
      if (/everything|myself|do it all/i.test(classification.utterance)) return pb.overwhelmed.everything;
      return pb.overwhelmed.cantKeepUp;

    case 'ad_spend':
      if (/wasted|waste|per lead|cost per/i.test(classification.utterance)) return pb.ad_spend.wasted;
      return pb.ad_spend.lsa;

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
    case 'GATEKEEPER':        return playbook.gatekeeper.reach;
    case 'OPENER':            return playbook.opener;
    case 'PERMISSION_MOMENT': return 'Can I ask you a quick question about new customer calls?';
    case 'MINI_PITCH':        return "We help contractors make sure inbound calls get handled when the team can't answer live.";
    case 'WRONG_PERSON':      return "Makes sense. What's the best way to reach the person who handles that?";
    case 'PRICING':           return "Happy to cover that — first I want to make sure this is even a problem worth solving on your side. When calls come in and nobody can grab them, what usually happens?";
    case 'BRIDGE':            return playbook.bridge.fallback;
    case 'QUALIFIER':         return playbook.qualifier;
    case 'SEED_EXIT':         return playbook.seedExit;
    case 'CLOSE':             return playbook.close;
    case 'BOOKED':            return playbook.booked;
    case 'EXIT':              return playbook.exit;
    case 'NON_CONNECT':       return playbook.voicemail;
    default:                  return '';
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
    case 'PERMISSION_MOMENT':
      return [
        { label: 'Permission ask', line: 'Can I ask you a quick question about new customer calls?' },
        { label: 'Backup (20s)', line: "This'll take 20 seconds — when a new call comes in and you can't grab it, what happens?" },
      ];
    case 'MINI_PITCH':
      return [
        { label: 'Mini pitch', line: "We help contractors make sure inbound calls get handled when the team can't answer live." },
        { label: 'Backup', line: "We help contractors avoid losing jobs when calls come in and nobody can grab the phone." },
        { label: 'Clarify', line: 'How are you handling that today?' },
      ];
    case 'WRONG_PERSON':
      return [
        { label: 'Referral ask', line: "Makes sense. What's the best way to reach the person who handles that?" },
        { label: 'Backup', line: "No worries — is there a good time to catch the owner?" },
        { label: 'Timing', line: "When's a good time to reach them?" },
      ];
    case 'PRICING':
      return [
        { label: 'Reframe', line: "Happy to cover that — first I want to make sure this is even a problem worth solving on your side. When calls come in and nobody can grab them, what usually happens?" },
        { label: 'Backup', line: "I can cover pricing. I just don't want to throw numbers at you before knowing whether there's actually a problem to solve." },
        { label: 'Frequency', line: 'How often do you think a good inbound call comes in when nobody can answer it properly?' },
      ];
    case 'BRIDGE':
      return [
        { label: '❌ Missed/voicemail', line: playbook.bridge.missed_calls.voicemail },
        { label: '❌ Missed/staff', line: playbook.bridge.missed_calls.staff },
        { label: '❌ Missed/covered', line: playbook.bridge.missed_calls.covered },
        { label: '📊 Comp/slow', line: playbook.bridge.competition.slow },
        { label: '📊 Comp/first', line: playbook.bridge.competition.firstResponder },
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
    TRADE: context.trade || 'home service',
  };

  return line.replace(/\{([A-Z]+)\}/g, (match, token) => replacements[token] || match);
}
