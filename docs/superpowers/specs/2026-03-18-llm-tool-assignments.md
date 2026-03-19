# LLM Tool Assignments — Agent-to-Model Routing

**Date:** 2026-03-18
**Status:** Draft
**Author:** Rashid Baset + Claude
**Depends on:** `2026-03-17-corporate-hierarchy-agent-roster.md`

## Design Principles

1. **Director Escalates** — Every department director runs on a high-tier model. Workers run on the cheapest model that can handle the job. When a worker produces low-confidence output, the director re-runs on their own (stronger) model.
2. **Context-dependent routing** — Some agents switch models based on what they're doing (sensitive repos, production data, multi-client setups). The routing table below captures both the default and the conditional overrides.
3. **Cost optimization** — The goal is minimum viable model per task. Executives justify their cost through decision authority; workers justify theirs through volume.
4. **Default-safe posture** — If context flags are missing or ambiguous, any operation that **writes** or **calls external tools** drops to NanoClaw (not ZeroClaw). Read-only operations may stay on the cheaper default. Fail closed, not open.
5. **Department-level defaults** — Worker specs inherit a department model group unless explicitly overridden. This reduces YAML drift as models evolve.
6. **Audit every call** — Every LLM invocation is tagged with `agent_id`, `llm_model` (alias), `override_fired` (bool), and `escalation_depth` (0=worker, 1=director, 2=exec). This is non-negotiable for proving which agent did what.

## Model Palette

| Model | Alias | Strength | Cost Tier | Best For |
|---|---|---|---|---|
| Claude Opus | `claude-opus` | Deep reasoning, strategy, compliance, nuanced judgment | $$$$ | Executives, legal, final decisions |
| Claude Sonnet | `claude-sonnet` | Strong reasoning, creative judgment, quality gate | $$$ | Directors, design, escalation reviews |
| Codex | `codex` | Code generation, scripts, batch engineering tasks | $$ | Engineering workers, growth engineering |
| Gemini 3 Flash | `gemini-flash` | Long context windows, structured outputs, summarization | $$ | Data analysis, research synthesis, structured reports |
| MiniMax | `minimax` | Audio/voice generation, multimodal | $$ | Voice agent design, audio testing |
| Qwen | `qwen` | Strong open-source, code, multilingual | $ | Routine ops, test scripts, troubleshooting |
| OpenClaw | `openclaw` | Orchestration hub with rich integrations, weaker isolation | $$ | Multi-tool workflows, content pipelines requiring external integrations |
| ZeroClaw | `zeroclaw` | Cheap agent spin-up, embedded agents, content ops default | $ | CRO experiments, small-service lifecycle, content ops |
| NanoClaw | `nanoclaw` | Sensitive/production contexts, multi-client isolation | $ | Sensitive repos, production data, agency setups |
| NotebookLM | `notebooklm` | Slide generation, document synthesis | $ | Invocable tool (not agent-bound) |
| OpenRouter Free | `openrouter-free` | Templated tasks, classification, formatting | Free | SDR outreach, routine check-ins |

## Static Assignments

### Executive Suite

| Agent | ID | Default Model | Rationale |
|---|---|---|---|
| CEO / Founder | `exec-ceo` | `claude-opus` | Highest-stakes decisions, strategy, closing |
| CPO | `exec-cpo` | `claude-opus` | Product strategy, pricing, value prop |
| CTO | `exec-cto` | `claude-opus` | Architecture decisions, reliability calls |
| COO | `exec-coo` | `claude-opus` | Operations, compliance, churn prevention |

### Product Management

| Agent | ID | Default Model | Rationale |
|---|---|---|---|
| Head of Product | `pm-product-strategy` | `claude-sonnet` | Director — escalation gate for product dept |
| PM Discovery | `pm-product-discovery` | `gemini-flash` | Long-context research synthesis, ideation |
| PO Execution | `pm-execution` | `gemini-flash` | Structured outputs (PRDs, tickets, roadmaps) |
| Market Researcher | `pm-market-research` | `gemini-flash` | Long-context market analysis, persona synthesis |
| Product Data Analyst | `pm-data-analytics` | `gemini-flash` | Structured data, cohort analysis, long context |
| ProdOps Manager | `pm-toolkit` | `qwen` | Routine ops, coordination, templating |
| Lead UI/UX Designer | `pm-designer` | `claude-sonnet` | Creative judgment, visual reasoning |

### Engineering

| Agent | ID | Default Model | Rationale |
|---|---|---|---|
| VP Engineering | `eng-vp` | `claude-sonnet` | Director — escalation gate for engineering |
| AI/Voice Engineer | `eng-ai-voice` | `minimax` | Voice/audio is core product; see conditional below |
| Full-Stack Developer | `eng-fullstack` | `codex` | Code generation, batch tasks, APIs |
| Product QA | `eng-product-qa` | `qwen` | Test scripts, repetitive validation |

### Growth Marketing

| Agent | ID | Default Model | Rationale |
|---|---|---|---|
| Head of Growth | `growth-head` | `claude-sonnet` | Director — escalation gate for growth dept |
| CRO Specialist | `growth-cro` | `zeroclaw` | Default: cheap test agent spin-up; see conditional |
| Content & Copy | `growth-content` | `zeroclaw` | Default for content ops; see conditional |
| Growth Engineer | `growth-engineer` | `codex` | Landing pages, A/B test code, rapid builds |
| Lifecycle/Retention | `growth-lifecycle` | `zeroclaw` | Default: embedded agents in small services; see conditional |
| Growth/Data Analyst | `growth-analyst` | `gemini-flash` | Full-funnel analytics, structured reports |

### Sales

| Agent | ID | Default Model | Rationale |
|---|---|---|---|
| SDR / Lead Router | `sales-sdr` | `openrouter-free` | Templated outreach, lead classification |

### Customer Success

| Agent | ID | Default Model | Rationale |
|---|---|---|---|
| Head of CS | `cs-head` | `claude-sonnet` | Director — escalation gate for CS dept |
| Onboarding Specialist | `cs-onboarding` | `qwen` | Guided flows, checklists, setup scripts |
| Account Manager | `cs-account-manager` | `gemini-flash` | Long-context account history, ROI proofs |
| Tech Support | `cs-tech-support` | `qwen` | Troubleshooting, docs lookup |
| Success Associate | `cs-associate` | `openrouter-free` | Templated check-ins, status updates |

### Finance/Legal

| Agent | ID | Default Model | Rationale |
|---|---|---|---|
| Finance Lead | `fin-lead` | `claude-sonnet` | Director — compliance stakes, budget decisions |
| Accounting | `fin-accounting` | `gemini-flash` | Structured outputs, calculations, reconciliation |
| Legal/Compliance | `fin-legal` | `claude-opus` | Zero-error tolerance, regulatory reasoning |

## Department Model Groups

Instead of hardcoding model names per worker, each department has a default model group. Workers inherit from the group unless explicitly overridden. This reduces YAML drift as models evolve.

| Group | Default Model | Department(s) | Override Example |
|---|---|---|---|
| `exec` | `claude-opus` | Executive Suite | — (never overridden) |
| `product` | `gemini-flash` | Product Management | `pm-designer` → `claude-sonnet` |
| `engineering` | `codex` | Engineering | `eng-ai-voice` → `minimax`, `eng-product-qa` → `qwen` |
| `growth` | `zeroclaw` | Growth Marketing | Conditional Claw routing (see below) |
| `sales` | `openrouter-free` | Sales | — |
| `cs` | `qwen` | Customer Success | `cs-account-manager` → `gemini-flash` |
| `finance` | `gemini-flash` | Finance/Legal | `fin-legal` → `claude-opus` |
| `director` | `claude-sonnet` | All directors | — (quality gate tier) |

In worker specs, omit `llm_model` to inherit the department default:

```yaml
# Inherits from department group
department: growth

# Or override explicitly
department: growth
llm_model: nanoclaw
```

## Context Flags Schema

Conditional routing depends on **concrete flags** set upstream by the supervisor graph — not ad-hoc booleans. Flags are derived from tool scopes and resource paths, not self-declared by the worker.

| Flag | Type | Set By | Source |
|---|---|---|---|
| `touches_sensitive_repo` | bool | Supervisor | Resource path matches any entry in `SENSITIVE_PATHS` allowlist (see below) |
| `manipulates_production_data` | bool | Supervisor | Tool scope is `prod` (not `staging` or `dev`) |
| `multi_client_context` | bool | Supervisor | Task `tenant_ids` array has length > 1, or resource path under `clients/*` |
| `writes_external` | bool | Supervisor | Task invokes any tool with `side_effect: true` |
| `token_budget_exceeded` | bool | Supervisor | Input context > 100K tokens (triggers Gemini Flash shared tool) |

**Default-safe rule:** If `writes_external` is true AND any of `touches_sensitive_repo`, `manipulates_production_data`, or `multi_client_context` is **missing** (not false — missing), the supervisor routes to NanoClaw regardless of the worker's default model. Fail closed.

### SENSITIVE_PATHS Allowlist

Any resource path matching these patterns forces `touches_sensitive_repo = true`. Organized by risk category:

```python
SENSITIVE_PATHS = [
    # ── Legal, compliance, policy ──
    "knowledge/compliance/*",
    "knowledge/legal/*",
    "knowledge/policies/*",          # Security, data handling, ToS/DPAs

    # ── Client- and revenue-bearing data ──
    "clients/*",                     # Per-client configs, transcripts, notes
    "crm/*",                         # Pipeline, deals, contact details
    "billing/*",                     # Invoices, payment terms, pricing

    # ── Production configs and infrastructure ──
    "infra/prod/*",                  # Prod-only infra/config
    "config/prod/*",                 # API endpoints, routing, feature flags
    "secrets/*",                     # Encrypted blobs, keys, tokens
    "deploy/*",                      # Deployment manifests, CI/CD configs

    # ── User PII / call artifacts ──
    "data/pii/*",                    # Names, emails, phone numbers, addresses
    "data/call-recordings/*",        # Audio files, transcripts
    "data/support-tickets/*",        # Customer messages, support logs

    # ── Internal HR / finance ──
    "internal/hr/*",
    "internal/finance/*",
]
```

**Why these categories:**
- **Legal/compliance/policy:** Encodes obligations (SLAs, DPAs, compliance playbooks). Must be edited in a sandbox with full audit logs — NanoClaw's design target.
- **Clients/CRM/billing:** Regulated or high-risk data. Updates must be auditable and tightly permissioned.
- **Prod config/infra/secrets:** Where mis-routed agents cause outages or leaks.
- **PII and artifacts:** Call recordings, transcripts, tickets commonly contain PII. Always sensitive.
- **HR/finance:** Confidential by any reasonable definition.

**Environment gating:** Combine path rules with `context.env` so the same directory in a local sandbox doesn't trigger NanoClaw unless explicitly desired:

```python
def is_sensitive(resource_path: str, env: str) -> bool:
    """Path match triggers sensitive flag. In non-prod, only fire if
    FORCE_SENSITIVE_ROUTING=true (useful for rehearsing prod routing)."""
    path_match = any(fnmatch(resource_path, p) for p in SENSITIVE_PATHS)
    if env == "prod":
        return path_match
    return path_match and os.getenv("FORCE_SENSITIVE_ROUTING", "false") == "true"
```

Keep `SENSITIVE_PATHS` small and semantic. Push environment-specific paths (e.g., `staging/`) into config rather than hardcoding them here.

## Conditional Routing Rules

These agents switch models based on runtime context flags. The default model handles the common case; the override handles the sensitive case. **The director reviews output in both paths.**

### Growth Marketing — Claw Variant Routing

#### Content & Copy (`growth-content`)

| Context | Model | Why |
|---|---|---|
| Standard content ops | `zeroclaw` | Default — cheap, fast content generation |
| Touching sensitive repos (brand voice, legal-reviewed copy, compliance content) | `nanoclaw` | Isolation and auditability for sensitive content |

#### CRO Specialist (`growth-cro`)

| Context | Model | Why |
|---|---|---|
| Spinning up many test agents cheaply (A/B variants, landing page experiments) | `zeroclaw` | Cost-optimized for high-volume experimentation |
| Manipulating production data (live funnel changes, production conversion flows) | `nanoclaw` | Safety rail for production mutations |

#### Lifecycle/Retention Marketer (`growth-lifecycle`)

| Context | Model | Why |
|---|---|---|
| Embedded agents inside small services (single-tenant, simple drip campaigns) | `zeroclaw` | Lightweight, cost-effective for simple flows |
| Multi-client or agency setups (multi-tenant CRM, cross-client lifecycle management) | `nanoclaw` | Tenant isolation, auditability for multi-client contexts |

### Engineering — AI/Voice Engineer (`eng-ai-voice`)

| Context | Model | Why |
|---|---|---|
| Voice agent design, audio testing, prompt tuning for voice | `minimax` | Native audio/voice capabilities |
| Writing voice pipeline code (Python, LangGraph, Retell integration) | `codex` | Code generation is Codex's strength |
| Architecture decisions, latency debugging, production incidents | Escalate to `eng-vp` (`claude-sonnet`) | Director escalation for high-stakes engineering |

## Escalation Protocol

```
Worker produces output
    │
    ▼
Director reviews output
    │
    ├── Acceptable → Ship it
    │
    └── Low quality / uncertain → Director re-runs on own model
                                   │
                                   ├── Resolved → Ship it
                                   │
                                   └── Still uncertain → Escalate to exec
                                                          (claude-opus)
```

**Escalation triggers** (director judgment, not automated):
- Output contradicts known facts or business context
- Output is vague where specificity is required
- Output touches compliance, legal, or financial commitments
- Output would be visible to customers or external stakeholders

## Audit Tags

Every LLM invocation emits a structured log entry. This is non-negotiable — proving which agent did what on which model is a prerequisite for trust in multi-model routing.

```json
{
  "agent_id": "growth-content",
  "llm_model": "nanoclaw",
  "department_group": "growth",
  "override_fired": true,
  "override_reason": "touches_sensitive_repo",
  "escalation_depth": 0,
  "writes_external": true,
  "human_approval_required": false,
  "timestamp": "2026-03-18T14:32:01Z",
  "tenant_id": "tenant-abc123"
}
```

| Field | Type | Description |
|---|---|---|
| `agent_id` | string | Worker spec ID |
| `llm_model` | string | Actual model alias used (after routing) |
| `department_group` | string | Department model group |
| `override_fired` | bool | Whether a conditional override changed the model |
| `override_reason` | string | Which context flag triggered the override (null if none) |
| `escalation_depth` | int | 0=worker, 1=director re-run, 2=exec re-run |
| `writes_external` | bool | Whether the task writes or calls external tools |
| `human_approval_required` | bool | Whether human checkpoint was triggered |
| `tenant_id` | string | Tenant scope for the operation |

## Human Approval Checkpoint

For any NanoClaw-routed action where `writes_external` is true, the supervisor inserts a human approval node before executing the write. This is a lightweight gate — in practice it's usually just the founder approving — but it exists to prevent autonomous production mutations.

```
NanoClaw worker produces write plan
    │
    ▼
Supervisor checks: writes_external?
    │
    ├── No → Execute
    │
    └── Yes → Queue for human approval
              │
              ├── Approved → Execute + log approval
              └── Rejected → Log rejection + notify director
```

## Shared Tools (Not Agent-Bound)

These are invocable by any agent regardless of their default model:

| Tool | Purpose | Invoked By |
|---|---|---|
| `notebooklm` | Slide generation, document synthesis, presentations | Any agent needing presentation output |
| `gemini-flash` (long-context mode) | Summarizing large documents, meeting transcripts | Any agent processing >100K tokens |

## Cost Tier Summary

| Tier | Model(s) | Agent Count | Use Case |
|---|---|---|---|
| $$$$ | Claude Opus | 5 | Executives + Legal |
| $$$ | Claude Sonnet | 6 | Directors + Designer |
| $$ | Codex, Gemini Flash, MiniMax | 8 | Engineering workers, data analysts, voice |
| $ | Qwen, ZeroClaw, NanoClaw | 9 | Ops, QA, growth execution |
| Free | OpenRouter | 2 | SDR, CS Associate |
| **Total** | | **30** | |

## Implementation Notes

### LiteLLM Router Config

The current `infra/litellm/config.yaml` has a single model. To support per-agent routing, extend to:

```yaml
model_list:
  - model_name: claude-opus
    litellm_params:
      model: anthropic/claude-opus-4-6
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-6
  - model_name: gemini-flash
    litellm_params:
      model: google/gemini-3-flash
  - model_name: codex
    litellm_params:
      model: openai/codex
  - model_name: minimax
    litellm_params:
      model: minimax/minimax-01
  - model_name: qwen
    litellm_params:
      model: openrouter/qwen/qwen-2.5-72b-instruct
  - model_name: zeroclaw
    litellm_params:
      model: zeroclaw/zeroclaw-v1
  - model_name: nanoclaw
    litellm_params:
      model: nanoclaw/nanoclaw-v1
  - model_name: openclaw
    litellm_params:
      model: openclaw/openclaw-v1
  - model_name: openrouter-free
    litellm_params:
      model: openrouter/meta-llama/llama-3.1-8b-instruct:free
```

### Worker Base Changes

`harness/src/harness/graphs/workers/base.py` needs model resolution with group fallback:

```python
# Model resolution order:
# 1. Conditional override (if context flags match)
# 2. Worker spec explicit llm_model
# 3. Department group default
# 4. Global fallback

DEPARTMENT_DEFAULTS = {
    "exec": "claude-opus",
    "product": "gemini-flash",
    "engineering": "codex",
    "growth": "zeroclaw",
    "sales": "openrouter-free",
    "cs": "qwen",
    "finance": "gemini-flash",
    "director": "claude-sonnet",
}

def resolve_model(worker_spec: dict, context: dict) -> tuple[str, bool, str | None]:
    """Returns (model_alias, override_fired, override_reason)."""
    # 1. Check conditional overrides
    for override in worker_spec.get("model_overrides", []):
        flag = override["condition"]
        if context.get(flag, None) is True:
            return override["model"], True, flag

    # Default-safe: if writes_external and any sensitive flag is MISSING, use nanoclaw
    if context.get("writes_external"):
        sensitive_flags = ["touches_sensitive_repo", "manipulates_production_data", "multi_client_context"]
        for flag in sensitive_flags:
            if flag not in context:  # missing, not False
                return "nanoclaw", True, f"default_safe:{flag}_missing"

    # 2. Worker spec explicit model
    if "llm_model" in worker_spec:
        return worker_spec["llm_model"], False, None

    # 3. Department group default
    dept = worker_spec.get("department", "")
    if dept in DEPARTMENT_DEFAULTS:
        return DEPARTMENT_DEFAULTS[dept], False, None

    # 4. Global fallback
    return os.getenv("LITELLM_MODEL", "claude-sonnet-4-6"), False, None
```

### Conditional Routing in Worker Specs

Worker specs that have conditional routing use a `model_overrides` section. Conditions reference concrete context flags set by the supervisor (see Context Flags Schema above).

```yaml
department: growth
llm_model: zeroclaw  # explicit override of department default (optional)
model_overrides:
  - condition: "touches_sensitive_repo"
    model: nanoclaw
    reason: "Isolation for sensitive content"
  - condition: "manipulates_production_data"
    model: nanoclaw
    reason: "Safety rail for production mutations"
```

Worker specs without conditional needs are minimal:

```yaml
department: product
# Inherits gemini-flash from department group
```

Or with an explicit override:

```yaml
department: product
llm_model: claude-sonnet  # pm-designer needs creative judgment
```

The supervisor graph sets context flags from tool scopes and resource paths, then calls `resolve_model()` before dispatching to the worker.
