# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mycelium is a multi-agent workflow framework for AI-assisted development emphasizing human oversight and auditability. Key principles:
- **Human-gated handoffs (HITL)**: All agent transitions require explicit user approval
- **Filesystem as state**: Progress stored in version-controlled `progress.yaml` files
- **Plan before code**: Scientist creates plan before Implementer codes
- **Separation of concerns**: Each agent has specific capabilities and constraints

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

# Python CLI
mycelium-py run <mission-path>                # run current agent
mycelium-py run <mission-path> --approve      # skip HITL gate
mycelium-py run <mission-path> --dry-run      # build prompt only
mycelium-py status <mission-path> --verbose   # show LLM usage breakdown
mycelium-py auto <mission-path> --approve     # auto-loop until complete

# Bash CLI (prompt generation)
.mycelium/bin/mycelium next [mission-path]    # generate prompt, copy to clipboard
.mycelium/bin/mycelium list                   # list all missions
.mycelium/bin/mycelium status <mission-path>

# MCP server
python -m mycelium.mcp
```

## Architecture

### Agent Flow

Mission agents execute in sequence: **Scientist** → **Implementer** → **Verifier** → **Maintainer**

| Agent | Role | Code Access |
|-------|------|-------------|
| Scientist | Creates falsifiable plan from mission context | Read-only |
| Implementer | Executes plan, writes code/tests | Read/write |
| Verifier | Validates Definition of Done | Run tests only |
| Maintainer | Cleanup, commit message | Refactor only |

Standalone: **Mission Organizer** (natural language → mission setup), **Repo Maintainer** (repo-wide cleanup)

### Mission State

Single source of truth: `.mycelium/missions/<mission-id>/progress.yaml`
- `current_agent`: Which agent runs next (empty = complete)
- `mission_context`: Objective, scope, constraints, `test_mode` (NONE/SMOKE/FULL)
- `scientist_plan`: Definition of Done, plan steps, risks
- `implementer_log`: Array of iteration records
- `verifier_report`: DoD check results
- `llm_usage`: Token counts and costs per run

### MCP Tools

7 tools: `read_progress`, `update_progress`, `list_files`, `read_file`, `write_file`, `run_command`, `search_codebase`

Write and command execution require HITL approval (bypass via `MYCELIUM_HITL_AUTO_APPROVE=1`).

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Required for Claude models | - |
| `MYCELIUM_MODEL` | LLM model override | `anthropic/claude-sonnet-4-20250514` |
| `MYCELIUM_AUTO_APPROVE` | Skip HITL gate (1/true/yes) | disabled |

## Key Files

- `.mycelium/CONTRACT.md`: Global rules, constraints, LLM retry logic (3 retries, exponential backoff)
- `.mycelium/WORKFLOW.md`: 6-step mission lifecycle documentation
- `.mycelium/agents/mission/*.md`: Agent prompt templates (scientist, implementer, verifier, maintainer)
- `.mycelium/missions/PROGRESS_TEMPLATE.yaml`: Schema for progress.yaml artifacts
