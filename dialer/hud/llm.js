// dialer/hud/llm.js — Groq LLM fallback client
// Vanilla JS ES module — no build step, no TypeScript.

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
export async function classifyWithLlm(utterance, stage, context, utteranceId) {
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
      return null;
    }

    const data = await res.json();

    if (data.error) {
      console.warn('[hud/llm] Server returned error flag');
      return null;
    }

    // Attach optional extended fields when the server provides them.
    if (data.tone) {
      data.tone_confidence = data.tone_confidence || 0.5;
      data.tone_source = 'llm_refined';
    }
    if (data.secondary_intent) {
      data.secondary_confidence = data.secondary_confidence || 0.5;
    }

    return data;
  } catch (err) {
    console.error('[hud/llm] Fetch failed:', err.message);
    return null;
  }
}
