---
id: DEC-2026-03-19-phone-tenant-fallback
domain: voice-pipeline
status: active
---

# Phone-to-tenant fallback for calls without custom_metadata

## Context
Some calls arrive at the post-call webhook without `custom_metadata.tenant_id` set. Without tenant resolution, the call can't be stored (RLS blocks it).

## Options Considered
- **Option A:** Reject calls without tenant metadata (data loss).
- **Option B:** Look up tenant by the called phone number as a fallback.

## Decision
Option B. If `custom_metadata.tenant_id` is absent, resolve tenant by matching the called phone number against the `tenant_phone_numbers` table.

## Consequences
- No call is silently dropped for missing metadata.
- Requires `tenant_phone_numbers` table to be kept up to date.
- If a phone number maps to multiple tenants (shared number), this is ambiguous — currently picks first match. Acceptable for now since each tenant has unique numbers.
- Commit: `edc2d94`
