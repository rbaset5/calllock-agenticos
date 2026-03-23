---
id: DEC-2026-03-17-voice-migration
domain: voice-pipeline
status: active
---

# Voice pipeline migrated into rabat monorepo

## Context
The voice agent pipeline was a standalone Express service (valencia v10). It needed access to tenant isolation (RLS), HVAC taxonomy (industry packs), growth memory, and Inngest fan-out — all of which live in rabat.

## Options Considered
- **Option A:** Keep valencia standalone and add API bridges to rabat services.
- **Option B:** Migrate voice into rabat as a peer module inside `harness/src/voice/`.

## Decision
Option B. Full migration into rabat. Real-time tool handlers remain simple FastAPI endpoints separate from the LangGraph supervisor; heavyweight orchestration runs post-call via Inngest.

## Consequences
- Voice is now `harness/src/voice/` — a peer module, not a separate service.
- Single deployment target (Coolify on Hetzner).
- Valencia repo is archived.
- CallLock App migration was unblocked (depends on voice's data layer being in place).
