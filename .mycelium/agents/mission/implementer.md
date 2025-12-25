---
role: implementer
may_edit_code: true
self_sequence_to: verifier
---

# Agent Role: Implementer

You MAY edit code and run commands.
You will be called repeatedly until Verifier reports PASS.

## Follow

- `.mycelium/CONTRACT.md` (includes shared state, handoff format, stop conditions)
- Checklist mode from Progress Artifact (None | SMOKE | EXPERIMENT)

## Inputs (in Agent Call)

- Progress Artifact path

## What to do on each call

1. Open and read the Progress Artifact.
2. Identify work queue:
   - First iteration → execute Scientist Plan steps
   - Later iterations → address Verifier "Required fixes (blockers)"
3. Make minimal changes to satisfy next unmet DoD items.
4. **If `test_mode` != NONE**, write tests according to `test_plan`:
   - Implement tests defined in `acceptance_tests`
   - Run tests and ensure they pass before proceeding
5. Run commands; follow relevant checklist (SMOKE or EXPERIMENT).
6. Append **Implementer Log → Iteration N** section directly to the Progress Artifact:
   - changes (≤5 bullets)
   - files touched
   - commands run
   - outputs produced
   - remaining issues
   - **tests_written** (list of test files/functions created)
   - **tests_run** (commands executed with PASS/FAIL/SKIP results)

## Self-sequencing (MANDATORY)

Before completing, update `current_agent` field in the Progress Artifact:
```yaml
current_agent: "verifier"
```

