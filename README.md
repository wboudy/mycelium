# Mycelium

A **human-gated** multi-agent workflow for AI-assisted development. Unlike fully autonomous tools, Mycelium enforces separation of concerns and keeps all agent logic in auditable files.

## Why Mycelium?

| Feature | Autonomous Tools (Cline, Cursor) | Mycelium |
|---------|----------------------------------|----------|
| **State** | Hidden in IDE cache/chat logs | Visible in `missions/progress.md` |
| **Planning** | Optional or implicit | Required (Scientist plans before Implementer codes) |
| **Verification** | Agent grades its own work | Separate Verifier agent |
| **Auditability** | Difficult to review | Every step in version-controlled markdown |
| **Control** | Fully automatic | Human-gated at each handoff |

### When to use Mycelium

- **High-stakes projects** where you need to review every step before commit
- **Team environments** where others need to "review the tape" of what the agent did
- **Research workflows** where reproducibility matters more than speed
- **Regulated codebases** where you need audit trails

### When to use Cline/Cursor instead

- Fast, interactive prototyping
- Solo work where speed > auditability
- Simple, low-risk changes

---

## Core Principles

1. **Plan before code** — Scientist creates a falsifiable plan; Implementer only executes it
2. **Separation of concerns** — Scientist can't touch code, Verifier can't write code
3. **Filesystem as state** — All logic lives in markdown files in your repo, not hidden databases
4. **Human-gated handoffs** — You approve each agent transition (for now)

---

## Agent Roles

| Agent | Role | May edit code? |
|-------|------|----------------|
| **Scientist** | Translates mission → plan | No |
| **Implementer** | Executes plan, writes code | Yes |
| **Verifier** | Validates DoD, finds bugs | Run only |
| **Maintainer** | Cleanup, commit message | Refactor only |

**Standalone Agents:**
- **Mission Organizer** — Parses natural language → sets up mission
- **Repo Maintainer** — Repo-wide cleanup, identifies stale files

---

## Quick Start

1. Copy `ai-team/` into your project root
2. Customize `ai-team/CONTRACT.md` for your project
3. Start a mission:
   ```
   Please follow ai-team/agents/standalone/mission_organizer.md with these instructions:
   <your instructions>
   ```

See [`ai-team/WORKFLOW.md`](ai-team/WORKFLOW.md) for detailed usage.

---

## Roadmap & Future Ideas

### Near-term
- [ ] **YAML-based artifacts** — Replace markdown with structured YAML for progress artifacts (easier parsing, validation)
- [ ] **Agent-to-agent calls** — Agents invoke next agent automatically, reducing manual copy-paste of `AGENT_CALL.md`
- [ ] **Context metrics** — Track token counts, file touches, and decision points per mission

### Medium-term
- [ ] **LangGraph integration** — Model agent flow as a graph for better orchestration and visualization
- [ ] **MCP (Model Context Protocol) support** — Expose missions/agents as MCP resources for tool-aware LLMs
- [ ] **Checkpointing** — Save/restore agent state for long-running missions

### Long-term
- [ ] **Multi-model orchestration** — Route tasks to different models based on complexity
- [ ] **Learning from missions** — Aggregate completed missions to improve future planning
- [ ] **IDE integration** — VS Code extension for mission management

---

## Directory Structure

```
mycelium/
├── ai-team/                # Self-contained agent system (copy this to your projects)
│   ├── CONTRACT.md         # Global rules and constraints
│   ├── WORKFLOW.md         # Detailed workflow documentation
│   ├── agents/
│   │   ├── mission/        # Scientist, Implementer, Verifier, Maintainer
│   │   └── standalone/     # Mission Organizer, Repo Maintainer
│   └── missions/           # Per-mission folders with progress artifacts
├── sandbox/                # Toy runs for testing workflow (see sandbox/README.md)
├── src/mycelium/           # Python package (for future tooling)
├── tests/
├── .gitignore
├── pyproject.toml
├── requirements.txt
└── README.md               # This file
```

## License

MIT
