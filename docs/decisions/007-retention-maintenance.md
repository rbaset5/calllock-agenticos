# ADR 007: Retention Maintenance Pass

Status: Accepted

## Decision

This repository uses an explicit retention maintenance pass, triggered through the harness control plane, to apply configured cleanup rules.

Current scope:

- tenant-scoped artifact archival and deletion by age
- tenant-scoped customer-content deletion by age
- tenant-scoped audit-log deletion by age
- local JSONL trace and recovery journal pruning by age

## Rationale

- Retention should be visible, reportable, and auditable rather than hidden inside normal request handling.
- The maintenance pass gives operators a dry-run path and a durable audit event for cleanup actions.
- Retention execution should follow tenant-local windows instead of a single global maintenance hour.

## Current Limits

- Local trace and recovery pruning is global, not tenant-differentiated.
