# Decisions Index

Structured decision records for CallLock AgentOS. Check here before proposing changes to voice pipeline, product, or architecture.

## Voice Pipeline

- [Disable supervisor in post-call pipeline](voice-pipeline/DEC-2026-03-20-disable-supervisor.md) — OOMs and quarantines; run extraction directly
- [Extract from Retell tool call arguments](voice-pipeline/DEC-2026-03-20-extract-from-tool-calls.md) — structured data lives in tool_call args, not free-text transcript
- [Fetch full call from Retell API before extraction](voice-pipeline/DEC-2026-03-21-fetch-full-call.md) — webhook payload is incomplete; always fetch
- [Voice pipeline migrated into rabat](voice-pipeline/DEC-2026-03-17-voice-migration.md) — consolidated from standalone valencia service
- [Phone-to-tenant fallback](voice-pipeline/DEC-2026-03-19-phone-tenant-fallback.md) — calls without custom_metadata resolve tenant by phone number

## Product

- [CallLock App is customer-facing only](product/DEC-2026-03-18-app-scope.md) — internal tools go elsewhere
- [Terminology: App not Dashboard](product/DEC-2026-03-18-terminology.md) — never call the CallLock App "the dashboard"
- [Outbound pipeline is single-worker Scout](product/DEC-2026-03-21-outbound-single-worker.md) — eliminated Composer, deferred email to v2
- [SMS follow-ups postponed; callback cadence replaces](product/DEC-2026-04-04-sms-postponed.md) — iMessage dormant, 3-attempt callback cadence enforced via lifecycle sweep

## Architecture

- [Python/TypeScript runtime split](architecture/DEC-2026-03-12-runtime-split.md) — Python for orchestration, TypeScript only for Inngest/validation
- [Compliance rules in Supabase not markdown](architecture/DEC-2026-03-12-compliance-in-db.md) — markdown documents intent, SQL is runtime
- [Coolify deployment on Hetzner](architecture/DEC-2026-03-20-coolify-hetzner.md) — Dockerfile-based deployment with health check
- [Discord as bidirectional context interface](architecture/DEC-2026-03-22-discord-gateway.md) — hermes-agent gateway for decomposition loop via Discord
