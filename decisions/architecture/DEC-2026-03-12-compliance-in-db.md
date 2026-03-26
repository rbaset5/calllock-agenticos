---
id: DEC-2026-03-12-compliance-in-db
domain: architecture
status: active
---

# Compliance rules in Supabase, not markdown

## Context
Compliance rules (required disclosures, forbidden claims, licensing requirements) need to be enforced at runtime by the voice agent and post-call verification. They also need to be queryable and tenant-scoped.

## Options Considered
- **Option A:** Compliance rules as markdown files in `knowledge/compliance/` — agent reads them.
- **Option B:** Compliance rules as SQL seed data in Supabase — queryable, tenant-scoped, version-controlled via migrations.

## Decision
Option B. Markdown compliance content documents policy intent (human-readable reference). Runtime compliance rules live in SQL seed data (machine-enforceable).

## Consequences
- Two representations of compliance: markdown for intent, SQL for enforcement.
- Changes to compliance rules require both a markdown update (for human understanding) and a SQL migration (for runtime enforcement).
- RLS ensures tenant-scoped compliance rules.
