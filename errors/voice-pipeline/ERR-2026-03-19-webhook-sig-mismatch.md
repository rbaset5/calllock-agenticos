---
id: ERR-2026-03-19-webhook-sig-mismatch
domain: voice-pipeline
occurrences: 1
status: resolved
---

# Retell webhook signature mismatch

## Symptoms
All incoming Retell webhooks rejected with 401 — signature verification failing despite correct API key configuration.

## Root Cause
Retell's actual webhook signature format differs from what their documentation describes. The HMAC computation uses a different encoding/ordering than documented.

## Fix
Updated signature verification to match Retell's actual format.
Commit: `4026e77`

## Pattern Notes
Don't trust Retell's webhook docs at face value. When signature verification fails, inspect the raw headers and compare against their actual implementation, not their docs.
