# CallLock AgentOS Conventions

## Monorepo Layout

- `knowledge/` stores markdown and YAML source-of-truth documents.
- `harness/` stores the Python LangGraph-oriented runtime.
- `inngest/` stores TypeScript event schemas and functions.
- `supabase/` stores SQL migrations and seed data.
- `scripts/` stores repository validation and extraction utilities.

## Knowledge Files

Every markdown knowledge node must include frontmatter with:

- `id`
- `title`
- `graph`
- `owner`
- `last_reviewed`
- `trust_level`
- `progressive_disclosure`

Wiki links use `[[path]]` syntax and resolve relative to `knowledge/`, for example `[[company/mission]]` -> `knowledge/company/mission.md`.

Each knowledge directory with child nodes must expose an `_moc.md` file linking to those child nodes.

## Worker Specs and Packs

- Worker specs live in `knowledge/worker-specs/` and use the standard schema in YAML.
- Industry packs live under `knowledge/industry-packs/<pack-id>/`.
- Changes to worker specs or packs must pass the repository validation scripts before merge.

## Tenant Isolation

- Tenant-scoped database operations use `set_config('app.current_tenant', tenant_id, true)`.
- RLS is enabled and forced on all tenant-scoped tables.
- Cache keys must be tenant-namespaced.

## Compliance Graph

Compliance rules are database-backed in Supabase, not file-backed markdown. Markdown compliance content documents policy intent; runtime compliance rules live in SQL seed data.

## Runtime Split

- Python harness for orchestration, context assembly, policy gate, verification, and persistence.
- TypeScript only where it interfaces with Inngest or repository validation/extraction.
