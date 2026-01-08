# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mycelium is a multi-agent workflow framework for AI-assisted development emphasizing human oversight and auditability. Key principles:
- **Human-gated handoffs (HITL)**: All agent transitions require explicit user approval
- **Beads as state**: Progress tracked via beads issue tracker with `agent:*` labels
- **Plan before code**: Scientist creates plan before implementation
- **Separation of concerns**: Each agent has specific capabilities and constraints

## Non-negotiables

- Prefer clarity over cleverness
- Keep changes minimal and localized
- No secrets, no large datasets or model weights committed
- No new heavy dependencies without explicit approval
- If you claim "it works," provide one exact command that reproduces it

## Plan Before Code (Enforced)

**All new work requires planning before implementation.** Use `/plan` mode (or `EnterPlanMode`) before writing any code for:
- New feature implementations
- Architectural changes
- Multi-file modifications
- Any work that touches mission-critical paths

This ensures the Scientist → Implementer flow is respected even in ad-hoc Claude Code sessions.

## Stop Conditions

Stop and ask the user if:
- Requirements are ambiguous
- A design or scope decision is needed
- Failures are unclear or unexpected
- Compute or resource scope expands significantly

Do not proceed with assumptions. Clarify first.

## Commands

```bash
# Setup (Python 3.10+)
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/
pytest tests/test_orchestrator.py                      # single file
pytest tests/test_orchestrator.py::test_func_name -v   # single test

# Lint and format (line-length: 100)
ruff check src/
ruff format src/

# Issue tracking (beads)
bd ready                    # find unblocked work
bd show <bead-id>          # show bead details
bd create "Title"          # create new bead
bd close <bead-id>         # close completed bead
bd sync                    # sync with git remote
```

## Architecture

### Agent Flow

Agents execute in sequence: **Scientist** → **Implementer** → **Verifier** → **Maintainer**

| Agent | Role | Code Access |
|-------|------|-------------|
| Scientist | Creates falsifiable plan from bead context | Read-only |
| Implementer | Executes plan, writes code/tests | Read/write |
| Verifier | Validates Definition of Done | Run tests only |
| Maintainer | Cleanup, commit message | Refactor only |

Agent state is tracked via bead labels: `agent:scientist`, `agent:implementer`, `agent:verifier`, `agent:maintainer`

### Workflow Skills

- `/mycelium-scientist` - Create plan from bead context
- `/mycelium-verifier` - Verify implementation against DoD
- `/mycelium-maintainer` - Cleanup and finalize
- `/mycelium-next` - Orchestrate next agent based on bead label
- `/mycelium-onboard` - Show current project status

### Bead State

Single source of truth: `.beads/issues.jsonl`
- Bead `labels` array contains `agent:*` for current workflow state
- Bead `notes` field contains scientist plan and verifier reports
- Bead `description` contains mission context

## Python Environment

- This repo uses a project-local virtual environment at `.venv/`
- All Python commands should assume `.venv` is activated
- Do not install packages globally
- If new Python dependencies are required:
  - Add them to `requirements.txt` or `pyproject.toml`
  - Note the change in a bead comment

## Testing

Testing guidelines by scope:

| Scope | When to Use | Requirements |
|-------|-------------|--------------|
| **NONE** | Exploratory, throwaway, or documentation-only | No tests required |
| **SMOKE** | Features that should work reliably | Basic sanity tests |
| **FULL** | Production-ready, critical infrastructure | Comprehensive tests with edge cases |

**Guidelines:**
- Default is NONE — explicitly upgrade based on work persistence
- Tests complement DoD verification; they don't replace it
- Verifier runs all tests; any failure = FAIL

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Required for Claude models | - |

## Key Files

- `CLAUDE.md`: Project instructions (this file)
- `.beads/issues.jsonl`: Issue tracker data
- `.claude/skills/mycelium-*/SKILL.md`: Agent skill definitions
