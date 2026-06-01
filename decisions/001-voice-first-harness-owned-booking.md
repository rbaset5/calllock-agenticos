# Decision 001: Voice-First Harness-Owned Booking

**Date:** 2026-06-01
**Status:** Accepted

## Context

CallLock is a voice-first call rescue product. The client keeps their existing business number; staff get the first chance to answer during business hours, and unanswered or after-hours calls forward to CallLock before voicemail.

The previous voice migration plan kept `book_service` on the CallLock App and left service-area checks partly in the Retell prompt. That puts the riskiest customer-facing write path outside the harness policy layer.

## Decision

Retell remains the short-term live speech runtime, but the Python harness owns operational decisions:

- `book_service` writes bookings through the harness.
- Service-area validation runs in harness code before booking.
- Failed or blocked booking routes through deterministic fallback policy.
- Retell tool URLs point at `/webhook/retell/*` on the harness service.
- SMS is allowed for owner notifications, but it is not the core customer-facing product path.

## Consequences

- The CallLock App reads and manages voice data; it does not own the live booking write path.
- Retell prompts can collect intent and speak naturally, but cannot improvise booking/fallback policy.
- Future deterministic-controller work can replace Retell without changing the booking and fallback interfaces.
