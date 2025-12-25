# Agent Contract (Always Applies)

## Decisions

Project-wide decisions (treat as fixed unless explicitly changed):

- Treat reproducibility as "one command that works" before formal experiments.

> **Pending decisions** (to discuss with collaborators):
> - Key architecture decisions?
> - Dependencies and frameworks?
> - Experiment tracking strategy?

## Project Type

General-purpose agentic workflow repository.

Phases: [Define your project phases here]

## Non-negotiables

- Prefer clarity over cleverness.
- Keep changes minimal and localized.
- No secrets, no large datasets or model weights committed.
- No new heavy dependencies without explicit approval.
- If you claim "it works," provide one exact command that reproduces it.

## Shared State

- **Agents do NOT rely on chat memory.**
- The Progress Artifact is the single source of truth:
  - Location: `.mycelium/missions/<mission-id>/progress.yaml`
- Read it first on every call.
- See `.mycelium/WORKFLOW.md` for multi-mission workflow.

## Handoff Format (all agents)

1. What changed (≤5 bullets)
2. Files touched
3. Command(s) run (exact)
4. Outputs produced
5. Issues / next steps

## Scale Guidelines

- Default to smoke-test scale for early development (define project-specific limits).
- Commands must run from repo root.
- Make side effects explicit (files written, logs).
- For formal experiments: define metrics upfront, save configs, track seeds.

## Python Environment

- This repo uses a project-local virtual environment at `.venv/`.
- All Python commands should assume `.venv` is activated.
- Do not install packages globally.
- If new Python dependencies are required:
  - add them to `requirements.txt`
  - note the change in the Progress Artifact

## Testing

Testing is integrated into the agent workflow. The `test_mode` field in `mission_context` determines requirements:

| Mode | When to Use | Requirements |
|------|-------------|--------------|
| **NONE** | Exploratory, throwaway, or documentation-only missions | No tests required |
| **SMOKE** | Features that should work reliably; default for most feature work | Basic sanity tests that verify core functionality |
| **FULL** | Production-ready, persistent code; critical infrastructure | Comprehensive tests with edge cases and error handling |

**Guidelines:**
- Default is `NONE` — the Scientist explicitly upgrades based on mission persistence
- Tests complement DoD verification; they don't replace it
- Specify WHAT to test, not HOW (framework choice is project-specific)
- Verifier runs all tests; any failure = mission FAIL (for SMOKE/FULL modes)



## Stop Conditions (all agents)

Stop and ask the user if:
- Requirements are ambiguous
- A design or scope decision is needed
- Failures are unclear
- Compute or training scope expands significantly

