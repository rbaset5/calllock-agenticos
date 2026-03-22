---
id: DEC-2026-03-20-coolify-hetzner
domain: architecture
status: active
---

# Coolify deployment on Hetzner

## Context
Needed a deployment target for the Python harness that supports Docker, health checks, and is cost-effective for a pre-revenue startup.

## Options Considered
- **Option A:** Render (existing render.yaml in repo).
- **Option B:** Fly.io.
- **Option C:** Coolify on Hetzner VPS.

## Decision
Option C. Coolify on Hetzner. Dockerfile-based deployment with curl health check endpoint.

## Consequences
- Dockerfile must be built from repo root and copy `knowledge/` for taxonomy access.
- Health check uses curl (added to Dockerfile).
- Hetzner provides good price/performance for always-on services.
- render.yaml still exists in repo but is not the primary deployment path.
- Commits: `56e7ed2`, `398acf5`, `7995274`
