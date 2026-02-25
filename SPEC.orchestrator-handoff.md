# Orchestrator Handoff and Escalation Spec
Version: 0.1
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
  timestamp: <ISO-8601 UTC>
```

## 11. Acceptance Criteria

1. Bug beads labeled `needs:orchestrator` are claimed and routed exactly once per attempt.
2. FSM transitions are valid and auditable in bead labels/notes.
3. A failing handoff never retries more than `max_retries`.
4. `needs:human` is set automatically when retry budget is exhausted.
5. Off-hours policy suppresses non-critical immediate paging.
6. Original implementation bead remains blocked until blocker bug is closed.

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
