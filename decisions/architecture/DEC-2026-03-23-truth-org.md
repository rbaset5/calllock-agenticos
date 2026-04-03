---
id: DEC-2026-03-23-truth-org
domain: architecture
status: active
---

# Truth org and voice worker split

## Context
The repo needs a clear operating split before detection work starts. The legacy `eng-ai-voice` role still mixes builder and judge behavior, while the next detection slice needs a stable voice execution owner and a separate truth owner. The founder control surface and detection plans also depend on a fixed ordering for which constitutional eval loops become binding first.

## Decision
- The active operating split is `Program`, `Execution`, `Truth`, and `Governance`.
- Execution workers may investigate, prepare candidates, and propose changes, but they may not certify their own work.
- The legacy `eng-ai-voice` role becomes a transitional compatibility worker and is replaced operationally by:
  - `voice-builder` for voice execution and investigation work
  - `voice-truth` for locked evaluation, canary review, and constitutional pass/block/escalate output
- `eng-product-qa` remains a cross-surface validation worker that consumes truth outputs; it does not own the voice truth verdict.
- Active constitutional eval-loop order is:
  - `voice` first
  - `app` second
  - `outbound` third
- Founder override is allowed only as an explicit governance action with written evidence. An override may change what proceeds, but it does not rewrite or suppress the underlying truth result.

## Consequences
- Detection-triggered voice investigations can route to `voice-builder` without collapsing builder and judge authority.
- Voice shipping quality is certified by `voice-truth`, not by the execution worker that proposed the change.
- The repo keeps `eng-ai-voice` for compatibility while new planning and routing work moves to the split roles.
- Future app and outbound truth loops should follow the same separation once their locked contracts are ready.
