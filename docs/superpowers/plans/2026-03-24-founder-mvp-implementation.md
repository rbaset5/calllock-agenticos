# Founder MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the smallest founder-usable operating surface for CallLock: `Home`, `Approvals`, and `Blocked Work`, backed by explicit harness read models for `FounderBriefing`, `VoiceTruthSummary`, `DetectionIssuePosture`, `ApprovalInboxItem`, and `BlockedWorkItem`.

**Architecture:** Add a focused backend founder read-model layer in the harness instead of letting the UI assemble raw records. Expose those projections through dedicated founder endpoints, then build a thin `office-dashboard` frontend that consumes those APIs with simple route-based pages. Treat the existing 3D office shell as optional presentation, not as an implementation dependency.

**Tech Stack:** Python 3.11 + FastAPI + pytest in `harness`, Next.js 14 + TypeScript + React in `office-dashboard`

**Specs:** `docs/superpowers/specs/2026-03-24-founder-mvp-design.md`, `docs/superpowers/specs/2026-03-23-founder-control-surface-design.md`, `docs/superpowers/specs/2026-03-24-detection-plane-design.md`

---

## Environment Notes

- The harness project expects Python 3.11 and declares `httpx` in [`harness/pyproject.toml`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/harness/pyproject.toml). If local test execution is still using a Python without `httpx`, fix that environment before relying on `fastapi.testclient`.
- The frontend lives in [`office-dashboard/package.json`](/Users/rashidbaset/conductor/workspaces/calllock-agenticos/denver/office-dashboard/package.json) and should be verified with `npm run lint` and `npm run build`.

## File Structure

### Files to Create

| File | Responsibility |
|---|---|
| `harness/src/harness/founder_mvp.py` | Canonical founder read-model builders: `FounderBriefing`, `VoiceTruthSummary`, `DetectionIssuePosture`, `ApprovalInboxItem`, `BlockedWorkItem` |
| `harness/tests/test_founder_mvp.py` | Unit tests for founder read-model shaping and separation rules |
| `office-dashboard/src/lib/founder-api.ts` | Shared fetch helpers and TypeScript types for founder pages |
| `office-dashboard/src/app/api/founder/home/route.ts` | Server-side proxy for harness founder home data |
| `office-dashboard/src/app/api/founder/approvals/route.ts` | Server-side proxy for harness founder approvals data |
| `office-dashboard/src/app/api/founder/approvals/[approvalId]/route.ts` | Server-side proxy for founder approval decisions against the existing harness approval API |
| `office-dashboard/src/app/api/founder/blocked-work/route.ts` | Server-side proxy for harness founder blocked-work data |
| `office-dashboard/src/components/founder/FounderNav.tsx` | Shared founder route navigation |
| `office-dashboard/src/components/founder/HomePanel.tsx` | Founder home screen rendering `Briefing`, `Voice Truth`, `Issue Posture`, and `Active Priority` |
| `office-dashboard/src/components/founder/ApprovalsPanel.tsx` | Founder approvals screen over real approval records |
| `office-dashboard/src/components/founder/BlockedWorkPanel.tsx` | Founder blocked-work screen over exception-state runs |
| `office-dashboard/src/app/approvals/page.tsx` | Founder approvals route |
| `office-dashboard/src/app/blocked-work/page.tsx` | Founder blocked-work route |

### Files to Modify

| File | Change |
|---|---|
| `harness/src/db/repository.py` | Add read helpers for founder projections if `agent_reports` and artifact listing are not sufficient as-is |
| `harness/src/db/local_repository.py` | Add local read helpers for founder projections, especially `list_agent_reports` if missing |
| `harness/src/db/supabase_repository.py` | Add Supabase read helpers for founder projections, especially `list_agent_reports` if missing |
| `harness/src/harness/models.py` | Add founder request/response models if needed for typed API inputs |
| `harness/src/harness/server.py` | Add dedicated founder endpoints for home, approvals, and blocked work |
| `harness/src/harness/cockpit.py` | Optionally reuse founder read models in cockpit overview rather than duplicating shaping logic |
| `harness/tests/test_server.py` | Add server tests for founder endpoints once `httpx`-capable test env is available |
| `office-dashboard/src/app/page.tsx` | Replace the current default landing page with the founder `Home` route UI |
| `office-dashboard/src/app/layout.tsx` | Ensure layout supports simple founder navigation |

### Existing Files to Read Before Editing

| File | Why |
|---|---|
| `harness/src/harness/detection/posture.py` | Reuse the detection posture shape instead of rebuilding it inside founder logic |
| `harness/src/harness/approvals.py` | Understand existing approval request fields and resolution flow |
| `harness/src/harness/nodes/persist.py` | Confirm what run records, agent reports, and artifacts are actually persisted today |
| `harness/src/db/repository.py` | Confirm which read helpers already exist and which need to be added for founder projections |
| `harness/src/harness/cockpit.py` | Follow existing read-model aggregation patterns where useful |
| `AGENT.md` | Confirm whether an explicit active-priority section exists; MVP must degrade honestly if it does not |
| `office-dashboard/src/app/page.tsx` | Current root route and shell assumptions |
| `office-dashboard/src/components/overlays/QuestLog.tsx` | Existing approval-style interaction patterns and visual language |
| `office-dashboard/src/components/overlays/DailyMemo.tsx` | Existing compact founder-readable card patterns |

---

### Task 1: Add Backend Founder Read Models

**Files:**
- Modify: `harness/src/db/repository.py`
- Modify: `harness/src/db/local_repository.py`
- Modify: `harness/src/db/supabase_repository.py`
- Create: `harness/src/harness/founder_mvp.py`
- Create: `harness/tests/test_founder_mvp.py`

- [ ] **Step 1: Write the failing founder read-model tests**

Add `harness/tests/test_founder_mvp.py` with seeded-data coverage for the actual founder contracts. Use the existing local-state reset fixture and seed synthetic records directly through repository helpers instead of relying on ambient `tenant-alpha` data.

```python
from db.repository import create_alert_and_sync_incident, create_approval_request, create_artifact, create_job, upsert_agent_report
from harness.founder_mvp import (
    build_founder_approvals,
    build_founder_blocked_work,
    build_founder_home,
    build_voice_truth_summary,
    load_active_priority,
)


def test_voice_truth_summary_prefers_truth_artifact_over_agent_report() -> None:
    create_artifact(
        {
            "tenant_id": "tenant-alpha",
            "run_id": "run-voice-truth",
            "created_by": "voice-truth",
            "artifact_type": "voice_truth_eval",
            "payload": {
                "state": "block",
                "top_reason": "customer_phone_exact regressed",
                "failed_metric_count": 2,
                "baseline_version": "prod-v1",
                "candidate_version": "candidate-v2",
            },
            "lineage": {"worker_id": "voice-truth"},
        }
    )
    upsert_agent_report(
        {
            "agent_id": "voice-truth",
            "report_type": "voice-eval",
            "report_date": "2026-03-24",
            "status": "green",
            "payload": {"summary": "stale advisory report"},
            "tenant_id": "tenant-alpha",
        }
    )
    summary = build_voice_truth_summary(tenant_id="tenant-alpha")
    assert summary["state"] == "block"
    assert summary["top_reason"] == "customer_phone_exact regressed"
    assert summary["baseline_version"] == "prod-v1"
    assert summary["candidate_version"] == "candidate-v2"


def test_founder_home_contains_contract_fields_not_just_keys() -> None:
    create_alert_and_sync_incident(
        {
            "tenant_id": "tenant-alpha",
            "alert_type": "voice_route_missing_spike",
            "severity": "high",
            "message": "Route missing spike",
            "metrics": {"detection": {"notification_outcome": "founder_notify"}},
        }
    )
    create_approval_request(
        {
            "tenant_id": "tenant-alpha",
            "run_id": "run-approval",
            "worker_id": "voice-builder",
            "status": "pending",
            "reason": "Truth escalation requires review",
            "requested_by": "harness",
            "request_type": "verification",
            "payload": {"verification": {"verdict": "escalate", "reasons": ["Boundary call"]}},
        }
    )
    payload = build_founder_home(tenant_id="tenant-alpha")
    assert payload["briefing"]["top_pending_approval"] is not None
    assert payload["voice_truth"]["state"] in {"pass", "block", "escalate", "not_active"}
    assert payload["issue_posture"]["counts"]["founder_visible_threads"] == 1
    assert "active_priority" in payload


def test_load_active_priority_returns_null_projection_when_agent_file_has_no_priority() -> None:
    priority = load_active_priority()
    assert priority["label"] is None
    assert priority["source"] == "AGENT.md"


def test_founder_approvals_uses_real_approval_requests_only() -> None:
    create_approval_request(
        {
            "tenant_id": "tenant-alpha",
            "run_id": "run-approval",
            "worker_id": "voice-builder",
            "status": "pending",
            "reason": "Truth escalation requires review",
            "requested_by": "harness",
            "request_type": "verification",
            "payload": {"verification": {"verdict": "escalate", "reasons": ["Boundary call"]}},
        }
    )
    approvals = build_founder_approvals(tenant_id="tenant-alpha")
    assert approvals["items"][0]["source"] == "approval_requests"
    assert approvals["items"][0]["reason"] == "Truth escalation requires review"
    assert approvals["items"][0]["requested_action"] in {"approve", "deny", "defer"}


def test_blocked_work_derives_reason_next_step_and_artifacts_from_jobs() -> None:
    job = create_job(
        {
            "tenant_id": "tenant-alpha",
            "origin_worker_id": "voice-builder",
            "origin_run_id": "run-blocked",
            "job_type": "voice-change",
            "status": "failed",
            "idempotency_key": "voice-builder:run-blocked",
            "payload": {"target_worker_id": "voice-builder"},
            "result": {
                "status": "block",
                "verification": {"passed": False, "verdict": "block", "reasons": ["route_no_regression failed"]},
            },
            "created_by": "harness",
        }
    )
    create_artifact(
        {
            "tenant_id": "tenant-alpha",
            "run_id": "run-blocked",
            "created_by": "voice-truth",
            "artifact_type": "run_record",
            "source_job_id": job["id"],
            "payload": {"summary": "blocked run artifact"},
            "lineage": {"worker_id": "voice-truth"},
        }
    )
    blocked = build_founder_blocked_work(tenant_id="tenant-alpha")
    item = blocked["items"][0]
    assert item["blocked_reason"] == "route_no_regression failed"
    assert item["recommended_next_step"] is not None
    assert len(item["artifact_refs"]) == 1
```

- [ ] **Step 2: Run the new tests to confirm the gap**

Run:

```bash
cd harness && pytest tests/test_founder_mvp.py -v
```

Expected:
- `FAIL` because `harness.founder_mvp` does not exist yet

- [ ] **Step 3: Add repository read helpers if they are missing**

If `db.repository` does not already expose what the founder builders need, add:
- `list_agent_reports(tenant_id: str | None = None, agent_id: str | None = None)`
- any thin helper needed to list artifacts by tenant/run without bypassing the repository layer

Implement the same functions in:
- `harness/src/db/repository.py`
- `harness/src/db/local_repository.py`
- `harness/src/db/supabase_repository.py`

Do not reach into `_request()` or `_state()` from `founder_mvp.py` directly.

- [ ] **Step 4: Implement the founder read-model module**

Create `harness/src/harness/founder_mvp.py` with focused builders:

```python
def build_founder_home(*, tenant_id: str | None = None) -> dict[str, Any]:
    return {
        "briefing": build_founder_briefing(tenant_id=tenant_id),
        "voice_truth": build_voice_truth_summary(tenant_id=tenant_id),
        "issue_posture": build_detection_posture(tenant_id=tenant_id),
        "active_priority": load_active_priority(),
    }
```

Also implement:
- `build_founder_briefing(...)`
- `build_voice_truth_summary(...)`
- `build_founder_approvals(...)`
- `build_founder_blocked_work(...)`
- `load_active_priority(...)`

Rules to encode:
- `FounderBriefing` is one compact object, not a list
- `VoiceTruthSummary` is one summary row only
- `Issue Posture` must reuse detection posture, not raw alerts
- `Approvals` must use existing `approval_requests` only
- `Blocked Work` must derive from exception-state `jobs`, not incidents
- `VoiceTruthSummary` must resolve from real persisted sources in this order:
  1. latest voice-specific truth artifact / eval result if present
  2. latest voice-related `agent_reports` summary if present
  3. otherwise return `state="not_active"` with a compact reason instead of inventing a pass state
- `load_active_priority()` must parse an explicit `## Active Priority` section or `Active Priority:` line from `AGENT.md`; if neither exists, return a null projection such as:

```python
{"label": None, "constraints": [], "source": "AGENT.md"}
```

- `BlockedWorkItem` derivation must be explicit:
  - `blocked_reason` from `result.verification.reasons[0]`, else `result.status`, else `"Blocked"`
  - `recommended_next_step` from verdict/status:
    - `escalate` with matching pending approval -> `"Review approval request"`
    - `block` -> `"Revise candidate and rerun truth gate"`
    - `retry` -> `"Retry after fixing verification findings"`
  - `artifact_refs` from matching tenant/run artifacts, preferring `source_job_id == job.id`
- `FounderBriefing` must derive each top slot from real records:
  - `top_pending_approval` from pending `approval_requests`
  - `top_issue_thread` from founder-visible detection posture
  - `top_blocked_work` from blocked-work projection
  - `top_regression` from `VoiceTruthSummary` when state is `block` or `escalate`

- [ ] **Step 5: Run the founder read-model tests**

Run:

```bash
cd harness && pytest tests/test_founder_mvp.py -v
```

Expected:
- `PASS`

- [ ] **Step 6: Commit**

```bash
git add harness/src/db/repository.py harness/src/db/local_repository.py harness/src/db/supabase_repository.py harness/src/harness/founder_mvp.py harness/tests/test_founder_mvp.py
git commit -m "feat: add founder mvp read models"
```

### Task 2: Add Founder API Endpoints in the Harness

**Files:**
- Modify: `harness/src/harness/models.py`
- Modify: `harness/src/harness/server.py`
- Modify: `harness/tests/test_server.py`

- [ ] **Step 1: Write the failing server tests**

Add tests in `harness/tests/test_server.py` for concrete payload contracts, not just `200` responses:

```python
def test_founder_home_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/founder/home", params={"tenant_id": "tenant-alpha"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["briefing"]["recommended_action"] is not None
    assert payload["voice_truth"]["state"] in {"pass", "block", "escalate", "not_active"}
    assert "active_threads" in payload["issue_posture"]


def test_founder_approvals_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/founder/approvals", params={"tenant_id": "tenant-alpha"})
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["source"] == "approval_requests"
    assert item["reason"]
    assert item["recommended_action"]


def test_founder_blocked_work_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/founder/blocked-work", params={"tenant_id": "tenant-alpha"})
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["blocked_reason"]
    assert item["recommended_next_step"]
    assert isinstance(item["artifact_refs"], list)
```

- [ ] **Step 2: Run the failing server tests**

Run:

```bash
cd harness && pytest tests/test_server.py -k "founder_home_endpoint or founder_approvals_endpoint or founder_blocked_work_endpoint" -v
```

Expected:
- `FAIL` because the founder routes do not exist yet

- [ ] **Step 3: Add the API models if needed**

In `harness/src/harness/models.py`, add a small typed request model only if needed for POST bodies. For GET routes, prefer simple query params and do not create unnecessary request models.

Use YAGNI here: if the routes are simple `GET`s with `tenant_id`, do not invent extra models.

- [ ] **Step 4: Add founder endpoints to the server**

In `harness/src/harness/server.py`, import the founder builders and add:

```python
@app.get("/founder/home")
def founder_home_endpoint(tenant_id: str = None) -> dict[str, Any]:
    return build_founder_home(tenant_id=tenant_id)


@app.get("/founder/approvals")
def founder_approvals_endpoint(tenant_id: str = None) -> dict[str, Any]:
    return build_founder_approvals(tenant_id=tenant_id)


@app.get("/founder/blocked-work")
def founder_blocked_work_endpoint(tenant_id: str = None) -> dict[str, Any]:
    return build_founder_blocked_work(tenant_id=tenant_id)
```

- [ ] **Step 5: Run the server tests**

Run:

```bash
cd harness && pytest tests/test_server.py -k "founder_home_endpoint or founder_approvals_endpoint or founder_blocked_work_endpoint" -v
```

Expected:
- `PASS`

If the local environment still fails on missing `httpx`, stop and fix the harness Python environment first instead of weakening the tests.

- [ ] **Step 6: Commit**

```bash
git add harness/src/harness/models.py harness/src/harness/server.py harness/tests/test_server.py
git commit -m "feat: add founder mvp harness endpoints"
```

### Task 3: Add Office Dashboard API Proxies and Shared Client

**Files:**
- Create: `office-dashboard/src/lib/founder-api.ts`
- Create: `office-dashboard/src/app/api/founder/home/route.ts`
- Create: `office-dashboard/src/app/api/founder/approvals/route.ts`
- Create: `office-dashboard/src/app/api/founder/approvals/[approvalId]/route.ts`
- Create: `office-dashboard/src/app/api/founder/blocked-work/route.ts`

- [ ] **Step 1: Write the failing API proxy expectations**

If there are no existing frontend tests, document verification-first expectations in the plan and use build-time verification instead of inventing a new frontend test harness.

The API proxy contract should be:

```ts
const response = await fetch("/api/founder/home?tenant_id=tenant-alpha");
const payload = await response.json();
expect(payload.briefing).toBeDefined();
```

- [ ] **Step 2: Create the shared founder API helper**

Create `office-dashboard/src/lib/founder-api.ts` with:
- shared base URL resolution using `NEXT_PUBLIC_HARNESS_BASE_URL`
- typed fetch helpers:
  - `fetchFounderHome(...)`
  - `fetchFounderApprovals(...)`
  - `fetchFounderBlockedWork(...)`
  - `resolveFounderApproval(...)`

- [ ] **Step 3: Add the Next.js proxy routes**

Create the three route handlers to forward to the harness:

```ts
export async function GET(request: Request) {
  const url = new URL(request.url);
  const tenantId = url.searchParams.get("tenant_id");
  const baseUrl = process.env.NEXT_PUBLIC_HARNESS_BASE_URL;
  const upstream = await fetch(`${baseUrl}/founder/home?tenant_id=${tenantId ?? ""}`, {
    cache: "no-store",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
  });
}
```

Repeat for:
- `/founder/approvals`
- `/founder/blocked-work`

Also add a mutation proxy for the real existing harness approval path:

```ts
export async function POST(
  request: Request,
  { params }: { params: { approvalId: string } }
) {
  const body = await request.text();
  const baseUrl = process.env.NEXT_PUBLIC_HARNESS_BASE_URL;
  const upstream = await fetch(`${baseUrl}/approvals/${params.approvalId}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
    cache: "no-store",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
  });
}
```

- [ ] **Step 4: Verify the frontend compiles**

Run:

```bash
cd office-dashboard && npm run build
```

Expected:
- `PASS`

- [ ] **Step 5: Commit**

```bash
git add office-dashboard/src/lib/founder-api.ts office-dashboard/src/app/api/founder
git commit -m "feat: add founder mvp dashboard api proxies"
```

### Task 4: Build the Founder Home Screen

**Files:**
- Create: `office-dashboard/src/components/founder/FounderNav.tsx`
- Create: `office-dashboard/src/components/founder/HomePanel.tsx`
- Modify: `office-dashboard/src/app/page.tsx`
- Modify: `office-dashboard/src/app/layout.tsx`

- [ ] **Step 1: Build the founder navigation component**

Create `FounderNav.tsx` with links to:
- `/`
- `/approvals`
- `/blocked-work`

Keep it simple and 2D. Do not depend on the 3D office scene.

- [ ] **Step 2: Build the home panel**

Create `HomePanel.tsx` that fetches `/api/founder/home` and renders four sections:
- `Briefing`
- `Voice Truth`
- `Issue Posture`
- `Active Priority`

Render rules:
- `Briefing` is one compact summary card, not a list
- `Voice Truth` is one status card
- `Issue Posture` is a small thread list
- `Active Priority` is one pinned strip

- [ ] **Step 3: Replace the current landing page**

In `office-dashboard/src/app/page.tsx`, replace the 3D-office-first landing page with the founder home screen:

```tsx
export default function Home() {
  return (
    <main>
      <FounderNav />
      <HomePanel />
    </main>
  );
}
```

Do not delete the old 3D files in this task. Just stop making them the default founder experience.

- [ ] **Step 4: Verify lint and build**

Run:

```bash
cd office-dashboard && npm run lint && npm run build
```

Expected:
- `PASS`

- [ ] **Step 5: Commit**

```bash
git add office-dashboard/src/components/founder office-dashboard/src/app/page.tsx office-dashboard/src/app/layout.tsx
git commit -m "feat: add founder mvp home screen"
```

### Task 5: Build Founder Approvals and Blocked Work Routes

**Files:**
- Create: `office-dashboard/src/components/founder/ApprovalsPanel.tsx`
- Create: `office-dashboard/src/components/founder/BlockedWorkPanel.tsx`
- Create: `office-dashboard/src/app/approvals/page.tsx`
- Create: `office-dashboard/src/app/blocked-work/page.tsx`

- [ ] **Step 1: Build the approvals panel**

Create `ApprovalsPanel.tsx` over `/api/founder/approvals` as a real list/detail workflow.

It must render:
- a selectable list of approval items
- a detail pane (or expanded detail section on mobile) for the selected item showing:
  - title
  - affected surface
  - risk level
  - reason
  - requested action
  - age
  - evidence summary
  - recommended action

Primary actions:
- `Approve`
- `Deny`
- `Defer`

Use the existing real harness approval resolution path through the new proxy route:
- `Approve` -> `{ status: "approved", resolution_notes: ... }`
- `Deny` -> `{ status: "rejected", resolution_notes: ... }`
- `Defer` -> `{ status: "cancelled", resolution_notes: ... }`

Rules:
- present `Defer` in UI even though the current backend enum is `cancelled`
- do not optimistic-update before the API returns success
- after success, refetch the approvals list and show the updated status
- if the backend rejects the mutation, surface the error inline and preserve the current list state
- if no item is selected, default to the highest-risk / oldest pending approval

- [ ] **Step 2: Build the blocked work panel**

Create `BlockedWorkPanel.tsx` over `/api/founder/blocked-work`.

It must render:
- worker
- task type
- state
- blocked reason
- recommended next step

This screen must not include issue threads from detection posture.

- [ ] **Step 3: Add the route pages**

Create:
- `office-dashboard/src/app/approvals/page.tsx`
- `office-dashboard/src/app/blocked-work/page.tsx`

Each page should render:
- `FounderNav`
- the corresponding panel

- [ ] **Step 4: Verify lint and build**

Run:

```bash
cd office-dashboard && npm run lint && npm run build
```

Expected:
- `PASS`

- [ ] **Step 5: Commit**

```bash
git add office-dashboard/src/components/founder/ApprovalsPanel.tsx office-dashboard/src/components/founder/BlockedWorkPanel.tsx office-dashboard/src/app/approvals/page.tsx office-dashboard/src/app/blocked-work/page.tsx
git commit -m "feat: add founder mvp approvals and blocked work views"
```

### Task 6: Final Verification and Acceptance Sweep

**Files:**
- Verify all files touched in Tasks 1-5

- [ ] **Step 1: Run the focused harness founder suite**

Run:

```bash
cd harness && pytest tests/test_founder_mvp.py tests/test_detection_posture.py tests/test_server.py -k "founder or detection" -v
```

Expected:
- `PASS`

- [ ] **Step 2: Run the frontend verification commands**

Run:

```bash
cd office-dashboard && npm run lint && npm run build
```

Expected:
- `PASS`

- [ ] **Step 3: Do a manual founder acceptance pass**

Verify manually in the browser:
- `/` shows `Briefing`, `Voice Truth`, `Issue Posture`, and `Active Priority`
- `/approvals` shows only real approval items
- `/blocked-work` shows only blocked or escalated work items
- no page depends on the 3D office scene to be usable
- issue posture is visibly distinct from blocked work

- [ ] **Step 4: Commit**

```bash
git add harness office-dashboard
git commit -m "feat: ship founder mvp operating surface"
```

## Acceptance Criteria

- `FounderBriefing` exists as a backend read model
- `VoiceTruthSummary` exists as a compact backend read model
- `DetectionIssuePosture` is reused, not rebuilt from raw alerts in the UI
- `Approvals` are backed by existing `approval_requests`
- `Blocked Work` is backed by exception-state `jobs`
- `/`, `/approvals`, and `/blocked-work` are the usable founder MVP routes
- the 3D office is not required for founder MVP acceptance

## Out of Scope

- reintroducing the 3D office as the main founder experience
- app truth UI
- outbound truth UI
- decisions explorer
- improvement-lab UI
- deep approval mutation flows beyond the current real backend capability
