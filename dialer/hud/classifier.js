// dialer/hud/classifier.js — Rules-based utterance classifier
// Direct port of the canonical rules.ts spec to vanilla JS ES modules.

// -------------------------
// Helpers
// -------------------------

const WORD_RE = /[a-z0-9']+/gi;

export function normalize(input) {
  return input
    .toLowerCase()
    .replace(/[–—-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function tokens(input) {
  return normalize(input).match(WORD_RE) ?? [];
}

export function hasPhrase(text, phrase) {
  // Strip commas/semicolons/periods so "Alright, Thursday" matches "alright thursday"
  const cleanText = normalize(text).replace(/[,;:.!?]/g, ' ').replace(/\s+/g, ' ');
  return cleanText.includes(normalize(phrase));
}

export function countPhraseMatches(text, phrases) {
  return phrases.reduce((acc, p) => acc + (hasPhrase(text, p) ? 1 : 0), 0);
}

export function countTokenMatches(textTokens, words) {
  const set = new Set(textTokens);
  return words.reduce((acc, w) => acc + (set.has(w) ? 1 : 0), 0);
}

export function hasNumber(text) {
  return /\b\d+\b/.test(text);
}

function clamp01(n) {
  return Math.max(0, Math.min(1, n));
}

export function bandFromScore(score) {
  if (score >= 0.8) return "high";
  if (score >= 0.6) return "medium";
  return "low";
}

function makeResult(utterance, partial) {
  const confidence = clamp01(partial.confidence);
  return {
    utterance,
    confidence,
    band: bandFromScore(confidence),
    ...partial,
  };
}

function lowConfidenceUnknown(utterance, why) {
  return makeResult(utterance, {
    confidence: 0.25,
    why,
  });
}

function bestScoredKey(scores) {
  const entries = Object.entries(scores);
  entries.sort((a, b) => b[1] - a[1]);
  const [winner, winnerScore] = entries[0];
  const runnerUpScore = entries[1]?.[1] ?? 0;
  return { winner, winnerScore, runnerUpScore };
}

// -------------------------
// Phrase dictionaries
// -------------------------

const GATEKEEPER_WHATS_THIS_ABOUT = [
  "what's this about",
  "what is this about",
  "what's this regarding",
  "what is this regarding",
  "who is this",
  "why are you calling",
];

const GATEKEEPER_NOT_AVAILABLE = [
  "he's not available",
  "not available",
  "in a meeting",
  "out right now",
  "not here",
  "can i take a message",
  "what do you need",
];

const CALLBACK_PHRASES = [
  "call back",
  "try later",
  "later today",
  "tomorrow morning",
  "this afternoon",
  "later this week",
];

const BRIDGE_KEYWORDS = {
  missed_calls: {
    phrases: [
      "goes to voicemail",
      "go to voicemail",
      "we call them back",
      "call them back",
      "my wife answers",
      "my office answers",
      "office handles it",
      "staff handles it",
      "we're covered",
      "we manage",
      "we figure it out",
      "answering service",
      "receptionist gets it",
      "miss some calls",
      "miss calls",
      "miss them",
      "dispatcher gets it",
      "dispatcher handles",
      "weekends are tough",
      "weekends are hard",
      "weekends are difficult",
      "after hours is tough",
      "after hours is hard",
      "close at noon",
      "close early",
    ],
    words: [
      "voicemail",
      "callback",
      "callbacks",
      "wife",
      "office",
      "staff",
      "receptionist",
      "covered",
      "manage",
      "dispatcher",
      "miss",
    ],
  },
  competition: {
    phrases: [
      "slow season",
      "trying to grow",
      "need more jobs",
      "competition is tough",
      "losing jobs",
      "losing bids",
      "want to get bigger",
      "market share",
    ],
    words: [
      "slow",
      "season",
      "growth",
      "grow",
      "competitor",
      "competitors",
      "losing",
      "bids",
      "market",
      "bigger",
    ],
  },
  overwhelmed: {
    phrases: [
      "i do everything",
      "i do it all",
      "it's just me",
      "i answer them myself",
      "can't keep up",
      "too much going on",
      "i'm slammed",
      "i'm stretched thin",
    ],
    words: [
      "busy",
      "slammed",
      "stretched",
      "myself",
      "everything",
      "rushed",
      "overwhelmed",
    ],
  },
};

const QUALIFIER_PAIN_PHRASES = [
  "more than i'd like",
  "more than i would like",
  "too many",
  "a lot",
  "way too many",
  "more than we should",
  "we lose some",
  "it is frustrating",
  "that's frustrating",
];

const QUALIFIER_NO_PAIN_PHRASES = [
  "a few",
  "not many",
  "pretty covered",
  "we're good",
  "we are good",
  "not really",
  "hardly any",
  "almost none",
  "we're covered",
  "we are covered",
  "don't miss calls",
  "don't really miss",
  "we handle it",
  "we've got it handled",
  "my wife answers",
  "my wife handles",
  "office manager handles",
  "receptionist handles",
  "we have a receptionist",
  "we use an answering service",
];

const QUALIFIER_UNKNOWN_PHRASES = [
  "don't know",
  "do not know",
  "not sure",
  "haven't tracked",
  "have not tracked",
  "no idea",
  "depends",
  "hard to say",
];

const OBJECTION_BUCKETS = {
  timing: {
    phrases: [
      "bad time",
      "not a good time",
      "call back later",
      "can't talk right now",
      "in the middle of something",
      "i'm on a job",
      "don't have time",
      "no time for this",
      "not right now",
    ],
    words: ["busy", "later", "tomorrow", "middle"],
  },
  interest: {
    phrases: [
      "not interested",
      "we're set",
      "we are set",
      "don't need it",
      "all good",
      "no thanks",
      "we're fine",
      "we are fine",
      "we're good",
      "we are good",
      "we already handle",
    ],
    words: ["interested", "fine", "set", "good"],
  },
  info: {
    phrases: [
      "send me info",
      "send me something",
      "email me",
      "shoot me an email",
      "send over your website",
      "just send it",
    ],
    words: ["email", "website"],
  },
  authority: {
    phrases: [
      "not my decision",
      "i don't handle that",
      "my wife handles that",
      "my partner handles that",
      "talk to my office",
      "talk to my dispatcher",
    ],
    words: ["decision", "wife", "partner", "dispatcher", "office"],
  },
};

// ── New intent dictionaries (spec Section 11) ──────────────────

const MINI_PITCH_PHRASES = [
  'what is this', 'what do you do', "what's this about", 'who are you',
  'who is this', 'who is calling',
  'what company', 'what are you selling', 'what is this about',
  "i don't understand", "don't understand what", "what do you mean",
  "i don't get it", "what are you talking about",
];

const WRONG_PERSON_PHRASES = [
  "i don't handle that", 'talk to my wife', 'talk to my partner',
  'talk to my husband', 'talk to dispatcher', 'wrong person',
  "i'm the tech", "i'm the helper", 'not my decision',
  "i'm just the tech", "i'm just the technician", "i'm just the installer",
  "just the tech", "just the technician", "just a tech",
  "owner isn't here", "he's not here", "she's not here",
  'my husband handles', 'my wife handles', 'he handles that',
  'she handles that', 'husband handles', 'wife handles',
  'take a message', 'leave your number',
  "can i take a message", "he's in a meeting", "she's in a meeting",
  "let me transfer you", "let me get him", "let me get her",
  "i'll transfer you", "i'll get the owner",
];

const PRICING_QUESTION_PHRASES = [
  'how much', "what's the cost", 'pricing', 'what do you charge', 'price range',
  'how much does it cost', 'what does it cost',
  'give me a ballpark', 'ballpark price', 'ballpark number',
  'tell me the price', 'what does this cost', 'what does something like this cost',
  'how much is it', 'what would it cost',
];

const PRICING_RESISTANCE_PHRASES = [
  'expensive', "can't afford", 'too much', 'not worth it', 'out of budget',
  'costs too much', "don't have the budget",
];

// Multi-word phrases only. Bare "yeah"/"sure"/"ok" handled by SHORT_UTTERANCE_MAP
// to avoid false positives in longer sentences like "yeah we get some calls".
const YES_PHRASES = [
  "that works",
  "sounds good",
  "thursday works",
  "friday works",
  "wednesday works",
  "monday works",
  "tuesday works",
  "let's do it",
  "let's set it up",
  "set something up",
  "set it up",
  "book it",
  "schedule it",
  "i'm down",
  "sign me up",
  "worth a look",
  "worth looking",
  "let's talk",
  "let's do",
  "morning works",
  "afternoon works",
  "before 9",
  "before 10",
  "after lunch",
  "sure yeah",
  "yeah sure",
  "sure let's",
  "ok let's",
  "yeah let's",
  "fine thursday",
  "fine friday",
  "fine wednesday",
  "fine monday",
  "fine tuesday",
  "fine show me",
  "fine let's",
  "alright thursday",
  "alright friday",
  "alright let's",
  "set up a call",
  "put me down",
  "put something on",
  "esta bien",
  "thursday i guess",
  "friday i guess",
  "friday at 2",
  "friday at 3",
  "wednesday at 4",
  "thursday at 2",
  "thursday at 3",
  "monday at",
  "tuesday at",
  "would work",
  "that works",
  "works for me",
  "works for both",
  "works for us",
];

const HEDGE_PHRASES = [
  "maybe",
  "let me think",
  "not sure",
  "i guess",
  "possibly",
];

// Exit-intent: DNC, wrong number, hostile, business closed
const EXIT_INTENT_PHRASES = [
  'take me off', 'remove my number', 'stop calling', 'do not call',
  'wrong number', 'not a business', "don't call again", 'harassment',
  'reporting you', 'report you', 'closed down', 'went out of business',
  'retired', 'sold the business', 'sold the company', 'no longer in business',
  'i said goodbye', 'i said no', 'i said bye',
  "you've reached", 'leave a message after the tone', 'leave a message at the beep',
  'please leave a message', 'not available right now',
  "i'm not going to", "not going to take a message",
  'hanging up', 'i gotta go bye',
];

// Conference / multi-party detection (NOT authority_mismatch)
const CONFERENCE_PHRASES = [
  'on speaker', 'speakerphone', 'both here', 'me and my partner are',
  'we are both', "we're both", 'got you on speaker',
];

// Short utterance map: 1-4 word responses with clear intent
// Note: "not interested" is NOT here — it goes through the stage-specific objection
// classifier which provides richer objectionBucket context.
const SHORT_UTTERANCE_MAP = {
  'no': 'brush_off',
  'nope': 'brush_off',
  'nah': 'brush_off',
  'bye': 'brush_off',
  'goodbye': 'brush_off',
  'yeah': 'engaged_answer',
  'yes': 'engaged_answer',
  'yep': 'engaged_answer',
  'sure': 'engaged_answer',
  'ok': 'engaged_answer',
  'okay': 'engaged_answer',
  'what': 'confusion',
  'huh': 'confusion',
  'what?': 'confusion',
  'huh?': 'confusion',
  'hmm': 'confusion',
  'who is this': 'confusion',
  'say again': 'confusion',
  'say that again': 'confusion',
  'come again': 'confusion',
};

// -------------------------
// Public API
// -------------------------

/**
 * Detect new v2 intents (confusion, wrong_person, pricing).
 * Returns { intent, confidence } or null if no match.
 * Stage-aware: same keyword weighted differently by current stage.
 */
export function detectNewIntents(utterance, stage) {
  const text = normalize(utterance);

  // Check confusion / mini-pitch
  const confusionHits = countPhraseMatches(text, MINI_PITCH_PHRASES);
  if (confusionHits > 0) {
    const stageBoost = ['OPENER', 'GATEKEEPER', 'PERMISSION_MOMENT'].includes(stage) ? 0.15 : 0;
    return { intent: 'confusion', confidence: clamp01(0.65 + stageBoost + (confusionHits - 1) * 0.1) };
  }

  // Exit-intent detection FIRST — DNC, wrong number, voicemail, hostile, closed.
  // Must run before wrong_person so "leave a message after the tone" matches as
  // voicemail exit, not gatekeeper/wrong_person.
  const exitHits = countPhraseMatches(text, EXIT_INTENT_PHRASES);
  if (exitHits > 0) {
    return { intent: 'brush_off', confidence: clamp01(0.80 + (exitHits - 1) * 0.05) };
  }

  // Conference call detection BEFORE wrong_person — "on speaker with my partner"
  // should not trigger authority_mismatch
  const confCallHits = countPhraseMatches(text, CONFERENCE_PHRASES);
  if (confCallHits > 0) {
    return { intent: 'engaged_answer', confidence: 0.65 };
  }

  // Check wrong person
  const wpHits = countPhraseMatches(text, WRONG_PERSON_PHRASES);
  if (wpHits > 0) {
    return { intent: 'authority_mismatch', confidence: clamp01(0.70 + (wpHits - 1) * 0.1) };
  }

  // Check pricing question
  const pqHits = countPhraseMatches(text, PRICING_QUESTION_PHRASES);
  if (pqHits > 0) {
    const stageBoost = ['QUALIFIER', 'CLOSE', 'BRIDGE'].includes(stage) ? 0.1 : 0;
    return { intent: 'pricing_question', confidence: clamp01(0.68 + stageBoost + (pqHits - 1) * 0.08) };
  }

  // Check pricing resistance
  const prHits = countPhraseMatches(text, PRICING_RESISTANCE_PHRASES);
  if (prHits > 0) {
    return { intent: 'pricing_resistance', confidence: clamp01(0.65 + (prHits - 1) * 0.08) };
  }

  // Yes/booking intent — checked BEFORE objection intents in booking-relevant stages
  // so "we have a receptionist but yeah Thursday works" captures the booking, not the objection.
  const yesHitsEarly = countPhraseMatches(text, YES_PHRASES);
  if (yesHitsEarly > 0 && ['CLOSE', 'QUALIFIER', 'BRIDGE', 'PRICING'].includes(stage)) {
    const stageBoost = ['CLOSE', 'QUALIFIER'].includes(stage) ? 0.1 : 0;
    return { intent: 'yes', confidence: clamp01(0.65 + stageBoost + (yesHitsEarly - 1) * 0.08) };
  }

  // Check existing coverage / answering service / tried AI / referral only / competitor comparison
  const EXISTING_COVERAGE_PHRASES = [
    'have a receptionist', 'we have a receptionist', 'receptionist handles',
    'wife answers', 'my wife answers', 'my wife handles',
    'someone answers', 'office manager handles', "we're covered",
    "we are covered", "don't miss calls", "we don't miss",
  ];
  const ecHits = countPhraseMatches(text, EXISTING_COVERAGE_PHRASES);
  if (ecHits > 0) {
    return { intent: 'existing_coverage', confidence: clamp01(0.70 + (ecHits - 1) * 0.08) };
  }

  const ANSWERING_SERVICE_PHRASES = [
    'answering service', 'use an answering', 'have an answering',
    'use smith', 'use ruby', 'use nexa', 'already have someone',
    'someone answers our phones',
  ];
  const asHits = countPhraseMatches(text, ANSWERING_SERVICE_PHRASES);
  if (asHits > 0) {
    return { intent: 'answering_service', confidence: clamp01(0.72 + (asHits - 1) * 0.08) };
  }

  const TRIED_AI_PHRASES = [
    'tried ai', 'used ai', 'had ai', 'ai before',
    'tried a robot', 'robot answering', 'tried chatbot',
    'tried one of those', 'tried something like that',
  ];
  const taiHits = countPhraseMatches(text, TRIED_AI_PHRASES);
  if (taiHits > 0) {
    return { intent: 'tried_ai', confidence: clamp01(0.68 + (taiHits - 1) * 0.08) };
  }

  const REFERRAL_ONLY_PHRASES = [
    'all referrals', 'referrals only', 'word of mouth',
    "don't run ads", "don't do ads", 'no google ads', 'no ads',
    "don't advertise", "don't do marketing",
  ];
  const roHits = countPhraseMatches(text, REFERRAL_ONLY_PHRASES);
  if (roHits > 0) {
    return { intent: 'referral_only', confidence: clamp01(0.68 + (roHits - 1) * 0.08) };
  }

  const COMPETITOR_COMPARISON_PHRASES = [
    'how is this different', 'what makes you different', 'why you',
    'use sameday', 'use servicetitan', 'heard of sameday',
    "what's different", 'how are you different',
  ];
  const ccHits = countPhraseMatches(text, COMPETITOR_COMPARISON_PHRASES);
  if (ccHits > 0) {
    return { intent: 'competitor_comparison', confidence: clamp01(0.68 + (ccHits - 1) * 0.08) };
  }

  // Check curiosity / engagement (helps advance from OPENER and BRIDGE)
  const CURIOSITY_PHRASES = [
    'how does that work', 'tell me more', 'that sounds interesting',
    'how would that work', 'what does that mean', 'what do you got',
    'what do you have', 'been looking for', 'was hoping', 'looking into',
    'is this a sales call', 'what are you offering',
    'returning your call', 'returning a call', 'you called me',
    'sounds like what we need', 'sounds like what i need',
    'that would help', 'we could use that', 'show me',
    'how does yours work', 'can you do that', 'can yours do that',
    'what would that look like',
    'how does it work', 'sounds interesting', 'looking for something',
    'been looking for something',
    "i'm interested", "yeah i'm interested", "that's interesting",
  ];
  const curHits = countPhraseMatches(text, CURIOSITY_PHRASES);
  if (curHits > 0) {
    const stageBoost = ['OPENER', 'PERMISSION_MOMENT'].includes(stage) ? 0.1 : 0;
    return { intent: 'curiosity', confidence: clamp01(0.65 + stageBoost + (curHits - 1) * 0.08) };
  }

  // Time pressure / urgency — only in OPENER/GATEKEEPER context.
  // In CLOSE/OBJECTION/BRIDGE, "I'm busy" is a timing objection handled by
  // the stage-specific classifier with richer objectionBucket context.
  if (['OPENER', 'GATEKEEPER', 'IDLE', 'PERMISSION_MOMENT'].includes(stage)) {
    const TIME_PRESSURE_PHRASES = [
      'make it quick', 'be quick', 'in a hurry', "don't have time",
      "i'm busy", 'got to go', 'gotta go',
      "can't talk", "can't talk right now", 'real quick',
      'thirty seconds', '30 seconds', 'make it fast',
    ];
    const tpHits = countPhraseMatches(text, TIME_PRESSURE_PHRASES);
    if (tpHits > 0) {
      return { intent: 'time_pressure', confidence: clamp01(0.70 + (tpHits - 1) * 0.08) };
    }
  }

  // Yes/booking intent — fallback for non-booking stages (OPENER, OBJECTION, etc.)
  if (yesHitsEarly > 0) {
    const stageBoost = ['CLOSE', 'QUALIFIER'].includes(stage) ? 0.1 : 0;
    return { intent: 'yes', confidence: clamp01(0.65 + stageBoost + (yesHitsEarly - 1) * 0.08) };
  }

  // Short utterance heuristics (1-4 words, no other match found)
  const wordCount = text.split(/\s+/).filter(w => w.length > 0).length;
  if (wordCount <= 4) {
    const cleanText = text.replace(/[?.!,]/g, '').trim();
    const mapped = SHORT_UTTERANCE_MAP[cleanText];
    if (mapped) {
      return { intent: mapped, confidence: 0.65 };
    }
  }

  return null;
}

export function classifyUtterance(utterance, { stage } = {}) {
  const text = normalize(utterance);

  // v2 pre-check: detect new intents before stage-specific routing
  // Skip for GATEKEEPER — its own classifier handles confusion phrases with richer context
  // Skip authority_mismatch for CLOSE/OBJECTION — their classifier provides richer objectionBucket
  if (stage !== 'GATEKEEPER') {
    const newIntent = detectNewIntents(utterance, stage);
    if (newIntent && newIntent.confidence >= 0.65) {
      const skipAuthority = newIntent.intent === 'authority_mismatch'
        && (stage === 'CLOSE' || stage === 'OBJECTION');
      if (!skipAuthority) {
        return makeResult(utterance, {
          confidence: newIntent.confidence,
          why: `new intent detected: ${newIntent.intent}`,
          // Pass through the intent for downstream use
          detectedIntent: newIntent.intent,
        });
      }
    }
  }

  if (!text) {
    return lowConfidenceUnknown(utterance, "Empty utterance");
  }

  switch (stage) {
    case "GATEKEEPER":
      return classifyGatekeeper(utterance);

    case "OPENER":
      return classifyBridge(utterance);

    case "MINI_PITCH":
    case "WRONG_PERSON": {
      // These side stages need deterministic exit paths, not just LLM.
      // Any bridge-angle signal → advance. Any engaged response → advance.
      const bridgeResult = classifyBridge(utterance);
      if (bridgeResult.confidence >= 0.5) {
        return bridgeResult;
      }
      // Fall through to low-confidence so LLM can also try
      return lowConfidenceUnknown(utterance, `${stage}: no clear bridge signal, awaiting LLM`);
    }

    case "BRIDGE": {
      // In BRIDGE, if the prospect gives NUMBERS (quantified pain), they're
      // answering the bridge question with qualifier-ready data. Route to
      // qualifier classifier. Pain words WITHOUT numbers are still bridge
      // angle confirmation (e.g., "we miss some calls" = confirming the angle).
      const hasNumbers = /\b\d+\b/.test(text);
      if (hasNumbers) {
        const qualResult = classifyQualifier(utterance);
        if (qualResult.confidence >= 0.5) {
          return qualResult;
        }
      }
      return classifyBridge(utterance);
    }

    case "QUALIFIER":
      return classifyQualifier(utterance);

    case "CLOSE":
    case "OBJECTION":
      return classifyObjectionOrClose(utterance);

    case "SEED_EXIT":
    case "BOOKED":
    case "EXIT":
    case "NON_CONNECT":
    case "IDLE":
    case "ENDED":
    default:
      return lowConfidenceUnknown(utterance, `No deterministic classifier for stage ${stage}`);
  }
}

// -------------------------
// Stage-specific classifiers
// -------------------------

export function classifyGatekeeper(utterance) {
  const text = normalize(utterance);

  if (countPhraseMatches(text, GATEKEEPER_WHATS_THIS_ABOUT) > 0) {
    return makeResult(utterance, {
      confidence: 0.92,
      stageSuggestion: "GATEKEEPER",
      why: "Gatekeeper asked what the call is about",
    });
  }

  if (countPhraseMatches(text, GATEKEEPER_NOT_AVAILABLE) > 0) {
    return makeResult(utterance, {
      confidence: 0.86,
      stageSuggestion: "GATEKEEPER",
      why: "Gatekeeper signaled owner unavailable",
    });
  }

  if (countPhraseMatches(text, CALLBACK_PHRASES) > 0) {
    return makeResult(utterance, {
      confidence: 0.74,
      stageSuggestion: "EXIT",
      why: "Callback language detected",
    });
  }

  return lowConfidenceUnknown(utterance, "Unclear gatekeeper intent");
}

export function classifyBridge(utterance) {
  const text = normalize(utterance);
  const toks = tokens(text);

  // Mixed-signal priority (from operator manual Part 8):
  // 1. Blocking objection  2. Pain/engagement  3. Soft maybe  4. Dead end
  // Check for objections first — a prospect saying "not interested" during BRIDGE
  // is an objection, not a bridge angle.
  const objScores = { timing: 0, interest: 0, info: 0, authority: 0 };
  for (const [bucket, config] of Object.entries(OBJECTION_BUCKETS)) {
    objScores[bucket] += countPhraseMatches(text, config.phrases) * 3;
    objScores[bucket] += countTokenMatches(toks, config.words) * 1.25;
  }
  const { winner: objWinner, winnerScore: objWinnerScore } = bestScoredKey(objScores);

  const scores = {
    missed_calls: 0,
    competition: 0,
    overwhelmed: 0,
  };

  // Phrase matches count more than token matches.
  for (const [angle, config] of Object.entries(BRIDGE_KEYWORDS)) {
    scores[angle] += countPhraseMatches(text, config.phrases) * 3;
    scores[angle] += countTokenMatches(toks, config.words) * 1.25;
  }

  // Tie-break nudges from strong signals.
  if (/\b(voicemail|callback|callbacks|staff|office|wife|receptionist)\b/.test(text)) {
    scores.missed_calls += 1.5;
  }
  if (/\b(slow|grow|growth|competitor|losing|market)\b/.test(text)) {
    scores.competition += 1.5;
  }
  if (/\b(busy|slammed|stretched|myself|everything)\b/.test(text)) {
    scores.overwhelmed += 1.5;
  }

  const { winner, winnerScore, runnerUpScore } = bestScoredKey(scores);

  // Mixed-signal rule: if both pain and objection present, objection wins
  // (handle the blocker first, pain is noted but doesn't advance the stage).
  // If objection signal is present and at least as strong as bridge, return objection.
  if (objWinnerScore > 0 && objWinnerScore >= winnerScore) {
    const confidence = objWinnerScore >= 5 ? 0.9 : objWinnerScore >= 3 ? 0.78 : 0.64;
    return makeResult(utterance, {
      confidence,
      objectionBucket: objWinner,
      why: `Objection during bridge: ${objWinner}`,
    });
  }

  if (winnerScore <= 0) {
    return makeResult(utterance, {
      confidence: 0.35,
      stageSuggestion: "BRIDGE",
      bridgeAngle: "fallback",
      why: "No clear bridge angle; use fallback question",
    });
  }

  const margin = winnerScore - runnerUpScore;

  if (margin < 1.25) {
    return makeResult(utterance, {
      confidence: 0.5,
      stageSuggestion: "BRIDGE",
      bridgeAngle: "fallback",
      why: `Bridge signals mixed (${winner} vs runner-up); use fallback question`,
    });
  }

  const confidence =
    winnerScore >= 5 ? 0.9 :
    winnerScore >= 3 ? 0.78 :
    0.66;

  return makeResult(utterance, {
    confidence,
    stageSuggestion: "BRIDGE",
    bridgeAngle: winner,
    why: `Bridge angle: ${winner}`,
  });
}

export function classifyQualifier(utterance) {
  const text = normalize(utterance);

  let painScore = 0;
  let noPainScore = 0;
  let unknownScore = 0;

  painScore += countPhraseMatches(text, QUALIFIER_PAIN_PHRASES) * 3;
  noPainScore += countPhraseMatches(text, QUALIFIER_NO_PAIN_PHRASES) * 3;
  unknownScore += countPhraseMatches(text, QUALIFIER_UNKNOWN_PHRASES) * 3;

  if (hasNumber(text)) painScore += 2.25;
  if (/\b(frustrat|losing|too many|lot)\b/.test(text)) painScore += 1.5;
  // Boost for loss/miss + temporal context (e.g., "lose calls on weekends")
  if (/\b(lose|miss|lost|missed)\b/.test(text) && /\b(weekends?|after hours|sometimes|evenings?|nights?|busy)\b/.test(text)) painScore += 1.75;
  if (/\b(few|covered|good|none)\b/.test(text)) noPainScore += 1.25;
  if (/\b(depends|unsure|idea)\b/.test(text)) unknownScore += 1.25;

  const scores = {
    pain: painScore,
    no_pain: noPainScore,
    unknown_pain: unknownScore,
    unknown: 0,
  };

  const { winner, winnerScore, runnerUpScore } = bestScoredKey(scores);

  if (winnerScore <= 0) {
    return makeResult(utterance, {
      confidence: 0.42,
      qualifierRead: "unknown_pain",
      why: "Qualifier answer vague; treat as unknown pain",
    });
  }

  const margin = winnerScore - runnerUpScore;
  const confidence =
    margin >= 2.5 ? 0.88 :
    margin >= 1.25 ? 0.72 :
    0.58;

  if (winner === "unknown" || confidence < 0.6) {
    return makeResult(utterance, {
      confidence: 0.58,
      qualifierRead: "unknown_pain",
      why: "Qualifier ambiguous; default to unknown pain path",
    });
  }

  return makeResult(utterance, {
    confidence,
    qualifierRead: winner === "unknown" ? "unknown_pain" : winner,
    why: `Qualifier read: ${winner}`,
  });
}

export function classifyObjectionOrClose(utterance) {
  const text = normalize(utterance);
  const toks = tokens(text);

  // Soft acceptance / booking language.
  if (countPhraseMatches(text, YES_PHRASES) > 0) {
    return makeResult(utterance, {
      confidence: 0.76,
      why: "Positive acceptance signal detected",
    });
  }

  if (countPhraseMatches(text, HEDGE_PHRASES) > 0) {
    return makeResult(utterance, {
      confidence: 0.68,
      why: "Hedge signal detected",
    });
  }

  const scores = {
    timing: 0,
    interest: 0,
    info: 0,
    authority: 0,
  };

  for (const [bucket, config] of Object.entries(OBJECTION_BUCKETS)) {
    scores[bucket] += countPhraseMatches(text, config.phrases) * 3;
    scores[bucket] += countTokenMatches(toks, config.words) * 1.25;
  }

  // Priority nudges.
  if (/\b(email|website|info)\b/.test(text)) scores.info += 1.25;
  if (/\b(decision|wife|partner|dispatcher)\b/.test(text)) scores.authority += 1.5;
  if (/\b(busy|later|tomorrow)\b/.test(text)) scores.timing += 1.25;
  if (/\b(interested|set|fine)\b/.test(text)) scores.interest += 1.0;

  const { winner, winnerScore, runnerUpScore } = bestScoredKey(scores);

  if (winnerScore <= 0) {
    // No objection signal — check for bridge/pain signals (OBJECTION recovery path)
    const bridgeResult = classifyBridge(utterance);
    if (bridgeResult.confidence >= 0.5 && (bridgeResult.bridgeAngle || bridgeResult.qualifierRead)) {
      return bridgeResult;
    }
    return lowConfidenceUnknown(utterance, "No clear objection bucket");
  }

  // Priority order for mixed signals:
  // authority > info > timing > interest
  const priority = ["authority", "info", "timing", "interest"];

  let resolvedWinner = winner;
  if (winnerScore - runnerUpScore < 1.0) {
    const tied = priority.filter((bucket) => scores[bucket] >= winnerScore - 0.25);
    resolvedWinner = tied[0] ?? winner;
  }

  const confidence =
    winnerScore >= 5 ? 0.9 :
    winnerScore >= 3 ? 0.78 :
    0.64;

  return makeResult(utterance, {
    confidence,
    objectionBucket: resolvedWinner,
    why: `Objection bucket: ${resolvedWinner}`,
  });
}

// -------------------------
// Convenience wrappers
// -------------------------

export function shouldCallLlmFallback(result) {
  return result.band === "low";
}

export function isUsableDeterministicResult(result) {
  return result.band === "high" || result.band === "medium";
}
