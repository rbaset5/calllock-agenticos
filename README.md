# CallLock AgentOS

CallLock AgentOS is a greenfield monorepo for the multi-tenant harness described in the architecture spec. It combines a Python orchestration service, TypeScript Inngest event wiring, file-backed knowledge graphs, industry packs, and Supabase-backed tenant/compliance data.

## Layout

- `knowledge/`: markdown and YAML knowledge graphs, worker specs, and industry packs
- `harness/`: Python harness runtime, health server, cache/db helpers, and worker orchestration
- `inngest/`: TypeScript event schemas and functions for Express V2 -> harness triggers
- `supabase/`: migrations and seed data for tenants, configs, jobs, and compliance rules
- `infra/`: deploy assets such as the LiteLLM proxy
- `scripts/`: validation and extraction scripts
- `tests/`: integration coverage for repository-level checks
- `plans/`: execution plans for Phases 1-4

## Phase Scope

This repository now contains the initial implementation for Phases 1-2:

- project scaffold and CI
- knowledge substrate and worker specs
- tenant schema, compliance schema, and RLS policies
- harness runtime skeleton with policy, context, verification, and persistence stages
- Inngest trigger stubs
- HVAC pack extraction/validation path

## Getting Started

### Python harness

```bash
cd harness
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pytest
```

### Validation scripts

```bash
node scripts/validate-knowledge.ts
node scripts/validate-worker-specs.ts
node scripts/validate-packs.ts
```

### Local extraction

```bash
node scripts/extract-hvac-pack.ts
```

The extraction script reads from the local V2 source tree under `retellai-calllock/madrid/V2` by default and can be overridden with `CALLLOCK_V2_ROOT`.
