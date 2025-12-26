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

## Orchestration Rules

### LiteLLM Integration

All LLM calls go through LiteLLM for unified provider access. This enables BYOK (Bring Your Own Key) via environment variables:

| Provider  | Environment Variable  |
|-----------|----------------------|
| Anthropic | `ANTHROPIC_API_KEY`  |
| OpenAI    | `OPENAI_API_KEY`     |
| Google    | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |

Default model: `anthropic/claude-sonnet-4-20250514` (override via `MYCELIUM_MODEL` env var or `--model` flag)

### Retry Logic

Provider failures are handled with automatic retry:
- **Max retries**: 3
- **Backoff**: Exponential (1s → 2s → 4s)
- **Retryable errors**: Rate limits (429), timeouts, transient network failures
- **Non-retryable**: Authentication errors, bad requests, invalid prompts

### Human-in-the-Loop (HITL) Approval Gate

Before the **Implementer** agent can modify source code, explicit approval is required:

```bash
# Interactive prompt (default)
mycelium-py run .mycelium/missions/<mission>

# Auto-approve (bypass HITL)
mycelium-py run .mycelium/missions/<mission> --approve
```

This prevents unreviewed code changes and maintains human oversight.

### Usage Logging

Every LLM call logs usage metadata to `progress.yaml`:

```yaml
llm_usage:
  runs:
    - agent_role: implementer
      model: anthropic/claude-sonnet-4-20250514
      total_tokens: 4523
      cost_usd: 0.013569
      timestamp: 2024-12-26T14:30:00Z
  total_tokens: 4523
  total_cost_usd: 0.013569
```

View cumulative usage with:
```bash
mycelium-py status .mycelium/missions/<mission> --verbose
```

