# CallLock AgentOS — Claude Instructions

Read and follow `AGENT.md` in this repo root. It is the single source of truth for all project conventions, navigation, and domain context.

## Claude-Specific Overrides

- Before proposing changes to voice pipeline, product, or architecture, check `decisions/_index.md`.
- Before debugging, check `errors/_index.md` for known patterns.
- Skills and memory pointers are managed via Claude Code's built-in memory system — they complement, not replace, the repo-based context in `AGENT.md`, `decisions/`, and `errors/`.
- When updating agent instructions, update `AGENT.md` (not this file) unless the change is Claude-specific.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review

## Deploy Configuration (configured by /setup-deploy)
- Platform: Coolify (harness only — dialer runs locally)
- Harness production URL: http://ls5e6qqlb3wl1jesk21ds2zb.89.167.116.18.sslip.io
- Harness health check: /health (returns JSON with service status)
- Dialer (HUD): localhost:3004 only — not yet deployed to production
- Deploy workflow: Coolify auto-deploy on push to main (harness)
- Merge method: squash
- Project type: web app (voice pipeline + sales HUD)

### Custom deploy hooks
- Pre-merge: none
- Deploy trigger: automatic on push to main (Coolify webhook for harness)
- Deploy status: curl harness /health endpoint
- Health check: http://ls5e6qqlb3wl1jesk21ds2zb.89.167.116.18.sslip.io/health
