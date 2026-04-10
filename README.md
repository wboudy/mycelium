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



---

## Core Principles

1. **Plan before code** — Scientist creates a falsifiable plan; Implementer only executes it
2. **Separation of concerns** — Scientist can't touch code, Verifier can't write code
3. **Filesystem as state** — All logic lives in markdown files in your repo, not hidden databases
4. **Human-gated handoffs** — You approve each agent transition (for now)

## Model Routing

Mycelium supports deterministic model routing for bug-interrupt handoffs:

- If the mission progress includes `model:deep`, the orchestrator routes to a higher-reasoning model.
- Default deep-route model: `openai/gpt-5`.

Routing precedence (highest to lowest):

1. Explicit CLI/API override (for example `mycelium-py run --model ...`)
2. `model:deep` route (`MYCELIUM_MODEL_DEEP`, then `MYCELIUM_DEEP_MODEL`, then `openai/gpt-5`)
3. Standard route (`MYCELIUM_MODEL`, else `anthropic/claude-sonnet-4-20250514`)

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

1. Copy `.mycelium/` into your project root
2. Customize `.mycelium/CONTRACT.md` for your project
3. Start a mission:
   ```
   Please follow .mycelium/agents/standalone/mission_organizer.md with these instructions:
   <your instructions>
   ```

See [`.mycelium/WORKFLOW.md`](.mycelium/WORKFLOW.md) for detailed usage.

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for detailed development phases:
- 🟢 **Phase 1: Hardening** — YAML artifacts, automated handoffs, observability
- 🟡 **Phase 2: Automation** — Agent-to-agent calls, LangGraph, MCP support
- 🔴 **Phase 3: Intelligence** — Multi-model orchestration, learning, IDE integration

## Directory Structure

```
mycelium/
├── .mycelium/                # Self-contained agent system (copy this to your projects)
│   ├── CONTRACT.md         # Global rules and constraints
│   ├── WORKFLOW.md         # Detailed workflow documentation
│   ├── bin/                # CLI tools (e.g. mycelium)
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
