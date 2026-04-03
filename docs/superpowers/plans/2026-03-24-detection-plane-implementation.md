# Detection Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first Detection Plane slice by extending the existing alerts/incidents runtime with voice monitors, triage outcomes, filtered notification decisions, automatic investigation dispatch, and founder-facing issue posture without adding a second incident system.

**Architecture:** Phase 1 / early Phase 2 detection reuses the current `alerts -> incidents -> cockpit` path and pulls voice signal inputs from existing `call_records` access paths rather than job payloads. Detection-specific logic lives in a new `harness.detection` package that normalizes monitor signals, computes `investigate | suppress | stand_down | escalate`, stores triage metadata inside existing alert payloads, reuses `incidents` as the first durable issue-thread model, dispatches investigation tasks through the existing harness dispatch path, and projects a filtered issue posture into the current `office-dashboard` overlays.

**Tech Stack:** Python (harness, FastAPI), existing alert/incident repository layer, JSON-in-`.yaml` knowledge specs, Supabase/local repository storage, Next.js founder cockpit, pytest

**Specs:** `docs/superpowers/specs/2026-03-24-detection-plane-design.md`, `docs/superpowers/specs/2026-03-23-founder-control-surface-design.md`, `docs/superpowers/specs/2026-03-23-truth-plane-design.md`, `docs/superpowers/specs/2026-03-23-governance-plane-design.md`, `docs/superpowers/specs/2026-03-23-execution-org-design.md`

---

## Resolved Detection Decisions

- Detection reuses existing `alerts` and `incidents`; no new detection table lands in this slice.
- `incidents` are the first durable `Issue Thread` model.
- Detection outcomes are:
  - `investigate`
  - `suppress`
  - `stand_down`
  - `escalate`
- Notification decisions are:
  - `internal_only`
  - `operator_notify`
  - `founder_notify`
  - `silent_stand_down`
- A fired monitor is an investigation trigger, not a truth verdict and not a governance verdict.
- Detection metadata is stored in `alert["metrics"]["detection"]` and projected into founder/cockpit read models.
- The first new monitor slice is `voice-only`; existing generic operational alerts remain in place.
- Voice signal inputs come from `call_records` via the existing health-check query path, not from `list_jobs()`.
- The first monitor set is grounded in fields the runtime already persists on call records:
  - `route`
  - `urgency_tier`
  - `safety_emergency`
  - `scorecard_warnings`
  - required-field presence
  - empty structured output
- `eng-product-qa` temporarily coordinates escalated detection triage, but `investigate` dispatch still routes to the specialized owner (`voice-builder` first).

## File Structure

### Files to Create

| File | Responsibility |
|---|---|
| `knowledge/detection/voice-monitor-spec.yaml` | Canonical first-slice monitor catalog, thresholds, surfaces, and notification defaults |
| `harness/src/harness/detection/__init__.py` | Public exports for the new detection package |
| `harness/src/harness/detection/catalog.py` | Loads and validates monitor catalog entries |
| `harness/src/harness/detection/triage.py` | Detection event normalization, triage assessment, notification-decision rules |
| `harness/src/harness/detection/evaluator.py` | Runs the detection pass by combining existing alerts with voice call-record signal checks |
| `harness/src/harness/detection/dispatch.py` | Converts `investigate` and `escalate` outcomes into bounded worker dispatch requests |
| `harness/src/harness/detection/posture.py` | Builds founder/operator issue posture from alerts + incidents |
| `harness/tests/test_detection_catalog.py` | Monitor-catalog validation tests |
| `harness/tests/test_detection_triage.py` | Triage and notification-decision tests |
| `harness/tests/test_detection_evaluator.py` | Detection evaluation and incident-reuse tests |
| `harness/tests/test_detection_dispatch.py` | Investigation-dispatch tests |
| `harness/tests/test_detection_posture.py` | Founder issue-posture projection tests |
| `office-dashboard/src/components/overlays/DetectionPosture.tsx` | Overlay for filtered founder-visible detection threads |
| `office-dashboard/src/app/api/detection/posture/route.ts` | Server-side proxy from the office dashboard to the harness detection posture endpoint |

### Files to Modify

| File | Change |
|---|---|
| `harness/src/harness/alerts/definitions.py` | Add detection-aware alert types for the first voice slice |
| `harness/src/harness/alerts/evaluator.py` | Delegate to the new detection evaluator while preserving existing alert behavior |
| `harness/src/harness/alerts/notifier.py` | Respect notification decisions when selecting channels |
| `harness/src/harness/cockpit.py` | Add filtered issue-posture read model for founder/operator surfaces |
| `harness/src/harness/models.py` | Add request models for detection evaluation and issue-posture endpoints if needed |
| `harness/src/harness/server.py` | Expose `/detection/evaluate` and detection posture endpoints; keep existing alert endpoints intact |
| `harness/src/harness/incident_classification.py` | Classify new voice detection alert types into stable incident domains/categories |
| `harness/src/harness/graphs/workers/eng_product_qa.py` | Consume detection-triggered issue context for triage coordination |
| `harness/tests/test_alerts.py` | Cover new detection-backed alert types and notification filtering |
| `harness/tests/test_server.py` | Cover detection endpoints and issue-posture API behavior |
| `office-dashboard/src/app/page.tsx` | Add a detection posture toggle/count to the existing command-center controls |
| `office-dashboard/src/components/office-scene.tsx` | Mount the detection posture overlay in the current 3D office scene |
| `office-dashboard/src/components/overlays/DailyMemo.tsx` | Optionally link filtered issue posture to the memo context without showing raw alert spam |

---

### Task 1: Lock the Detection Catalog and Contracts

**Files:**
- Create: `knowledge/detection/voice-monitor-spec.yaml`
- Create: `harness/src/harness/detection/catalog.py`
- Create: `harness/tests/test_detection_catalog.py`
- Modify: `harness/src/harness/alerts/definitions.py`

- [ ] **Step 1: Write the failing catalog test**

Add `harness/tests/test_detection_catalog.py` with assertions like:

```python
from harness.detection.catalog import load_voice_monitor_spec


def test_voice_monitor_spec_defines_first_slice_monitors() -> None:
    spec = load_voice_monitor_spec()
    monitor_ids = {monitor["monitor_id"] for monitor in spec["monitors"]}

    assert "voice_empty_structured_output_spike" in monitor_ids
    assert "voice_required_field_missing_spike" in monitor_ids
    assert "voice_warning_rate_spike" in monitor_ids
    assert "voice_route_missing_spike" in monitor_ids
```

- [ ] **Step 2: Run the test to confirm the gap**

Run:

```bash
pytest harness/tests/test_detection_catalog.py -v
```

Expected:
- `FAIL` because the detection catalog module and spec file do not exist yet

- [ ] **Step 3: Create the monitor spec**

Create `knowledge/detection/voice-monitor-spec.yaml` with one first-slice section:

```json
{
  "version": "1.0",
  "owner": "eng-product-qa",
  "surface": "voice",
  "monitors": [
    {
      "monitor_id": "voice_empty_structured_output_spike",
      "signal_type": "empty_structured_output_rate",
      "default_threshold": 0.1,
      "severity": "high",
      "triage_default": "investigate",
      "notification_default": "internal_only"
    },
    {
      "monitor_id": "voice_required_field_missing_spike",
      "signal_type": "required_field_missing_rate",
      "required_fields": ["customer_phone", "urgency_tier", "route"],
      "default_threshold": 0.15,
      "severity": "high",
      "triage_default": "investigate",
      "notification_default": "internal_only"
    }
  ]
}
```

Also include:
- `voice_warning_rate_spike`
- `voice_route_missing_spike`
- `voice_safety_emergency_mismatch_signal`

- [ ] **Step 4: Implement the catalog loader**

In `harness/src/harness/detection/catalog.py`, add:

```python
from pathlib import Path

from knowledge.pack_loader import load_json_yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
VOICE_MONITOR_SPEC = REPO_ROOT / "knowledge" / "detection" / "voice-monitor-spec.yaml"


def load_voice_monitor_spec() -> dict[str, object]:
    payload = load_json_yaml(VOICE_MONITOR_SPEC)
    monitors = payload.get("monitors", [])
    if not isinstance(monitors, list) or not monitors:
        raise ValueError("voice monitor spec must define at least one monitor")
    return payload
```

- [ ] **Step 5: Register the new alert types**

Extend `harness/src/harness/alerts/definitions.py` with detection-aware types:

```python
"voice_empty_structured_output_spike": "Voice output is empty more often than the configured threshold.",
"voice_required_field_missing_spike": "Required voice fields are missing above threshold.",
"voice_warning_rate_spike": "Voice scorecard warnings are spiking.",
"voice_route_missing_spike": "Voice outputs are missing route more often than expected.",
```

- [ ] **Step 6: Run the catalog test**

Run:

```bash
pytest harness/tests/test_detection_catalog.py -v
```

Expected:
- `PASS`

### Task 2: Add Detection Events, Triage, and Notification Decisions

**Files:**
- Create: `harness/src/harness/detection/triage.py`
- Create: `harness/tests/test_detection_triage.py`
- Modify: `harness/src/harness/incident_classification.py`

- [ ] **Step 1: Write the failing triage tests**

Add `harness/tests/test_detection_triage.py` covering:

```python
from harness.detection.triage import assess_detection_event, decide_notification


def test_duplicate_open_issue_stands_down() -> None:
    event = {"signal_type": "voice_warning_rate_spike", "severity": "high", "dedupe_key": "tenant-1:voice_warning_rate_spike"}
    assessment = assess_detection_event(event, has_open_issue=True, in_flight_fix=False)
    assert assessment["outcome"] == "stand_down"


def test_high_severity_new_signal_investigates() -> None:
    event = {"signal_type": "voice_empty_structured_output_spike", "severity": "high", "dedupe_key": "tenant-1:voice_empty_structured_output_spike"}
    assessment = assess_detection_event(event, has_open_issue=False, in_flight_fix=False)
    assert assessment["outcome"] == "investigate"
```

Also cover notification separation:

```python
decision = decide_notification({"outcome": "investigate", "severity": "high", "surface": "voice"})
assert decision["notification_outcome"] == "internal_only"
```

And cover the other required branches:

```python
escalated = assess_detection_event(
    {"signal_type": "voice_safety_emergency_mismatch_signal", "severity": "critical", "dedupe_key": "tenant-1:voice_safety"},
    has_open_issue=False,
    in_flight_fix=False,
)
assert escalated["outcome"] == "escalate"

operator_notice = decide_notification(
    {"surface": "voice", "severity": "critical"},
    {"outcome": "escalate", "reason": "safety_signal"},
)
assert operator_notice["notification_outcome"] in {"operator_notify", "founder_notify"}
```

- [ ] **Step 2: Run the triage tests to confirm the gap**

Run:

```bash
pytest harness/tests/test_detection_triage.py -v
```

Expected:
- `FAIL` because the triage module does not exist yet

- [ ] **Step 3: Implement normalized detection-event helpers**

In `harness/src/harness/detection/triage.py`, add small pure helpers:

```python
def build_detection_event(*, monitor_id: str, tenant_id: str | None, severity: str, raw_context: dict[str, object]) -> dict[str, object]:
    dedupe_key = f"{tenant_id or 'global'}:{monitor_id}"
    return {
        "source": "alerts",
        "surface": "voice" if monitor_id.startswith("voice_") else "product",
        "signal_type": monitor_id,
        "severity": severity,
        "tenant_id": tenant_id,
        "dedupe_key": dedupe_key,
        "raw_context": raw_context,
    }
```

- [ ] **Step 4: Implement triage assessment and notification rules**

Keep the first slice narrow and explicit:

```python
def assess_detection_event(event: dict[str, object], *, has_open_issue: bool, in_flight_fix: bool) -> dict[str, object]:
    if has_open_issue or in_flight_fix:
        return {"outcome": "stand_down", "reason": "matching_issue_already_active"}
    if event["signal_type"] == "voice_safety_emergency_mismatch_signal":
        return {"outcome": "escalate", "reason": "safety_signal"}
    if event["severity"] == "low":
        return {"outcome": "suppress", "reason": "below_operational_threshold"}
    return {"outcome": "investigate", "reason": "new_meaningful_signal"}


def decide_notification(event: dict[str, object], assessment: dict[str, object] | None = None) -> dict[str, object]:
    outcome = (assessment or {}).get("outcome", event.get("outcome"))
    if outcome == "stand_down":
        return {"notification_outcome": "silent_stand_down", "channels": []}
    if outcome == "escalate" and event.get("severity") == "critical":
        return {"notification_outcome": "founder_notify", "channels": ["dashboard", "email"]}
    if outcome == "escalate":
        return {"notification_outcome": "operator_notify", "channels": ["dashboard", "email"]}
    return {"notification_outcome": "internal_only", "channels": ["dashboard"]}
```

- [ ] **Step 5: Teach incident classification about the new alert types**

Extend `harness/src/harness/incident_classification.py` with rules like:

```python
{
    "match": {"alert_type_prefix": "voice_"},
    "incident_domain": "voice",
    "incident_category": "voice_quality_regression",
    "remediation_category": "voice_investigation",
},
```

- [ ] **Step 6: Run the triage tests**

Run:

```bash
pytest harness/tests/test_detection_triage.py -v
```

Expected:
- `PASS`

### Task 3: Build the Detection Evaluator on Top of `call_records`, Alerts, and Incidents

**Files:**
- Create: `harness/src/harness/detection/evaluator.py`
- Create: `harness/tests/test_detection_evaluator.py`
- Modify: `harness/src/harness/alerts/evaluator.py`
- Modify: `harness/src/harness/alerts/notifier.py`
- Modify: `harness/src/voice/services/health_check.py`
- Modify: `harness/tests/test_alerts.py`

- [ ] **Step 1: Write the failing evaluator tests**

Add `harness/tests/test_detection_evaluator.py` with one test for new-signal investigation and one for duplicate stand-down. Use call-record-shaped rows, not job rows:

```python
from harness.detection.evaluator import evaluate_detection


def test_detection_evaluator_persists_triage_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        "harness.detection.evaluator.list_recent_call_records",
        lambda **_: [
            {
                "call_id": "call-1",
                "extracted_fields": {},
                "route": "",
                "urgency_tier": "urgent",
                "scorecard_warnings": ["callback-gap"],
            }
        ],
    )
    results = evaluate_detection(tenant_id="tenant-alpha", window_minutes=15)
    assert results
    first = results[0]
    assert first["metrics"]["detection"]["triage_outcome"] in {"investigate", "suppress", "stand_down", "escalate"}
    assert first["metrics"]["detection"]["notification_outcome"] in {
        "internal_only",
        "operator_notify",
        "founder_notify",
        "silent_stand_down",
    }
```

- [ ] **Step 2: Run the evaluator tests to confirm the gap**

Run:

```bash
pytest harness/tests/test_detection_evaluator.py -v
```

Expected:
- `FAIL` because the evaluator does not exist yet

- [ ] **Step 3: Implement the detection evaluator**

In `harness/src/harness/detection/evaluator.py`, build on the current alert path and the existing call-record query helper:

```python
from db.repository import create_alert_and_sync_incident, get_tenant_config, list_incidents
from harness.detection.catalog import load_voice_monitor_spec
from harness.detection.triage import assess_detection_event, build_detection_event, decide_notification
from voice.services.health_check import list_recent_call_records


def evaluate_detection(*, tenant_id: str | None = None, window_minutes: int = 15) -> list[dict[str, object]]:
    tenant_config = get_tenant_config(tenant_id) if tenant_id else {}
    incidents = list_incidents(tenant_id=tenant_id, status="open")
    rows = list_recent_call_records(limit=50)
    # compute first-slice voice metrics from call_records fields
    # create alerts only when thresholds breach
```

Use fields the runtime already persists on call records:
- empty `extracted_fields`
- missing `route`
- missing required fields (`customer_phone`, `urgency_tier`, `route`)
- non-empty `scorecard_warnings`
- `safety_emergency` mismatch signals where the rerun/manual comparison data exists

Persist triage metadata inside `metrics["detection"]`:

```python
metrics["detection"] = {
    "triage_outcome": assessment["outcome"],
    "triage_reason": assessment["reason"],
    "notification_outcome": notification["notification_outcome"],
    "dedupe_key": event["dedupe_key"],
}
```

- [ ] **Step 4: Delegate alert evaluation through the detection evaluator**

Update `harness/src/harness/alerts/evaluator.py` so the current endpoint remains stable:

```python
from harness.detection.evaluator import evaluate_detection


def evaluate_alerts(*, tenant_id: str | None = None, window_minutes: int = 15) -> list[dict[str, Any]]:
    return evaluate_detection(tenant_id=tenant_id, window_minutes=window_minutes)
```

Preserve existing generic alert metrics inside the new evaluator rather than deleting them.

- [ ] **Step 5: Respect notification decisions**

Update `harness/src/harness/alerts/notifier.py` to accept channel overrides:

```python
def notify(alert: dict, tenant_config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = tenant_config or {}
    detection_meta = (alert.get("metrics") or {}).get("detection", {})
    forced_channels = detection_meta.get("channels")
    for channel in forced_channels or _resolve_channels(config):
        ...
```

Skip founder/operator channels when `notification_outcome` is `internal_only` or `silent_stand_down`.

- [ ] **Step 6: Expand alert tests**

Add cases in `harness/tests/test_alerts.py` to assert:
- detection alerts are created with `metrics["detection"]`
- duplicate incidents produce `stand_down`
- `silent_stand_down` does not page/email

- [ ] **Step 7: Run the evaluator and alert test suite**

Run:

```bash
pytest harness/tests/test_detection_evaluator.py harness/tests/test_alerts.py -v
```

Expected:
- `PASS`

### Task 4: Automatically Dispatch Investigation Workflows

**Files:**
- Create: `harness/src/harness/detection/dispatch.py`
- Create: `harness/tests/test_detection_dispatch.py`
- Modify: `harness/src/harness/detection/evaluator.py`
- Modify: `harness/src/harness/graphs/workers/eng_product_qa.py`

- [ ] **Step 1: Write the failing dispatch tests**

Add `harness/tests/test_detection_dispatch.py` with one `investigate` case and one `escalate` case:

```python
from harness.detection.dispatch import build_detection_dispatches


def test_investigate_dispatches_to_voice_builder() -> None:
    alert = {
        "tenant_id": "tenant-alpha",
        "alert_type": "voice_route_missing_spike",
        "metrics": {"detection": {"triage_outcome": "investigate", "dedupe_key": "tenant-alpha:voice_route_missing_spike"}},
    }
    requests = build_detection_dispatches(alert)
    assert requests[0].worker_id == "voice-builder"
    assert requests[0].task_type == "detection-investigate"
```

- [ ] **Step 2: Run the dispatch tests to confirm the gap**

Run:

```bash
pytest harness/tests/test_detection_dispatch.py -v
```

Expected:
- `FAIL` because the dispatch helper does not exist yet

- [ ] **Step 3: Implement the dispatch helper**

Create `harness/src/harness/detection/dispatch.py` using the existing dispatch path:

```python
from harness.dispatch import RunTaskRequest


def build_detection_dispatches(alert: dict[str, object]) -> list[RunTaskRequest]:
    detection = (alert.get("metrics") or {}).get("detection", {})
    outcome = detection.get("triage_outcome")
    if outcome not in {"investigate", "escalate"}:
        return []

    worker_id = "voice-builder" if str(alert.get("alert_type", "")).startswith("voice_") else "eng-product-qa"
    priority = "high" if outcome == "escalate" else "medium"
    return [
        RunTaskRequest(
            worker_id=worker_id,
            task_type="detection-investigate",
            task_context={
                "detection_issue": {
                    "alert_type": alert["alert_type"],
                    "triage_outcome": outcome,
                    "incident_key": detection["dedupe_key"],
                }
            },
            idempotency_key=f"detection:{detection['dedupe_key']}",
            priority=priority,
            requires_approval=outcome == "escalate",
        )
    ]
```

- [ ] **Step 4: Dispatch investigations from the evaluator**

In `harness/src/harness/detection/evaluator.py`, after creating an alert:

```python
from harness.dispatch import dispatch_job_requests
from harness.detection.dispatch import build_detection_dispatches

requests = build_detection_dispatches(alert)
if requests:
    dispatch_result = dispatch_job_requests(
        requests=requests,
        origin_worker_id="eng-product-qa",
        tenant_id=alert["tenant_id"],
        inngest_client=None,
        supabase_client=None,
    )
    alert["detection_dispatch"] = dispatch_result.__dict__
```

- [ ] **Step 5: Make `eng-product-qa` consume escalated detection context**

Update `harness/src/harness/graphs/workers/eng_product_qa.py` so escalated detection investigations summarize the issue and next owner cleanly instead of acting as the fix owner.

- [ ] **Step 6: Run the dispatch tests**

Run:

```bash
pytest harness/tests/test_detection_dispatch.py harness/tests/test_detection_evaluator.py -v
```

Expected:
- `PASS`

### Task 5: Expose Detection Through API and Filtered Founder Read Models

**Files:**
- Create: `harness/src/harness/detection/posture.py`
- Create: `harness/tests/test_detection_posture.py`
- Modify: `harness/src/harness/cockpit.py`
- Modify: `harness/src/harness/models.py`
- Modify: `harness/src/harness/server.py`
- Modify: `harness/tests/test_server.py`

- [ ] **Step 1: Write the failing posture tests**

Add `harness/tests/test_detection_posture.py` to assert a filtered issue summary is built from alerts + incidents and hides internal-only noise:

```python
from harness.detection.posture import build_detection_posture


def test_detection_posture_filters_to_meaningful_active_threads() -> None:
    posture = build_detection_posture()
    assert "active_threads" in posture
    assert "counts" in posture
    assert all(
        thread["notification_outcome"] in {"operator_notify", "founder_notify"}
        for thread in posture["active_threads"]
    )
```

Also add server tests for:
- `POST /detection/evaluate`
- `GET /cockpit/detection`

- [ ] **Step 2: Run the failing tests**

Run:

```bash
pytest harness/tests/test_detection_posture.py harness/tests/test_server.py -k detection -v
```

Expected:
- `FAIL` because the posture builder and endpoints do not exist yet

- [ ] **Step 3: Implement the detection posture builder**

Create `harness/src/harness/detection/posture.py` with a read model that joins existing records and filters by detection notification policy:

```python
from db.repository import list_alerts, list_incidents


def build_detection_posture(*, tenant_id: str | None = None) -> dict[str, object]:
    alerts = list_alerts(tenant_id=tenant_id)
    incidents = list_incidents(tenant_id=tenant_id)
    active_threads = [
        {
            "incident_id": incident["id"],
            "incident_key": incident["incident_key"],
            "workflow_status": incident["workflow_status"],
            "severity": incident["severity"],
            "current_alert_id": incident.get("current_alert_id"),
            "notification_outcome": ((alert_map.get(incident.get("current_alert_id")) or {}).get("metrics", {}).get("detection", {}).get("notification_outcome"),
        }
        for incident in incidents
        if incident.get("status") != "resolved"
        and ((alert_map.get(incident.get("current_alert_id")) or {}).get("metrics", {}).get("detection", {}).get("notification_outcome") in {"operator_notify", "founder_notify"})
    ]
    return {
        "counts": {
            "open_threads": len(active_threads),
            "founder_visible_threads": sum(1 for thread in active_threads if thread["notification_outcome"] == "founder_notify"),
        },
        "active_threads": active_threads,
    }
```

- [ ] **Step 4: Add API models and endpoints**

In `harness/src/harness/models.py`, add:

```python
class DetectionEvaluationRequest(StrictModel):
    tenant_id: Optional[str] = None
    window_minutes: int = 15
```

In `harness/src/harness/server.py`, add:

```python
@app.post("/detection/evaluate")
def evaluate_detection_endpoint(request: DetectionEvaluationRequest) -> list[dict[str, Any]]:
    return evaluate_detection(tenant_id=request.tenant_id, window_minutes=request.window_minutes)


@app.get("/cockpit/detection")
def cockpit_detection_endpoint(tenant_id: str | None = None) -> dict[str, Any]:
    return build_detection_posture(tenant_id=tenant_id)
```

- [ ] **Step 5: Project detection posture into the cockpit**

In `harness/src/harness/cockpit.py`, add a detection view helper and include it in the overview payload:

```python
from harness.detection.posture import build_detection_posture


def cockpit_overview() -> dict:
    ...
    return {
        ...,
        "detection": build_detection_posture(),
    }
```

- [ ] **Step 6: Run the posture and server tests**

Run:

```bash
pytest harness/tests/test_detection_posture.py harness/tests/test_server.py -k "detection or alert_lifecycle" -v
```

Expected:
- `PASS`

### Task 6: Thread Detection Into the Existing Office Dashboard

**Files:**
- Create: `office-dashboard/src/components/overlays/DetectionPosture.tsx`
- Create: `office-dashboard/src/app/api/detection/posture/route.ts`
- Modify: `office-dashboard/src/app/page.tsx`
- Modify: `office-dashboard/src/components/office-scene.tsx`
- Modify: `office-dashboard/src/components/overlays/DailyMemo.tsx`
- Test: `harness/tests/test_server.py`

- [ ] **Step 1: Write the failing coordination/UI tests**

Add a server-level assertion that detection posture is accessible for the office dashboard to fetch.

For the web layer, if there are no frontend tests here yet, document browser verification instead of inventing a new framework.

- [ ] **Step 2: Run the relevant test/build commands to confirm the current gap**

Run:

```bash
pytest harness/tests/test_server.py -k detection -v
cd office-dashboard && npm run lint
```

Expected:
- server tests fail or remain incomplete until the new read model is consumed
- lint may fail if new founder API calls are not wired yet

- [ ] **Step 3: Add the dashboard proxy route**

Create `office-dashboard/src/app/api/detection/posture/route.ts` so the browser can fetch filtered issue posture without direct cross-origin coupling:

```ts
import { NextResponse } from "next/server";

export async function GET() {
  const baseUrl = process.env.HARNESS_BASE_URL;
  if (!baseUrl) {
    return NextResponse.json({ error: "HARNESS_BASE_URL is required" }, { status: 500 });
  }
  const response = await fetch(`${baseUrl}/cockpit/detection`, { cache: "no-store" });
  const payload = await response.json();
  return NextResponse.json(payload, { status: response.status });
}
```

- [ ] **Step 4: Create the detection posture overlay**

Create `office-dashboard/src/components/overlays/DetectionPosture.tsx` patterned after the existing overlays. It should:
- fetch `/api/detection/posture`
- show only founder-visible issue threads
- display the top thread, count, and triage state
- stay quiet when there are no founder-visible issues

- [ ] **Step 5: Mount the overlay in the current office dashboard**

In `office-dashboard/src/components/office-scene.tsx`, mount `<DetectionPosture visible={showDetectionPosture} />`.

In `office-dashboard/src/app/page.tsx`:
- add `showDetectionPosture` state
- add a top-level stat card for founder-visible issues
- add a toggle button alongside Quest Log and Daily Memo

Optionally add a short founder-visible issue line in `DailyMemo.tsx` if the overlay is hidden.

- [ ] **Step 6: Run verification**

Run:

```bash
pytest harness/tests/test_server.py -k detection -v
cd office-dashboard && npm run lint
```

Expected:
- server tests pass
- frontend lint passes

### Task 7: End-to-End Detection Verification and Documentation Cleanup

**Files:**
- Modify: `harness/tests/test_alerts.py`
- Modify: `harness/tests/test_server.py`
- Modify: `knowledge/product/roadmap.md` only if the current roadmap text no longer matches implementation details

- [ ] **Step 1: Add one end-to-end detection scenario test**

In `harness/tests/test_server.py` or `harness/tests/test_alerts.py`, add a scenario that:
- creates voice-like job results with missing `route` / warnings
- seeds voice-like `call_records`
- runs `/detection/evaluate`
- verifies an alert is created
- verifies an incident is reused on the second run
- verifies founder posture shows one active thread, not duplicates, and hides `internal_only` alerts

- [ ] **Step 2: Run the focused detection suite**

Run:

```bash
pytest \
  harness/tests/test_detection_catalog.py \
  harness/tests/test_detection_triage.py \
  harness/tests/test_detection_evaluator.py \
  harness/tests/test_detection_dispatch.py \
  harness/tests/test_detection_posture.py \
  harness/tests/test_alerts.py \
  harness/tests/test_server.py -k "detection or alert" -v
```

Expected:
- `PASS`

- [ ] **Step 3: Run the broader regression checks**

Run:

```bash
pytest harness/tests/test_alerts.py harness/tests/test_server.py harness/tests/test_approvals.py -v
cd office-dashboard && npm run lint
```

Expected:
- alert lifecycle remains intact
- server endpoints still pass
- founder UI lint stays clean

- [ ] **Step 4: Commit**

```bash
git add knowledge/detection \
  harness/src/harness/detection \
  harness/src/harness/alerts/definitions.py \
  harness/src/harness/alerts/evaluator.py \
  harness/src/harness/alerts/notifier.py \
  harness/src/harness/cockpit.py \
  harness/src/harness/models.py \
  harness/src/harness/server.py \
  harness/src/harness/incident_classification.py \
  harness/src/harness/graphs/workers/eng_product_qa.py \
  harness/tests/test_detection_catalog.py \
  harness/tests/test_detection_triage.py \
  harness/tests/test_detection_evaluator.py \
  harness/tests/test_detection_dispatch.py \
  harness/tests/test_detection_posture.py \
  harness/tests/test_alerts.py \
  harness/tests/test_server.py \
  office-dashboard/src/app/api/detection/posture/route.ts \
  office-dashboard/src/app/page.tsx \
  office-dashboard/src/components/office-scene.tsx \
  office-dashboard/src/components/overlays/DetectionPosture.tsx \
  office-dashboard/src/components/overlays/DailyMemo.tsx
git commit -m "feat: add detection plane foundation"
```

## Notes for the Implementer

- Do not add a new `detections` or `issue_threads` table in this slice.
- Keep detection metadata nested under existing alert payloads unless a file proves that impossible.
- Reuse `incidents` as the durable dedupe object.
- Keep `/alerts/evaluate` backward-compatible by delegating through the detection evaluator rather than removing the existing endpoint.
- Do not let detection outcomes masquerade as truth or governance verdicts in API names or payloads.
- Do not read voice signal inputs from `jobs`; use `call_records` or an explicit repository helper that exposes the same fields.
