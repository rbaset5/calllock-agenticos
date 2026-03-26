---
id: DEC-2026-03-18-app-scope
domain: product
status: active
---

# CallLock App is customer-facing only

## Context
During product development, there was a tendency to add internal tools (outbound prospecting, pipeline management, operational dashboards) into the CallLock App codebase.

## Options Considered
- **Option A:** Build everything in the App — internal and external.
- **Option B:** Strict separation — App is customer-facing only, internal tools live elsewhere.

## Decision
Option B. The CallLock App (`web/`) is strictly for HVAC contractors reviewing their calls and managing their business. Internal tools use separate surfaces: Discord for outbound call lists and outcome logging, CLI for ops, separate admin surfaces if needed.

## Consequences
- Clear boundary: if a feature serves the founder/team, it doesn't go in `web/`.
- Discord becomes the primary internal operations surface.
- May need a dedicated admin app later, but Discord + CLI covers v1 needs.
