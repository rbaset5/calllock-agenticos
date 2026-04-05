---
id: DEC-2026-04-04-sms-postponed
domain: product
status: active
---

# SMS follow-ups postponed; callback cadence replaces

## Context
Post-call iMessage follow-ups (followup.py) are live but depend on macOS Messages.app + AppleScript via the `imsg` CLI. This is fragile for production: requires full disk access, breaks if Messages isn't running, and has no cloud fallback. Sprint velocity is better served by a reliable callback cadence than flaky text messages.

## Options Considered
- **Option A:** Keep iMessage follow-ups live, add Twilio SMS as fallback.
- **Option B:** Postpone all SMS/iMessage follow-ups. Replace with a structured 3-attempt callback cadence enforced by the lifecycle sweep, using existing sprint blocks (MID/EOD) for callback attempts.
- **Option C:** Remove follow-up code entirely.

## Decision
Option B. Postpone SMS follow-ups. The iMessage follow-up path remains in code but is not triggered. Callback cadence is the primary follow-up mechanism for sprint calls.

## Callback Cadence (3-attempt rule)
| Attempt | Timing | Sprint Block | On No Answer |
|---------|--------|--------------|--------------|
| 1 | Same day or next business day | MID block | Log voicemail, set next_action_date +1 day |
| 2 | +1 business day after attempt 1 | MID block | Second voicemail, set next_action_date +2 days |
| 3 | +2 business days after attempt 2 | EOD block | Final attempt at different time-of-day |
| After 3 strikes | Automatic | Lifecycle sweep | Disqualify as unreachable (existing Rule 2) |

Callbacks due today are prioritized above fresh dials in MID block queue ordering.

## Consequences
- `followup.py` iMessage send path is dormant (Inngest event still fires but follow-up is skipped).
- Lifecycle Rule 1 tightened: overdue callbacks re-queue after 1 day (was 3 days).
- Sprint schedule gains a `callback_cadence` config section read by daily_plan.py.
- SMS/iMessage follow-ups will be revisited when Twilio SMS is production-ready (v2).
