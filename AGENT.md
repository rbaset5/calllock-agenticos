# CallLock AgentOS — Agent Instructions

This file is the single source of truth for any AI agent working in this repo.
Tool-specific files (CLAUDE.md, GEMINI.md, CODEX.md) point here plus add tool-specific overrides.

---

## Monorepo Layout

- `knowledge/` — markdown and YAML source-of-truth documents (domain knowledge, worker specs, industry packs)
- `harness/` — Python LangGraph-oriented runtime (orchestration, context assembly, policy gate, verification, persistence)
- `inngest/` — TypeScript event schemas and Inngest functions
- `supabase/` — SQL migrations and seed data
- `scripts/` — repository validation and extraction utilities
- `web/` — CallLock App (customer-facing Next.js application — never call it "the dashboard")
- `office-dashboard/` — internal 3D agent visualization (separate from customer-facing app)
- `evals/` — evaluation harnesses and rubrics
- `plans/` — implementation plans
- `docs/` — specs and design documents
- `decisions/` — structured decision records (check before proposing changes)
- `errors/` — error pattern log (check before debugging)
- `kb/` — LLM-compiled research wiki (competitors, voice AI, sales playbooks). See "How to Use kb/" below.

## How to Navigate knowledge/

1. Start at `knowledge/_moc.md` — this is the root index.
2. Follow `[[wiki-links]]` which resolve relative to `knowledge/` (e.g., `[[company/mission]]` -> `knowledge/company/mission.md`).
3. Each subdirectory has its own `_moc.md` linking to child nodes.
4. Respect `progressive_disclosure` frontmatter — pull only what's relevant to avoid token bloat.
5. Every knowledge file must include frontmatter: `id`, `title`, `graph`, `owner`, `last_reviewed`, `trust_level`, `progressive_disclosure`.

## How to Use decisions/

**Before proposing any change to voice pipeline, product, or architecture, check `decisions/_index.md`.**

- Decisions are never deleted — superseded ones link to their replacement.
- If your proposed change conflicts with an active decision, surface the conflict explicitly.
- If no prior decision exists, suggest creating one as part of the change.

## How to Use errors/

**Before investigating a bug or unexpected behavior, check `errors/_index.md`.**

- If a matching error exists, read it before proposing a fix.
- If your fix resolves an existing logged error, update its status.
- If a pattern recurs 3+ times, extract a rule into `decisions/` or update the relevant `knowledge/` file.

## How to Use kb/

The `kb/` directory is an LLM-compiled research wiki — separate from the curated `knowledge/` system.

- `kb/raw/` contains immutable source documents. The LLM reads but never modifies these.
- `kb/wiki/` contains LLM-compiled articles organized into dossier types: `positioning/`, `product/`, `competitors/`, `playbooks/`, `marketing/`, `voice-ai/`.
- Start at `kb/wiki/_index.md` for a catalog of all articles.
- Use `/kb-ingest` to process new raw sources into wiki articles.
- Use `/kb-query` to ask research questions against the wiki.
- Use `/kb-status` to check wiki health and size.
- Articles use `[[wiki-links]]` that resolve within `kb/wiki/`. To reference curated knowledge, use relative paths like `[[../../knowledge/product/overview]]`.
- The wiki is the LLM's domain — users rarely edit it directly.

### Canon vs. Derived in kb/wiki/

Not all dossiers are equal. Changes to canon ripple through derived artifacts; changes to derived artifacts do not affect canon.

- **Canon** (source of truth — everything else inherits from these):
  - `positioning/` — ICP, Dunford framework, category, wedge, messaging foundations
  - `product/` — what CallLock *is* (feature set, offering, pitch)

- **Derived / research / operational** (inherit from canon — safe to churn):
  - `competitors/` — market intelligence, not authored positioning
  - `playbooks/` — operational scripts derived from positioning
  - `marketing/` — homepage, ads, emails, landing pages (outputs derived from canon)
  - `voice-ai/` — technical research

**Rule (forward ripple-check):** When you change anything in `positioning/` or `product/`, grep every file in `competitors/`, `playbooks/`, `marketing/` for phrases that may have drifted, and fix them in the same commit. When you change a derived file, canon is unaffected.

**Rule (reverse ripple-check — fix canon first):** When drafting a derived artifact exposes a claim that isn't in canon, contradicts canon, or surfaces a new insight about the market/positioning/product, **stop and fix canon first.** Then re-sync the derived artifact against the corrected canon. Do not patch the derived artifact and leave canon drifting — next time someone drafts a different derived artifact from the same canon, they'll hit the same gap.

**Pattern: drafting derived artifacts is a canon stress-test.** Writing marketing copy, playbooks, or other derived artifacts is the single best way to surface gaps and drift in canon — because it forces you to put claims into sentences and defend them. Treat every drafting session as an opportunity to audit and improve canon, not just an opportunity to produce the derived artifact. If a derived draft produced more canon improvements than it did derived content, that's a feature, not a failure.

## Decomposition Protocol

When a new problem arrives (bug, feature, feedback, idea):

1. **Clarify** — What is the actual problem vs. symptom? What outcome do we want? What constraints apply?
2. **Check existing context** — Search `decisions/`, `errors/`, and `knowledge/` for prior art.
3. **Capture** — Write lightweight updates to the appropriate files:
   - New trade-off or conclusion → `decisions/`
   - Domain knowledge update → `knowledge/`
   - Error pattern → `errors/`
   - Agent instruction change → this file (`AGENT.md`)
4. **Execute** — Act on the now-clarified, context-rich problem.
5. **Synthesize** — After execution, update context files with what was learned.

## Worker Specs and Packs

- Worker specs live in `knowledge/worker-specs/` and use the standard YAML schema.
- Industry packs live under `knowledge/industry-packs/<pack-id>/`.
- Changes to worker specs or packs must pass validation scripts before merge.

## Tenant Isolation

- Tenant-scoped database operations use `set_config('app.current_tenant', tenant_id, true)`.
- RLS is enabled and forced on all tenant-scoped tables.
- Cache keys must be tenant-namespaced.

## Compliance Graph

Compliance rules are database-backed in Supabase, not file-backed markdown. Markdown compliance content documents policy intent; runtime compliance rules live in SQL seed data.

## Runtime Split

- **Python** (harness/) — orchestration, context assembly, policy gate, verification, persistence.
- **TypeScript** (inngest/, scripts/) — only where it interfaces with Inngest or repository validation/extraction.
- **Next.js** (web/) — customer-facing CallLock App only. Internal tools go elsewhere (Discord, CLI, separate admin surfaces).

## Discord Interface (CEO Agent Gateway)

The founder controls the agent organization and context system through Discord via a hermes-agent gateway (`harness/src/hermes_gateway/`).

**Two Discord systems coexist:**
1. **Gateway (bidirectional)** — hermes-agent bot handles conversation, tool calls, decomposition loop. Founder posts in #incoming, bot decomposes to repo files.
2. **Projector (one-way)** — Inngest webhook projector (`inngest/src/functions/discord-projector.ts`) streams agent events (state changes, verifications, health checks) to Discord channels.

**Channel layout:**
- `#incoming` — founder posts problems/ideas, bot decomposes and routes
- `#decisions` — bot posts decision summaries when created/updated
- `#errors` — bot posts error patterns when logged/bumped
- `#outbound-calls` — daily call list + outcome logging
- `#skills` — skill candidate detection + promotion
- `#health-checks` — guardian health status
- DM with bot — private commands (dispatch, approve, query)

**Context tools available via gateway:**
- `decompose_problem` — first tool to run on any new input; checks prior art
- `check_decisions` / `create_decision` — search and write decision records
- `check_errors` / `log_error` — search and write error patterns
- `update_knowledge` — write to knowledge/ files

## Key Constraints

- The CallLock App (`web/`) is strictly customer-facing. Internal tools (outbound, ops, analytics) must NOT live in the App.
- Never call the CallLock App "the dashboard" — it's an app that contractors use to review calls and manage their business.
