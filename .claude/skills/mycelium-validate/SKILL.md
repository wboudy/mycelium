---
name: mycelium-validate
description: >
  Validate progress.yaml before role transitions. Use when checking if a mission
  is ready for the next agent, when the user says "validate progress", "check yaml",
  or before any agent transition in the mycelium workflow.
version: 1.0.0
author: mycelium
allowed-tools:
  - Read
  - Glob
---

# Mycelium Validate Skill

Validates progress.yaml against required schema rules before role transitions.

## Purpose

Ensure critical fields are present before transitioning between agents:
- Before Implementer: `definition_of_done` must exist and have items
- Before Verifier: `commands_run` must exist in implementer_log
- Before Maintainer: verifier_report must have `overall_status: PASS`

## Instructions

1. **Locate the progress.yaml file**
   - User provides path, OR
   - Search in `.mycelium/missions/*/progress.yaml`

2. **Read and parse the YAML**

3. **Validate based on current_agent transition target:**

### Transition to Implementer (from Scientist)
Required fields:
- `scientist_plan.definition_of_done` - must be array with at least one item
- `scientist_plan.plan_steps` - must be array with at least one step
- Each DoD item must have `description` field

### Transition to Verifier (from Implementer)
Required fields:
- All Scientist requirements, PLUS:
- `implementer_log` - must have at least one iteration
- Latest iteration must have `commands_run` with at least one command
- Each command must have `command` and `result` fields

### Transition to Maintainer (from Verifier)
Required fields:
- All previous requirements, PLUS:
- `verifier_report` - must have at least one iteration
- Latest iteration must have `overall_status` containing "PASS"

## Output Format

```
## Validation Report

**File:** <path to progress.yaml>
**Current Agent:** <current_agent value>
**Transition To:** <next agent>

### Required Fields Check

| Field | Status | Details |
|-------|--------|---------|
| definition_of_done | PASS/FAIL | count or error |
| plan_steps | PASS/FAIL | count or error |
| commands_run | PASS/FAIL | count or error |
| overall_status | PASS/FAIL | value or error |

### Result

**VALID** - Ready to transition to <next_agent>

OR

**INVALID** - Missing required fields:
- <list of missing/invalid fields>
```

## Validation Rules Summary

| Transition | Required Fields |
|------------|-----------------|
| scientist → implementer | definition_of_done, plan_steps |
| implementer → verifier | commands_run in latest iteration |
| verifier → maintainer | overall_status contains "PASS" |
| maintainer → complete | behavior_unchanged = true |
