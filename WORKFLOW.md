# Mycelium Workflow

This document explains the Claude Code + Beads integration workflow for AI-assisted development.

## Overview

Mycelium uses a multi-agent workflow where each agent has specific responsibilities:

```
Scientist → Implementer → Verifier → Maintainer → Complete
```

State is tracked via **beads** (git-backed issue tracker) with `agent:*` labels.

## Agent Roles

### Scientist (`agent:scientist`)
- **Responsibility**: Create a plan from the bead's mission context
- **Outputs**: Definition of Done (DoD), plan steps, risks
- **Code Access**: Read-only
- **Transitions to**: Implementer

### Implementer (`agent:implementer`)
- **Responsibility**: Execute the plan, write code and tests
- **Inputs**: Scientist's plan from bead notes
- **Code Access**: Read/write
- **Transitions to**: Verifier
- **Note**: Human implements; no skill for this phase

### Verifier (`agent:verifier`)
- **Responsibility**: Validate implementation against DoD
- **Approach**: Skeptical - assume implementation may be wrong
- **Code Access**: Run tests, read code
- **Transitions to**: Maintainer (PASS) or Implementer (FAIL)

### Maintainer (`agent:maintainer`)
- **Responsibility**: Cleanup, refactor, prepare commit
- **Constraint**: Do NOT change behavior
- **Code Access**: Refactor only
- **Transitions to**: Complete (closes bead)

## Workflow Commands

### Starting Work

```bash
# See what's ready to work on
bd ready

# Check a bead's current state
bd show <bead-id>

# Start scientist planning
/mycelium-scientist
```

### During Implementation

```bash
# After implementing, run verification
/mycelium-verifier

# If PASS, run maintainer
/mycelium-maintainer
```

### Orchestration

```bash
# Automatically invoke the next agent based on bead label
/mycelium-next

# Check project status
/mycelium-onboard
```

## Bead Labels

Agent state is tracked via labels:

| Label | Meaning |
|-------|---------|
| `agent:scientist` | Ready for planning |
| `agent:implementer` | Ready for implementation |
| `agent:verifier` | Ready for verification |
| `agent:maintainer` | Ready for cleanup |
| (no agent label) | Work complete or needs assignment |

## State Storage

All state lives in `.beads/issues.jsonl`:

```json
{
  "id": "mycelium-abc",
  "title": "Add feature X",
  "description": "Mission context...",
  "labels": ["agent:scientist"],
  "notes": "## Scientist Plan\n..."
}
```

- **description**: Mission context (what to build)
- **labels**: Current agent state
- **notes**: Plan, verifier reports, maintainer notes

## Example Workflow

1. **Create bead** with mission context
   ```bash
   bd create "Add dark mode toggle" --type feature
   bd label mycelium-abc agent:scientist
   ```

2. **Scientist** creates plan
   ```
   /mycelium-scientist
   ```
   - Reads bead description
   - Creates DoD and plan steps in notes
   - Transitions to `agent:implementer`

3. **Human implements** the plan
   - Write code following the plan
   - When done, manually transition: `bd label mycelium-abc agent:verifier`

4. **Verifier** checks DoD
   ```
   /mycelium-verifier
   ```
   - Runs tests, validates each DoD item
   - PASS → transitions to `agent:maintainer`
   - FAIL → back to `agent:implementer` with fixes list

5. **Maintainer** finalizes
   ```
   /mycelium-maintainer
   ```
   - Cleanup, generate commit message
   - Closes bead

## Human-in-the-Loop

All agent transitions happen explicitly:
- Skills update the bead label to signal the next phase
- User reviews and approves before continuing
- Use `/mycelium-next` to continue workflow automatically
