---
id: feature-voice-agent
title: Voice Agent
graph: product
owner: voice
last_reviewed: 2026-06-11
trust_level: curated
progressive_disclosure:
  summary_tokens: 110
  full_tokens: 260
---

# Voice Agent

Retell AI remains the real-time voice runtime. The live system uses a 10-state FSM and GPT-4o. The harness does not replace the call runtime; it orchestrates follow-up work and production assurance around it.

The production assurance layer records Retell call events, tool calls, and config snapshots, then builds operator debug packets for each completed call. Post-call processing runs deterministic safety checks for fake booking claims, callback promises without callback evidence, emergency mishandling, missing tenant context, and tool failures or unknown timeouts.

The voice eval suite now requires at least 50 golden-set calls and can assert expected safety findings as well as extraction fields. Operators can run `python scripts/run-voice-eval.py` for eval health and `python scripts/run-voice-production-report.py --days 7` for the weekly production report. The report summarizes call volume, bookings, callbacks, safety findings, tool failures and latency, extraction drift, unresolved findings, the top recommended fix, and a conservative Retell migration gate.
