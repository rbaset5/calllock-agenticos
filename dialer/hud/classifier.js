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
  return normalize(text).includes(normalize(phrase));
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
    words: ["email", "website", "info"],
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
  'what company', 'what are you selling', 'what is this about',
];

const WRONG_PERSON_PHRASES = [
  "i don't handle that", 'talk to my wife', 'talk to my partner',
  'talk to my husband', 'talk to dispatcher', 'wrong person',
  "i'm the tech", "i'm the helper", 'not my decision',
  "owner isn't here", "he's not here", "she's not here",
  'my husband handles', 'my wife handles', 'he handles that',
  'she handles that', 'husband handles', 'wife handles',
];

const PRICING_QUESTION_PHRASES = [
  'how much', "what's the cost", 'pricing', 'what do you charge', 'price range',
  'how much does it cost', 'what does it cost',
];

const PRICING_RESISTANCE_PHRASES = [
  'expensive', "can't afford", 'too much', 'not worth it', 'out of budget',
  'costs too much', "don't have the budget",
];

const YES_PHRASES = [
  "yeah",
  "yes",
  "sure",
  "okay",
  "ok",
  "that works",
  "sounds good",
  "thursday works",
  "friday works",
];

const HEDGE_PHRASES = [
  "maybe",
  "let me think",
  "not sure",
  "i guess",
  "possibly",
];

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

  // Check curiosity / engagement (helps advance from OPENER)
  const CURIOSITY_PHRASES = ['how does that work', 'tell me more', 'that sounds interesting', 'how would that work', 'what does that mean'];
  const curHits = countPhraseMatches(text, CURIOSITY_PHRASES);
  if (curHits > 0) {
    const stageBoost = ['OPENER', 'PERMISSION_MOMENT'].includes(stage) ? 0.1 : 0;
    return { intent: 'curiosity', confidence: clamp01(0.65 + stageBoost + (curHits - 1) * 0.08) };
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
    case "BRIDGE":
      return classifyBridge(utterance);

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
