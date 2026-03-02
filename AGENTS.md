# Agent Instructions (Mycelium)

## 1) Scope and Source of Truth

This file governs work in `/Users/will/Developer/mycelium/mycelium`.

- Primary implementation spec: `docs/plans/mycelium_refactor_plan_apr_round5.md`.
- Planning artifacts and council outputs: `plans/`.
- This repo now uses a single worktree model.

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

## 4) Role Separation (Critical)

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

Guidance:
- Yes, include `ROLE: WORKER` explicitly. This reduces role drift.
- Keep one primary task per prompt.
- Include requirement IDs or file paths for grounding.

Worker-side interpretation:
- If prompt says `ROLE: WORKER`, ignore orchestrator responsibilities and execute only worker contract.
- Worker should begin first response line with `ROLE_ACK: WORKER`.
- If `ROLE_ACK: WORKER` is missing, orchestrator should resend with a short role-reset prompt before delegating further.

## 8) Palette and Orchestration Prompts

Planning/decomposition keys currently available:
- `plan`
- `merge_plan`
- `merge_paths`
- `decompose`
- `review_beads`
- `review_master_plan_v2`
- `swarm_beads`
- `braindump_plan`

Rule:
- `swarm_beads` is implementation-phase only.
- Do not use implementation swarm prompts during spec-closure/decomposition.

## 9) Ambiguity Gate Before Decomposition

Do not decompose into beads while blocking ambiguities remain.

Blocking examples:
- contradictory dependency order
- unresolved ownership boundaries
- undefined promotion/rollback criteria
- unresolved requirement conflicts

If blocked:
- write a blocking artifact in `plans/`
- include `NO_BEAD_CREATION_DUE_TO_AMBIGUITY`

## 10) Canonical Update Boundary

- Canonical updates must follow spec-defined promotion flow.
- Ingest/draft steps must not mutate canonical directories directly.
- Any emergency bypass requires explicit user authorization + audit note.

## 11) Quality Gates

Fail-closed policy:
- Do not declare completion while required checks fail unless user explicitly approves exception.

For behavior changes, include:
- happy path test
- edge case test
- error path test
- regression test

## 12) Destructive Action Policy

- No destructive commands without explicit user permission.
- If impact is uncertain, stop and ask.
- Record destructive action audit in handoff:
  - authorization text
  - exact command
  - affected scope
  - timestamp

## 13) Session Completion (Landing)

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

## 14) Handoff Minimum Schema

Every handoff should include:
- issue id(s) + state
- files changed
- tests/commands run + outcomes
- blockers + owner + next action
- policy exceptions (if any)

<!-- bv-agent-instructions-v1 -->

---

## Beads Workflow Integration

This project uses [beads_viewer](https://github.com/Dicklesworthstone/beads_viewer) for issue tracking. Issues are stored in `.beads/` and tracked in git.

### Essential Commands

```bash
# View issues (launches TUI - avoid in automated sessions)
bv

# CLI commands for agents (use these instead)
bd ready              # Show issues ready to work (no blockers)
bd list --status=open # All open issues
bd show <id>          # Full issue details with dependencies
bd create --title="..." --type=task --priority=2
bd update <id> --status=in_progress
bd close <id> --reason="Completed"
bd close <id1> <id2>  # Close multiple issues at once
bd sync               # Commit and push changes
```

### Workflow Pattern

1. **Start**: Run `bd ready` to find actionable work
2. **Claim**: Use `bd update <id> --status=in_progress`
3. **Work**: Implement the task
4. **Complete**: Use `bd close <id>`
5. **Sync**: Always run `bd sync` at session end

### Key Concepts

- **Dependencies**: Issues can block other issues. `bd ready` shows only unblocked work.
- **Priority**: P0=critical, P1=high, P2=medium, P3=low, P4=backlog (use numbers, not words)
- **Types**: task, bug, feature, epic, question, docs
- **Blocking**: `bd dep add <issue> <depends-on>` to add dependencies

### Session Protocol

**Before ending any session, run this checklist:**

```bash
git status              # Check what changed
git add <files>         # Stage code changes
bd sync                 # Commit beads changes
git commit -m "..."     # Commit code
bd sync                 # Commit any new beads changes
git push                # Push to remote
```

### Best Practices

- Check `bd ready` at session start to find available work
- Update status as you work (in_progress → closed)
- Create new issues with `bd create` when you discover tasks
- Use descriptive titles and set appropriate priority/type
- Always `bd sync` before ending session

<!-- end-bv-agent-instructions -->
