// dialer/hud/llm.js — Groq LLM fallback client
// Vanilla JS ES module — no build step, no TypeScript.

// Cache 503 status to avoid repeated network round-trips.
// After a 503, skip the fetch for 30s before retrying.
let _lastFailureAt = 0;
const FAILURE_BACKOFF_MS = 30_000;

/**
 * Call the server-side Groq classify endpoint.
 * Returns the parsed classification or null on error/timeout.
 * Does NOT dispatch to reducer — the caller in ui.js handles that.
 *
 * @param {string} utterance
 * @param {string} stage
 * @param {{ bridgeAngle?: string, lastObjectionBucket?: string }} context
 * @param {*} utteranceId
 * @returns {Promise<object|null>}
 */
/**
 * Returns true if the LLM endpoint is in backoff (recent 503/502).
 * When true, callers should skip the async fallback and promote rules
 * results synchronously to avoid race conditions with fast transcripts.
 */
export function isLlmBackoffActive() {
  return _lastFailureAt > 0 && (Date.now() - _lastFailureAt) < FAILURE_BACKOFF_MS;
}

export async function classifyWithLlm(utterance, stage, context, utteranceId) {
  // Skip network call if we got a 503 recently — fall through immediately
  if (_lastFailureAt > 0 && (Date.now() - _lastFailureAt) < FAILURE_BACKOFF_MS) {
    return null;
  }

  try {
    const res = await fetch('/hud/groq-classify', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        utterance,
        stage,
        bridgeAngle: context.bridgeAngle ?? undefined,
        lastObjectionBucket: context.lastObjectionBucket ?? undefined,
        utteranceId,
        requestTone: true,
        requestSecondaryIntent: true,
      }),
    });

    if (!res.ok) {
      console.warn('[hud/llm] Server returned', res.status);
      if (res.status === 503 || res.status === 502) {
        _lastFailureAt = Date.now();
      }
      return null;
    }

    const data = await res.json();

    if (data.error) {
      console.warn('[hud/llm] Server returned error flag');
      return null;
    }

    // Attach optional extended fields when the server provides them.
    // Validate tone against known labels to prevent silent mismatches.
    const VALID_TONES = ['rushed', 'skeptical', 'annoyed', 'curious', 'guarded', 'neutral', 'unknown'];
    if (data.tone && VALID_TONES.includes(data.tone)) {
      data.tone_confidence = data.tone_confidence || 0.5;
      data.tone_source = 'llm_refined';
    } else {
      delete data.tone;
    }
    if (data.secondary_intent) {
      data.secondary_confidence = data.secondary_confidence || 0.5;
    }

    return data;
  } catch (err) {
    console.error('[hud/llm] Fetch failed:', err.message);
    _lastFailureAt = Date.now();
    return null;
  }
}
