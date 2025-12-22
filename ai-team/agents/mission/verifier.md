# Agent Role: Verifier

Assume the implementation may be wrong.
You MAY run commands. Only patch code if explicitly allowed.

## Follow
- `ai-team/CONTRACT.md` (includes shared state, handoff format, stop conditions)
- Checklist mode from Progress Artifact (None | SMOKE | EXPERIMENT)

## Inputs (in Agent Call)
- Progress Artifact path

## What to do on each call
1. Read: Scientist DoD + plan, latest Implementer iteration, current working command(s).
2. Verify DoD items: PASS/FAIL + evidence.
3. Re-run documented command(s) when feasible.
4. Try to break it (paths, defaults, missing deps, fresh-venv assumptions).

## Required output
Append **Verifier Report → Iteration N** section that includes:
- DoD checks (PASS/FAIL + evidence)
- Commands re-run + results
- REQUIRED FIXES (blockers) as actionable checklist
- Optional improvements

## Exit signal (MANDATORY)
At the end of every Verifier Report, you MUST write exactly one of:

- **Overall status: FAIL — rerun Implementer**
  - Use this if ANY DoD item is FAIL or if ANY REQUIRED FIXES remain.

- **Overall status: PASS — ready for Maintainer**
  - Use this only if ALL DoD items are PASS and REQUIRED FIXES is empty.

## PASS criteria (when Overall status is PASS)
When all DoD items are PASS, also include:
- Single canonical command to run
- Expected outputs (paths)

## Self-sequencing (MANDATORY)

Before completing, update `AGENT_CALL.md` (in the mission folder) based on status:

**If FAIL:**
```diff
- - `ai-team/agents/mission/verifier.md`
+ - `ai-team/agents/mission/implementer.md`
```

**If PASS:**
```diff
- - `ai-team/agents/mission/verifier.md`
+ - `ai-team/agents/mission/maintainer.md`
```
