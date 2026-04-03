---
id: worker-specs-moc
title: Worker Spec Library
graph: worker-specs
owner: platform
last_reviewed: 2026-03-24
trust_level: curated
progressive_disclosure:
  summary_tokens: 60
  full_tokens: 140
---

# Worker Specs

- `eng-product-qa.yaml` — cross-surface QA and seam validation worker; consumes truth outputs and coordinates early detection triage
- `eng-ai-voice.yaml` — deprecated compatibility alias retained only for legacy references during the voice split migration
- `voice-builder.yaml` — execution worker for voice investigations and candidate generation
- `voice-truth.yaml` — truth worker for locked evals, canary review, and pass/block/escalate verdicts
- `eng-app.yaml` — app validation worker for rendering, realtime, and browser-based verification
- `eng-fullstack.yaml` — implementation worker for app and seam fixes routed from guardian issues
- `product-manager.yaml`
- `engineer.yaml`
- `designer.yaml`
- `product-marketer.yaml`
- `customer-analyst.yaml`
- `outbound-scout.yaml` — outbound workflow execution worker for prospecting and probing
