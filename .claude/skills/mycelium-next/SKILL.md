---
name: mycelium-next
description: >
  Orchestrate the next agent in the mycelium workflow. Use when the user says
  "next agent", "continue workflow", "mycelium next", or to automatically
  invoke the appropriate agent based on a bead's current_agent label.
version: 1.0.0
author: mycelium
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Skill
---

# Mycelium Next - Agent Orchestrator

This skill reads a bead's `agent:*` label and invokes the appropriate mycelium agent skill.

## Agent Flow

```
scientist → implementer → verifier → maintainer → complete
```

- **scientist**: Creates plan, transitions to implementer
- **implementer**: Human implements (no skill), transitions to verifier
- **verifier**: Validates DoD, transitions to maintainer (or back to implementer)
- **maintainer**: Cleanup and commit, closes bead

## Instructions

1. **Identify the bead** - User provides bead ID, or use `bd ready` to find work
2. **Read the bead's labels** - Look for `agent:*` label
3. **Invoke the appropriate skill**:

| Label | Action |
|-------|--------|
| `agent:scientist` | Invoke `/mycelium-scientist` |
| `agent:implementer` | Inform user: "Implementer phase - you implement, then run `/mycelium-next`" |
| `agent:verifier` | Invoke `/mycelium-verifier` |
| `agent:maintainer` | Invoke `/mycelium-maintainer` |
| No agent label | Ask user which agent to start with |

## Reading Bead Labels

```python
import json

with open('.beads/issues.jsonl', 'r') as f:
    for line in f:
        if line.strip():
            issue = json.loads(line)
            if issue.get('id') == '<bead-id>':
                labels = issue.get('labels', [])
                agent_labels = [l for l in labels if l.startswith('agent:')]
                if agent_labels:
                    current_agent = agent_labels[0].replace('agent:', '')
                else:
                    current_agent = None
```

## Usage Examples

```bash
# Check what's next for a specific bead
/mycelium-next mycelium-abc

# Find ready work and continue
/mycelium-next
```

## Output

After determining the current agent:
1. State the bead ID and current agent
2. Either invoke the skill or inform the user of their action
3. On completion, the invoked skill handles transition to next agent
