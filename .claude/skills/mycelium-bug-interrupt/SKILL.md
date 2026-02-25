---
name: mycelium-bug-interrupt
description: >
  Interrupt active implementation when an unexpected blocker bug appears.
  Use when work exposes a bug that should be split from the current bead,
  when the user says "spin out a bug bead", "interrupt and debug",
  "park this and investigate", or "unexpected issue". Creates a linked bug
  bead, blocks the original bead, captures reproduction context, and defines
  the resume path back to original work.
version: 1.0.0
author: mycelium
allowed-tools:
  - Read
  - Bash
  - Grep
---

# Mycelium Bug Interrupt

Interrupt implementation work when an unexpected blocker appears. Do not do a
drive-by fix inside the original bead.

## Inputs

- `origin_id`: bead currently being implemented
- `bug_title`: short bug summary
- `bug_description`: expected vs actual, reproduction hints, first evidence
- Optional: `priority` (default `1` for blocker bugs)

## Interrupt Workflow

1. Validate origin context
   - Run `bd show <origin_id>`
   - Confirm this bug blocks completion of the origin bead
2. Create dedicated bug bead

```bash
bug_id="$(bd create "<bug_title>" \
  --type bug \
  --priority "${priority:-1}" \
  --description "<bug_description>" \
  --labels "interrupt,root-cause,model:deep" \
  --silent)"
```

3. Link bug as blocker of origin and freeze origin work

```bash
bd dep "$bug_id" --blocks "<origin_id>"
bd update "<origin_id>" --status blocked \
  --notes "Interrupted by blocker bug $bug_id. Resume only after bug is closed."
```

4. Switch active execution to the bug bead

```bash
bd update "$bug_id" --status in_progress \
  --notes "Spawned from <origin_id>. Start with root-cause analysis before patching."
```

5. Deliberate analysis pass before code changes
   - Reproduce failure once
   - Capture probable causes (2-3 hypotheses)
   - Choose one smallest falsifiable check
   - Only then patch

## Resume Workflow

After the bug is fixed:

```bash
bd close "$bug_id" --reason "Fixed blocker and verified behavior"
bd dep remove "<origin_id>" "$bug_id"
bd update "<origin_id>" --status in_progress \
  --notes "Resumed after blocker bug $bug_id closed."
```

Return to the origin bead and continue implementation.

## Output Format

Always report:

1. `origin_id`
2. `bug_id`
3. Dependency created (`bug_id` blocks `origin_id`)
4. Active bead now in progress
5. Explicit resume command block

## Model Routing Notes

- Do not claim model switching inside the same turn; this skill cannot change
  the running model mid-response.
- Use label `model:deep` on the spawned bug bead to request higher-reasoning
  routing on the next turn in orchestrators that support model-by-label.
