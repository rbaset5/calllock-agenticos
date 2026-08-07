---
id: product-architecture
title: Product Architecture
graph: product
owner: platform
last_reviewed: 2026-06-11
trust_level: curated
progressive_disclosure:
  summary_tokens: 140
  full_tokens: 320
---

# Architecture

The product consists of a shared product core, a voice runtime that remains on Retell AI, and a harness layer for orchestration, policy, context, evals, production assurance, and improvement. The full source of truth is the architecture spec in `docs/superpowers/specs/2026-03-12-calllock-agentos-architecture-design.md`.

The current voice production layer hangs durable evidence off the root `call_records` row: normalized Retell call events, tool calls, config snapshots, safety findings, and idempotent debug packets. Weekly production reporting reads those records to identify the top fix and expose a conservative migration gate; it does not treat missing owned STT/TTS runtime as a defect while Retell remains the intended live-call boundary.
