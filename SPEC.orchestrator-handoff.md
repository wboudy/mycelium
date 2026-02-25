# Orchestrator Handoff and Escalation Spec
Version: 0.4
Status: Draft

## 1. Purpose

Define how mid-implementation bug interrupts are routed safely:

1. Preserve the existing Mycelium workflow and skill context.
2. Add watcher-driven orchestration for `model:deep` bug beads.
3. Prevent alert fatigue with trivial-fix gating and time-aware escalation.
4. Prevent infinite orchestration loops with explicit FSM + retry limits.

## 2. Relationship to Existing Workflow

This is not a replacement for existing skills. It is a control-plane extension.

- `mycelium-bug-interrupt` skill:
  - Splits blocker into bug bead.
  - Blocks origin bead.
  - Labels bug bead (`model:deep`, `needs:orchestrator`).
- Watcher (new):
  - Detects and routes queued beads.
  - Enforces FSM, retries, cooldown, escalation policy.
- Orchestrator runner (existing/new command wrapper):
  - Executes the routed bead using configured model.

## 3. System Components

| Component | Responsibility |
|---|---|
| Worker Skill | Emits structured handoff intent on bug bead |
| Watcher Loop | Polls `bd` for queued handoffs and drives state transitions |
| Locking | Ensures only one watcher claims a handoff at a time |
| Orchestrator Command | Runs the selected model for one bead |
| Escalation Sink | Marks `needs:human` and optionally sends notification |

## 4. Handoff Signals

### 4.1 Required Labels on Spawned Bug Bead

- `interrupt`
- `root-cause`
- `model:deep`
- `needs:orchestrator`

### 4.2 Optional Labels

- `triage:trivial-candidate` (worker believes inline/cheap fix is plausible)
- `customer-impact` (enables off-hours high-priority paging)

### 4.3 Required Notes Block

Worker appends a structured block to bead notes:

```yaml
handoff:
  origin_id: <origin-bead-id>
  bug_id: <bug-bead-id>
  error_signature: <stable-short-signature>
  expected_minutes: <int>
  estimated_loc: <int>
  touches_api_or_schema: <bool>
  touches_security_or_auth: <bool>
  quick_test_available: <bool>
```

If this block is missing, watcher treats the bead as non-trivial.

## 5. Finite State Machine

State is represented using labels and retry metadata in notes.

### 5.1 States

| State | Label Contract |
|---|---|
| `QUEUED` | `needs:orchestrator` present, `orchestrator:running` absent |
| `RUNNING` | `orchestrator:running` present |
| `RETRY_WAIT` | `orchestrator:failed` present and retry cooldown active |
| `DONE` | `orchestrator:done` present, `needs:orchestrator` absent |
| `HUMAN_REQUIRED` | `needs:human` present |

### 5.2 Transitions

1. `QUEUED -> RUNNING`
   - Preconditions: watcher lock acquired, bead claim succeeds.
   - Actions: add `orchestrator:running`, remove `needs:orchestrator`.
2. `RUNNING -> DONE`
   - Preconditions: orchestrator returns success.
   - Actions: remove `orchestrator:running`, add `orchestrator:done`.
3. `RUNNING -> RETRY_WAIT`
   - Preconditions: orchestrator fails and retry_count < max_retries.
   - Actions: remove `orchestrator:running`, add `orchestrator:failed` + cooldown metadata.
4. `RUNNING/RETRY_WAIT -> HUMAN_REQUIRED`
   - Preconditions: retry_count >= max_retries, or failure classified as non-retriable.
   - Actions: add `needs:human`, remove `needs:orchestrator` and `orchestrator:running`.

## 6. Trivial Fix Policy

Goal: keep humans out of low-risk noise.

Watcher auto-resolves without escalation only when all are true:

1. `expected_minutes <= 10`
2. `estimated_loc <= 30`
3. `touches_api_or_schema == false`
4. `touches_security_or_auth == false`
5. `quick_test_available == true`
6. Attempts so far <= 2

If any check fails, route through standard orchestrator flow.

## 7. Retry and Loop Prevention

### 7.1 Retry Defaults

- `max_retries = 3`
- Backoff schedule: `1m`, `5m`, `15m`

### 7.2 Loop Guards

1. Single active watcher via lock file (for example `.beads/orchestrator-watch.lock`).
2. Idempotency key:
   - `handoff_key = sha1(origin_id + ":" + bug_id + ":" + error_signature)`
3. Never process bead in `RUNNING` or `DONE`.
4. Do not requeue a `HUMAN_REQUIRED` bead automatically.

## 8. Human Escalation Policy

### 8.1 Escalation Triggers

- Retry budget exhausted.
- Non-retriable failure class (auth, permissions, malformed input).
- Explicit high-risk flags from triage.

### 8.2 Time-Aware Notification

- Business hours (default local weekday `09:00-18:00`):
  - Raise `needs:human` immediately.
- Off-hours:
  - Immediate human notification only for P0/P1 or `customer-impact`.
  - Else queue (`notify:queued`) and schedule next business-hour notification.

### 8.3 Human Reach-Out Channels

Minimum required: bead labels + notes (`needs:human`, structured failure summary).

Optional integrations:
- Slack webhook
- Email endpoint
- Pager for critical severities only

## 9. Command Contract (Watcher)

Watcher executes a configured command template per claimed bead:

```bash
<orchestrator_cmd> --bead-id <bug_id> --model deep
```

Notes:
- Actual command remains configurable to avoid coupling this spec to one CLI shape.
- Watcher must capture exit code and append summary notes.

## 10. Observability

Watcher appends machine-parseable notes per attempt:

```yaml
watcher_run:
  handoff_key: <hash>
  state_from: <state>
  state_to: <state>
  attempt: <int>
  result: success|retry|human_required
  error_class: <optional>
  policy_version: <optional-policy-hash>
  replay_artifact: <optional-run-file-path>
  capsule_artifact: <optional-repro-capsule-path>
  risk_budget_decision: <optional-allow|defer|bypass-critical>
  signature_trust_score: <optional-0-to-1>
  timestamp: <ISO-8601 UTC>
```

## 11. Acceptance Criteria

1. Bug beads labeled `needs:orchestrator` are claimed and routed exactly once per attempt.
2. FSM transitions are valid and auditable in bead labels/notes.
3. A failing handoff never retries more than `max_retries`.
4. `needs:human` is set automatically when retry budget is exhausted.
5. Off-hours policy suppresses non-critical immediate paging.
6. Original implementation bead remains blocked until blocker bug is closed.
7. Daily digest is generated and delivered during business hours with escalation summary.
8. Duplicate human notifications for same signature are suppressed within dedupe window.
9. Stale `RUNNING` beads are auto-reconciled without manual intervention.
10. Watcher policy is loaded from versioned config and passes static validation before startup.
11. Any executed handoff attempt is replayable in deterministic dry-run mode.
12. Daily digest includes incident clusters with blast-radius ordering.
13. Failed or escalated handoffs include a sanitized reproducibility capsule.
14. Human escalation flow respects configurable daily risk budget with critical bypass.
15. Model-routing decisions incorporate signature trust history and are auditable.

## 12. Out of Scope (This Spec)

- Full implementation of notification providers.
- Model-specific prompt engineering details.
- Replacing existing manual `mycelium-next` workflow.

## 13. Next Implementation Steps

1. Add watcher script (`src/mycelium/handoff_watcher.py`).
2. Add CLI command (`mycelium-py watch-handoffs`).
3. Add tests:
   - FSM transitions
   - Retry ceilings
   - Off-hours escalation routing
   - Trivial-fix gate behavior
4. Update `mycelium-bug-interrupt` to emit required handoff block.

## 14. Detailed Implementation Plan

### 14.1 Phase 1: Core Reliability

1. Replace basic lock with lease lock + heartbeat.
   - Lock file: `.beads/orchestrator-watch.lock`
   - Lease fields: `owner_id`, `pid`, `started_at`, `last_heartbeat`
   - Heartbeat interval: 10s
   - Stale lease timeout: 45s
2. Add persistent idempotency store.
   - File: `.beads/orchestrator-handoff-state.json`
   - Keys: `handoff_key`, `state`, `attempt`, `last_transition_at`
   - Required invariant: same `handoff_key` cannot execute concurrently.
3. Add stale-run reconciler pass before each poll iteration.
   - If bead labeled `orchestrator:running` and heartbeat stale:
     - transition to `RETRY_WAIT`
     - append recovery note
4. Enforce strict handoff schema validation.
   - Missing required fields => `needs:human` with `error_class=schema_invalid`
   - No execution attempt allowed on invalid payload.
5. Add dead-letter state.
   - Label: `orchestrator:dead`
   - Enter when retry cap reached or hard non-retriable failure occurs.
   - Must always co-occur with `needs:human`.

### 14.2 Phase 2: Signal Quality and Human Load Control

1. Add notification dedupe window.
   - Key: `origin_id + error_signature + error_class`
   - Suppression window: 60 minutes
2. Add daily human digest.
   - Delivery window: next business-hour window (default 09:30 local)
   - Content:
     - New escalations
     - Dead-letter items
     - Top recurring signatures
     - Retry trend and success ratio
3. Add off-hours queuing policy.
   - P0/P1 or `customer-impact`: immediate notify
   - P2+: queue for digest unless explicit urgent override
4. Add escalation priority scoring for digest order.
   - Inputs: priority, customer-impact, retries, age
   - Output: deterministic sort for human triage.

### 14.3 Phase 3: Adaptive and Advanced Behaviors

1. Add shadow mode.
   - Watcher computes transitions and logs "would-run" outcomes without execution.
   - Exit criterion: 7-day false-positive rate under threshold.
2. Add trivial-fix confidence scoring.
   - Start rule-based; persist prediction vs outcome.
   - Track precision/recall weekly for threshold tuning.
3. Add adaptive retry backoff.
   - Repeated identical transient infra failures => longer cooldown.
   - Unique/first-time transient failures => default schedule.
4. Add daily quality report.
   - Metrics:
     - Auto-resolve rate
     - Human escalation rate
     - Mean time to recovery
     - Loop prevention interventions

### 14.4 Selected Enhancements (Top 3)

The following three additions were selected after evaluating ten candidates.

1. Policy-as-code with static verifier.
   - Source file: `.mycelium/orchestrator-policy.yaml`
   - Startup hard-fail conditions:
     - unreachable FSM states
     - conflicting escalation rules
     - overlapping time-window rules without precedence
   - Persist policy hash in every `watcher_run.policy_version`.
2. Deterministic replay harness ("flight recorder").
   - Persist per-attempt run artifact:
     - `.beads/orchestrator-runs/<handoff_key>/<attempt>.jsonl`
   - Artifact must include:
     - labels and notes snapshot
     - evaluated policy hash
     - local-time window decision path
     - orchestrator command envelope (exit code, parsed status)
   - Add command:
     - `mycelium-py replay-handoff --run-file <path> --dry-run`
3. Incident-cluster digest intelligence.
   - Build derived incident graph keyed by `error_signature`.
   - Cluster features:
     - connected origin beads
     - affected components (if labeled)
     - escalation outcomes and age
   - Daily digest ordering:
     - cluster risk first (priority, spread, age, human impact)

### 14.5 Selected Enhancements (Top 3, New Iteration)

1. Reproducibility capsule generator.
   - For every failure or escalation, persist a sanitized capsule:
     - `.beads/orchestrator-capsules/<handoff_key>/<attempt>.md`
   - Capsule must include:
     - minimal reproduction steps
     - observed vs expected behavior
     - exact command envelope and key logs
     - environment metadata (timezone, policy hash, run id)
   - Capsule path is recorded in `watcher_run.capsule_artifact`.
2. Daily human risk-budget governor.
   - Add policy knobs:
     - `max_noncritical_escalations_per_day`
     - `max_noncritical_pages_per_hour`
   - Decision rules:
     - critical (`P0/P1` or `customer-impact`) always bypass budget
     - noncritical over-budget items are deferred to digest queue
   - Decision is recorded in `watcher_run.risk_budget_decision`.
3. Signature trust ledger for routing.
   - Persist per-signature historical outcomes:
     - auto-resolve success rate
     - mean retries
     - human-escalation rate
   - Use score to route:
     - high trust => cheaper/shallower path first
     - low trust => deep model earlier + stricter guardrails
   - Score is recorded in `watcher_run.signature_trust_score`.

## 15. Failure Modes and Mitigation Plan

### 15.1 Two Watchers Claim Same Bead

- Failure mode: duplicate execution due to race.
- Prevention:
  - Lease lock with heartbeat.
  - Atomic claim transition: add `orchestrator:running` and remove `needs:orchestrator` in one guarded update.
- Detection:
  - Invariant check: no bead may have multiple active watcher owners.
  - Alert on duplicate `RUNNING` notes for same `handoff_key`.
- Recovery:
  - Keep earliest owner; demote later owner attempt to no-op.
  - Append conflict note and continue with single owner.

### 15.2 Stuck `RUNNING` After Crash/Reboot

- Failure mode: orphaned in-flight state blocks progress.
- Prevention:
  - Heartbeat required while running.
  - Max run duration per attempt (for example 20m).
- Detection:
  - Reconciler identifies stale heartbeat or exceeded runtime.
- Recovery:
  - Transition to `RETRY_WAIT` with `error_class=stale_run`.
  - Increment attempt and schedule backoff.

### 15.3 Origin/Bug Loop Due to Dependency Cleanup Drift

- Failure mode: bug closes but origin remains blocked or re-enters interrupt loop repeatedly.
- Prevention:
  - Resume workflow must remove dependency and set origin `in_progress`.
  - Enforce max re-interrupt count per origin+signature.
- Detection:
  - Repeated interrupts with same signature over threshold.
  - Closed bug with origin still blocked beyond grace period.
- Recovery:
  - Auto-open follow-up bead with `needs:human`.
  - Mark pair as circuit-broken; stop auto re-interrupt for that signature.

### 15.4 Timezone/DST Escalation Mistakes

- Failure mode: notifications sent in wrong window.
- Prevention:
  - Store schedule in explicit IANA timezone, not UTC offsets.
  - Normalize all internal timestamps to UTC + timezone conversion at evaluation.
- Detection:
  - Emit evaluated window metadata in logs (`local_time`, `tz`, `policy_path`).
  - Add DST boundary tests.
- Recovery:
  - If schedule ambiguity detected, fall back to safe mode:
    - queue non-critical
    - immediately notify critical.

### 15.5 Partial Success with Non-Zero Exit

- Failure mode: orchestrator changed bead state but process exits as failure.
- Prevention:
  - Command contract must support structured status output (success/failure + action id).
  - Idempotent side effects keyed by `handoff_key` + `attempt`.
- Detection:
  - Post-run state reconciliation compares expected vs actual labels/notes.
- Recovery:
  - If state indicates success, transition to `DONE` and record `result=success_with_exit_mismatch`.
  - Else treat as retriable failure.

### 15.6 Manual Label Edits Break FSM Invariants

- Failure mode: impossible combinations (for example `needs:orchestrator` + `orchestrator:done`).
- Prevention:
  - Invariant validator runs each loop and before transitions.
  - Optional protected-label policy for orchestrator-owned labels.
- Detection:
  - Validator emits `fsm_invalid` with full label snapshot.
- Recovery:
  - Auto-normalize to nearest valid state when unambiguous.
  - Escalate to `needs:human` when ambiguous.

### 15.7 `bd` Staleness and Sync Inconsistency

- Failure mode: watcher acts on stale issue view.
- Prevention:
  - Poll cycle includes `bd sync --status` health check.
  - Use monotonic snapshot token and skip processing when stale warning present.
- Detection:
  - Mismatch between local bead state and command write result.
  - Repeated optimistic-update failures.
- Recovery:
  - Refresh state, retry once with jitter.
  - If mismatch persists, set `needs:human` with `error_class=state_divergence`.

## 16. Additional Test Matrix

1. Lease handoff race simulation with two watcher instances.
2. Crash/restart stale heartbeat reconciliation.
3. DST transition cases for off-hours policy.
4. Duplicate notification suppression in dedupe window.
5. Partial-success exit mismatch reconciliation.
6. Manual label corruption auto-normalization.
7. Dead-letter transition after max retries.
8. Daily digest generation with mixed severities and dedupe.
9. Policy verifier rejects contradictory or unreachable rule sets.
10. Replay harness reproduces identical transitions under deterministic inputs.
11. Incident-cluster digest groups related signatures and ranks by blast radius.
12. Reproducibility capsule generation validates completeness and redaction rules.
13. Risk-budget governor enforces quotas while always allowing critical bypass.
14. Signature trust ledger updates deterministically and changes routing as expected.
