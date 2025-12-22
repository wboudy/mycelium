# Sandbox

This directory is for **toy runs** — experimental missions to test and iterate on the `ai-team` workflow.

## Convention

Use the `toy-` prefix for any experimental run:

```
sandbox/
├── toy-yaml-migration/
├── toy-test-workflow/
├── toy-langgraph-spike/
└── README.md          # This file (tracked)
```

All `toy-*` directories are **gitignored** and will not be committed.

## How to Use

1. Create: `mkdir sandbox/toy-<name>`
2. Run agents from repo root, pointing to toy run for artifacts
3. The `ai-team/` folder stays in place — toy runs hold only outputs
4. Delete or keep for local reference

---

## Toy Run Ideas (Progressive)

Each toy run includes the exact prompt to give Mission Organizer.

---

### Phase 1: Foundation

#### `toy-simple-script`
**Goal:** Verify basic Scientist → Implementer → Verifier flow completes.

```
Please follow ai-team/agents/standalone/mission_organizer.md with these instructions:

Create a Python script at sandbox/toy-simple-script/hello.py that:
- Takes a name as a CLI argument
- Prints "Hello, {name}!"
- Returns exit code 0 on success

Scope: Only modify files in sandbox/toy-simple-script/
```

#### `toy-failing-verifier`
**Goal:** Test that Verifier catches a bug and loops back to Implementer.

```
Please follow ai-team/agents/standalone/mission_organizer.md with these instructions:

Create a Python script at sandbox/toy-failing-verifier/divide.py that:
- Takes two numbers as CLI arguments
- Prints their quotient
- Handles division by zero gracefully

Constraint: Scientist should intentionally omit the division-by-zero requirement 
from the plan, so Verifier catches it.

Scope: Only modify files in sandbox/toy-failing-verifier/
```

#### `toy-stop-condition`
**Goal:** Test that agents stop and ask user when requirements are ambiguous.

```
Please follow ai-team/agents/standalone/mission_organizer.md with these instructions:

Build a "data processor" in sandbox/toy-stop-condition/.

(Intentionally vague — Scientist should ask: What data? What format? What processing?)

Scope: Only modify files in sandbox/toy-stop-condition/
```

---

### Phase 2: Testing Integration

#### `toy-pytest-flow`
**Goal:** Implementer writes tests, Verifier runs them.

```
Please follow ai-team/agents/standalone/mission_organizer.md with these instructions:

Create a utility module at sandbox/toy-pytest-flow/utils.py with:
- add(a, b) → returns sum
- multiply(a, b) → returns product

Requirements:
- Include pytest tests in sandbox/toy-pytest-flow/test_utils.py
- Verifier must run pytest and report results
- DoD: All tests pass

Scope: Only modify files in sandbox/toy-pytest-flow/
```

#### `toy-test-failure`
**Goal:** Verifier catches a failing test, triggers Implementer loop.

```
Please follow ai-team/agents/standalone/mission_organizer.md with these instructions:

Create sandbox/toy-test-failure/calculator.py with:
- subtract(a, b) → returns difference

Constraint: Implementer should write the test but introduce an off-by-one bug.
Verifier should catch it via pytest and loop back.

Scope: Only modify files in sandbox/toy-test-failure/
```

---

### Phase 3: YAML Artifacts

#### `toy-yaml-progress`
**Goal:** Test using YAML for progress artifacts instead of markdown.

```
Please follow ai-team/agents/standalone/mission_organizer.md with these instructions:

Create a simple config loader at sandbox/toy-yaml-progress/config.py that:
- Reads a YAML config file
- Returns a dictionary

Meta-goal: Use a YAML-based progress artifact for this mission 
(test the new format).

Scope: Only modify files in sandbox/toy-yaml-progress/
```

---

### Phase 4+: Advanced (prompts TBD as workflow evolves)

- `toy-auto-sequence` — Agent-to-agent handoff without manual paste
- `toy-langgraph-basic` — Model flow as LangGraph
- `toy-mcp-resource` — Expose mission as MCP resource
- `toy-token-tracking` — Track tokens per agent call
