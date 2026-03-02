# Agent Instructions (Mycelium)

## 1) Scope and Source of Truth

This file governs work in the Mycelium knowledge vault project.

- **What this project is**: A local-first, Obsidian-compatible knowledge vault with a human-gated 7-stage ingestion pipeline (capture, normalize, fingerprint, extract, compare, delta, propose_queue), deduplication engine, review queue, graduation workflow, egress security, and graph analysis.
- **Primary spec**: `docs/plans/mycelium_refactor_plan_apr_round5.md`.
- **Source code**: `src/mycelium/` (pipeline stages in `stages/`, commands in `commands/`, MCP server in `mcp/`).
- **Tests**: `tests/` (2300+ tests).
- This repo uses a single worktree model.

### Key architectural rules

- **Canonical Scope** (`Sources/`, `Claims/`, `Concepts/`, `Questions/`, `Projects/`, `MOCs/`) is writable only through the `graduate` command.
- **Draft Scope** (`Inbox/`, `Reports/`, `Logs/`, `Indexes/`, `Quarantine/`) is agent-writable.
- All vault persistence must use `atomic_write_text()` from `atomic_write.py` (temp file + `os.replace`).
- All YAML serialization must use `yaml.safe_dump()`, never `yaml.dump()`.
- User-supplied path components must be validated with `sanitize_path_component()`.
- Every command returns an `OutputEnvelope` (defined in `models.py`).

## 2) Precedence

Instruction precedence is:
1. system/developer/user directives
2. this file

When directives conflict, follow higher precedence and document any deviation in handoff.

## 3) Issue Tracking (`br`)

Use `br` (beads_rust) as primary tracker.

```bash
br onboard
br ready
br show <id>
br update <id> --status in_progress
br close <id>
br sync --flush-only
```

`br` does not run git commands. Persist `.beads` changes manually when needed.

## 4) Role Separation

There are two roles. Use only the section for your current role.

- `orchestrator`: coordination, pane routing, prompt delegation, merge/review synthesis.
- `worker`: implementation, testing, validation, and artifact production.

Default assumption:
- If not explicitly assigned orchestrator duties, act as `worker`.

Role switch rule:
- A role switch must be explicit in user/captain instructions.

## 5) Worker Contract

Workers MUST:
- Focus on assigned implementation/review task only.
- Claim work before substantive edits.
- Run relevant validation before closing.
- Escalate blockers immediately with follow-up issue artifacts.

Workers MUST NOT:
- Re-route prompts across panes.
- Broadcast orchestration messages.
- Invoke orchestrator-only skills unless explicitly switched to orchestrator role.

## 6) Orchestrator Contract

Orchestrator MUST:
- Be phase-aware (discovery -> spec closure -> decomposition -> implementation -> validation).
- Use palette-first delegation for pane prompts.
- Perform state-aware routing (do not interrupt active workers).
- Use send-confirm delivery (send, enter, capture verify).

Orchestrator SHOULD:
- Resolve decomposition ambiguity before spawning implementation swarms.
- Keep worker prompts task-scoped with explicit done criteria.

## 7) Worker Prompt Contract (Required)

When orchestrator delegates to a worker, prompt MUST start with this preamble:

```text
ROLE: WORKER
PHASE: <PLANNING|IMPLEMENTATION|VALIDATION>
TASK: <single concrete task>
CONTEXT: <paths/spec ids only>
OUTPUT: <exact file/artifact path>
DONE: <explicit completion marker>
```

Worker-side interpretation:
- If prompt says `ROLE: WORKER`, ignore orchestrator responsibilities and execute only worker contract.
- Worker should begin first response line with `ROLE_ACK: WORKER`.
- If `ROLE_ACK: WORKER` is missing, orchestrator should resend with a short role-reset prompt.

## 8) Quality Gates

Fail-closed policy:
- Do not declare completion while required checks fail unless user explicitly approves exception.

For behavior changes, include:
- happy path test
- edge case test
- error path test
- regression test

Run `pytest` and confirm all tests pass before closing work.

## 9) Canonical Update Boundary

- Canonical updates must follow spec-defined promotion flow (via `graduate`).
- Ingest/draft steps must not mutate canonical directories directly.
- Any emergency bypass requires explicit user authorization + audit note.

## 10) Destructive Action Policy

- No destructive commands without explicit user permission.
- If impact is uncertain, stop and ask.
- Record destructive action audit in handoff:
  - authorization text
  - exact command
  - affected scope
  - timestamp

## 11) Session Completion (Landing)

Work is not complete until pushed.

```bash
git pull --rebase
br sync --flush-only
git add .beads/        # if changed
git commit -m "sync beads"  # if needed
git push
git status
```

`git status` must be clean or explicitly explain remaining local work.

## 12) Handoff Minimum Schema

Every handoff should include:
- issue id(s) + state
- files changed
- tests/commands run + outcomes
- blockers + owner + next action
- policy exceptions (if any)

## 13) Beads Workflow

This project uses beads_rust (`br`) for issue tracking. Issues are stored in `.beads/` and tracked in git.

### Essential Commands

```bash
br ready              # Show issues ready to work (no blockers)
br list --status=open # All open issues
br show <id>          # Full issue details with dependencies
br create --title="..." --labels=task --priority P2
br update <id> --status in_progress
br close <id> --reason="Completed"
br sync --flush-only  # Export to JSONL
```

### Workflow Pattern

1. **Start**: Run `br ready` to find actionable work.
2. **Claim**: `br update <id> --status in_progress`
3. **Work**: Implement the task.
4. **Complete**: `br close <id>`
5. **Sync**: Always run `br sync --flush-only` at session end.

### Key Concepts

- **Dependencies**: Issues can block other issues. `br ready` shows only unblocked work.
- **Priority**: P0=critical, P1=high, P2=medium, P3=low, P4=backlog.
- **Labels**: task, bug, feature, epic, question, docs.

### Session Protocol

```bash
git status              # Check what changed
git add <files>         # Stage code changes
br sync --flush-only    # Export beads
git add .beads/         # Stage beads changes
git commit -m "..."     # Commit
git push                # Push to remote
```
