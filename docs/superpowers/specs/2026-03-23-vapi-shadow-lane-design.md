# Vapi Shadow Lane Design

**Date:** March 23, 2026
**Status:** Draft
**Owner:** Founder

## Summary

Introduce a `vapi-shadow` evaluation lane alongside the current Retell inbound HVAC receptionist. Phase 1 does not route customer traffic to Vapi. Instead, it runs offline replay against a curated bank of audio fixtures using a Vapi assistant configured to match the existing inbound HVAC receptionist contract. Phase 1 also includes the minimum neutral benchmark needed to compare Retell and Vapi fairly on that contract. The next implementation plan should cover Phase 1 only. Phases 2 through 4 are roadmap context for later specs and later planning.

The key design constraint is boundary discipline. Vapi should own conversation orchestration, endpointing, interruption behavior, and voice-pipeline tuning. This repo should continue to own tenant resolution, tool business logic, persistence, post-call extraction, and reporting. That keeps the comparison apples-to-apples and avoids forking domain logic across providers.

`autovoiceevals` is explicitly not the benchmark authority in phase 1. It is an optimization loop for Vapi after the neutral benchmark exists. It can improve prompts and adversarial robustness, but it does not define pass/fail for provider graduation.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Initial scope | Inbound HVAC receptionist only | Matches the current Retell production scope and avoids widening the comparison surface before parity exists. |
| Rollout mode | Offline replay of curated audio fixtures only | Lowest-risk way to compare providers without customer exposure while still measuring latency and interruption behavior. |
| Success standard | Balanced gate | Vapi must achieve near-parity on quality and a material latency or cost advantage. |
| Benchmark owner | Repo-native neutral harness | Prevents provider-specific tooling from becoming the source of truth. |
| Business logic ownership | Existing repo services remain canonical | Avoids drift between Retell and Vapi behavior. |
| Tool transport for Vapi | Thin adapter endpoints first, MCP optional after parity | Fastest route to a fair comparison; MCP is a later leverage point, not a phase-1 requirement. |
| Optimization tooling | Add `autovoiceevals` after baseline benchmark is stable | Keeps optimization separate from judging. |
| Production promotion | Explicit graduation gate only after repeated benchmark wins | Avoids premature migration based on anecdotal speed impressions. |

## 1. Goals And Non-Goals

### Goals

- Build a Vapi-based shadow receptionist for the same inbound HVAC call contract Retell currently handles.
- Create a neutral benchmark that scores both providers on full-conversation performance, not just post-call extraction.
- Reuse existing call tools, tenant routing, extraction logic, and reporting wherever possible.
- Make it obvious why one provider wins or loses by separating latency, interruption handling, tool correctness, and downstream extraction quality.

### Non-Goals

- No customer-facing cutover in phase 1.
- No expansion into outbound, internal operations, or non-HVAC packs.
- No provider-specific business logic forks.
- No assumption that MCP is required to beat Retell; phase 1 should prove parity before deeper platform specialization.
- No booking scenarios in the initial wedge.

## 2. Architectural Boundary

Retell remains the live production receptionist. Vapi is added as a parallel evaluation target only.

The correct boundary is:

- **Provider-owned concerns:** real-time speech pipeline, endpointing, interruption handling, transcript generation, assistant prompt/runtime behavior.
- **Repo-owned concerns:** tenant resolution, tool execution, business rules, persistence, extraction/classification, eval storage, and comparison reporting.

This means the Vapi assistant should call into the same domain operations already represented by the Retell stack:

- caller lookup
- callback request creation
- sales lead alerting

For phase 1, Vapi should reach those operations through thin compatibility endpoints that wrap the existing Python business logic. The compatibility layer translates Vapi-native tool requests into the repo’s canonical function signatures and returns normalized responses. The underlying domain code remains shared.

Booking is out of scope for the first implementation plan. If booking is later added to the provider comparison, that should be treated as a deliberate scope expansion after parity is proven on the narrower receptionist wedge.

## 3. Phased Delivery

### Phase 1: Contract Parity Plus Minimum Benchmark

Build a Vapi assistant for the inbound HVAC receptionist contract and run only offline replay against curated audio fixtures. This phase includes the minimum provider-neutral benchmark required to judge parity on the chosen wedge. The output of this phase is a fair comparison lane, not a production-ready migration.

Deliverables:

- Vapi assistant configuration for inbound HVAC receptionist flows
- Vapi compatibility tool adapter endpoints
- curated audio fixtures for offline replay
- normalized artifact capture for Vapi runs
- initial scenario bank covering the current receptionist scope
- minimum shared scorecard for latency, interruption recovery, tool correctness, and downstream extraction parity
- file-backed benchmark artifacts plus CLI comparison reporting

### Phase 2: Benchmark Hardening

Extend the phase-1 benchmark into a more robust conversation benchmark with stronger persistence, richer reporting surfaces, broader scenario coverage, and stricter thresholds.

Deliverables:

- durable benchmark persistence beyond file-backed artifacts
- richer reporting surfaces beyond CLI comparison output
- historical benchmark snapshots for regression tracking
- expanded scenario coverage and stricter promotion thresholds

### Phase 3: Vapi Optimization

Once the benchmark is stable, optimize Vapi’s speech stack and prompt behavior. This is where endpointing, interruption sensitivity, speech wait timing, and TTS/STT model choices become first-class tuning inputs.

Deliverables:

- tunable Vapi pipeline presets
- scenario-driven parameter sweeps
- `autovoiceevals` integration for adversarial prompt improvement

### Phase 4: Graduation

If Vapi repeatedly clears the gate, move to higher-risk validation such as mirrored controlled calls or limited routing. This phase requires a separate spec.

## 4. Benchmark Architecture

The current repo evaluator at `scripts/run-voice-eval.py` only compares post-call extraction output against `knowledge/voice-pipeline/eval/golden-set.yaml`. That remains useful, but it is insufficient for deciding whether Vapi can outperform Retell as a receptionist.

The benchmark must become a repo-native, provider-neutral pipeline with these layers. Phase 1 builds the minimum viable version of this pipeline; phase 2 strengthens it rather than introducing it for the first time.

### Layer 1: Objective Telemetry

- first-response latency
- median turn latency
- p95 turn latency
- tool round-trip latency
- interruption recovery timing
- hard failures and retries

### Layer 2: Contract Correctness

- correct caller name, phone, address, and problem capture
- correct routing outcome
- correct tool choice
- correct tool arguments
- correct callback or escalation outcome within the initial wedge

### Layer 3: Downstream Business Quality

- transcript quality sufficient for extraction
- extraction parity when fed through the existing post-call pipeline
- classification parity for urgency, route, issue type, and tags

Each provider should produce one normalized `voice_eval_run` artifact shape containing:

- provider name and versioned config
- scenario id
- transcript
- per-turn timestamps
- interruption events
- tool call log
- final call outcome
- post-call extraction output
- provider cost metadata for the run
- benchmark scores and failure reasons

## 5. Data Flow

The phase-1 data flow should look like this:

1. A scenario runner selects a curated HVAC receptionist audio fixture.
2. The runner executes the scenario against Retell and Vapi independently.
3. Each provider adapter captures native artifacts and maps them into the shared eval format.
4. The shared scorer computes telemetry, correctness, and downstream extraction results.
5. Results are stored and diffed against the Retell baseline.
6. Reports show where Vapi wins, loses, or ties.

```text
Scenario Bank
  -> Provider Runner (Retell)
  -> Provider Runner (Vapi)
      -> Provider Adapter
      -> Normalized Eval Artifact
          -> Shared Scorecard
              -> Stored Benchmark Run
                  -> Comparison Report
```

This design allows provider substitution without rewriting the benchmark core.

Replay modality for phase 1 is fixed as `offline replay of curated audio fixtures`. Text transcripts can still be used for cheaper extraction-only regression checks, but phase-1 provider comparison must use audio fixtures so latency, endpointing, interruption behavior, and transcript quality are measured from comparable inputs.

## 6. Components

Recommended component split:

- `harness/src/voice_eval/` for provider-neutral benchmark models and scoring
- `harness/src/voice_eval/providers/retell.py` for Retell artifact normalization
- `harness/src/voice_eval/providers/vapi.py` for Vapi artifact normalization
- `harness/src/voice_eval/scenarios/` for synthetic and replay scenario definitions
- `scripts/run-voice-benchmark.py` as the main benchmark entrypoint
- `scripts/run-voice-eval.py` retained for extraction-only regression checks

Recommended data structures:

- `VoiceEvalScenario`
- `VoiceEvalRun`
- `VoiceEvalTurn`
- `VoiceEvalToolCall`
- `VoiceEvalScorecard`
- `VoiceEvalComparison`

The benchmark package should not embed provider-specific scoring assumptions. Provider adapters convert raw artifacts into shared types; the scorecard consumes only shared types.

## 7. Vapi Integration Shape

Phase 1 should use the smallest Vapi integration surface that yields a fair comparison.

Recommended shape:

- configure one Vapi assistant for inbound HVAC receptionist scenarios
- use thin tool adapter endpoints in the existing repo
- start with direct tool compatibility wrappers
- defer MCP-specific wiring until parity exists or a concrete tool-control gap appears

Rationale:

- direct compatibility wrappers are simpler to debug
- they preserve canonical repo business logic
- they avoid conflating transport innovation with receptionist quality

MCP remains strategically interesting because it can later reduce custom glue and widen tool access. It should be treated as a phase-3 optimization or phase-4 expansion lever, not a phase-1 dependency.

## 8. `autovoiceevals` Integration

`autovoiceevals` should be introduced only after:

- the Vapi assistant is benchmarkable
- the shared scorecard is stable
- the scenario bank covers the receptionist wedge credibly

Its role is:

- generate adversarial scenarios
- mutate prompt variants
- run keep/revert optimization loops
- improve Vapi robustness against edge-case callers

Its role is not:

- define the canonical benchmark
- replace the shared scorecard
- decide promotion on its own

The integration should write its trial outputs back into the same benchmark artifact store so optimized variants can be compared against the same neutral rubric.

## 9. Promotion Gate

Vapi can only advance beyond the shadow lane if all three categories are satisfied.

### Quality Floor

Vapi must achieve parity or near-parity on:

- required field capture
- tool success and correctness
- final receptionist outcome
- downstream extraction/classification quality

### Performance Edge

Vapi must show at least one material advantage without quality regression:

- better median latency
- better p95 latency
- lower cost per completed scenario

### Reliability Floor

Vapi must not introduce a worse failure mode than Retell in:

- interruption handling
- endpointing stability
- tool retry behavior
- transcript degradation severe enough to harm downstream extraction

One fast configuration winning once is not enough. Graduation requires repeated benchmark wins across a stable scenario bank.

## 10. Error Handling And Observability

The benchmark system must preserve enough evidence to debug provider failures without replay ambiguity.

Requirements:

- store raw provider artifacts alongside normalized eval artifacts
- record scoring failures with explicit reasons instead of aggregate pass/fail only
- distinguish provider transport failures from benchmark-runner failures
- retain tool payloads and timing for failed scenarios
- flag whether a loss came from latency, tool misuse, interruption behavior, or downstream extraction

This is especially important because phase 1 is intended to answer why Vapi underperforms if it does.

## 11. Testing Strategy

Testing should proceed in four layers:

### Unit Tests

- normalized model validation
- provider adapter transformations
- scorecard calculations
- threshold and gate logic

### Fixture Tests

- replay scenario fixtures
- synthetic scenario expected outcomes
- transcript and tool-call normalization correctness

### Integration Tests

- Vapi compatibility endpoint behavior
- benchmark runner end-to-end against mocked provider responses
- shared scorer feeding existing extraction pipeline

### Regression Tests

- fixed benchmark suite run on both providers
- historical comparison against prior benchmark snapshots
- `autovoiceevals`-produced prompt variants checked against the neutral benchmark before acceptance

## 12. Risks And Open Questions

### Main Risks

- Vapi transcript artifacts may not map cleanly enough to the current downstream extraction assumptions.
- Retell and Vapi may expose different timing primitives, making some latency comparisons noisy until normalized carefully.
- Prompt optimization can overfit to adversarial scenarios if it is not checked against the neutral benchmark.

### Open Questions Deferred From This Spec

- exact storage location and schema for benchmark run persistence
- exact minimum sample size for promotion decisions
- whether benchmark reporting lives in the customer-facing app, internal office dashboard, or a separate internal surface

These are planning-level details, not blockers for the design.

## 13. Success Criteria

This spec is successful if the implementation plan it produces would let the team answer all of the following:

- Can Vapi match the current inbound HVAC receptionist contract without forking business logic?
- Can the repo measure full-conversation quality neutrally across Retell and Vapi?
- Can `autovoiceevals` improve Vapi without becoming the judge of success?
- Is there a defensible, evidence-based gate for deciding whether Vapi should progress past the shadow lane?

## References

- Existing extraction evaluator: `scripts/run-voice-eval.py`
- Existing golden set: `knowledge/voice-pipeline/eval/golden-set.yaml`
- Existing Retell tool surface: `harness/src/voice/router.py`
- Existing post-call integration tests: `harness/tests/voice/test_post_call_pipeline.py`
- Vapi voice pipeline configuration: https://docs.vapi.ai/customization/voice-pipeline-configuration
- Vapi MCP integration: https://docs.vapi.ai/tools/mcp
- autovoiceevals: https://github.com/ArchishmanSengupta/autovoiceevals
