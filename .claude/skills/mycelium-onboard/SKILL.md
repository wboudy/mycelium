---
name: mycelium-onboard
description: >
  Summarize current project status and ready work. Use when starting a session,
  checking what work is available, or when the user asks "what should I work on?",
  "show me the current status", "what's ready?", or "onboard me".
version: 1.0.0
author: mycelium
allowed-tools:
  - Bash(bd:*)
  - Bash(/Users/williamboudy/.local/bin/bd:*)
  - Read
---

# Mycelium Onboard

Get oriented with the current project state and discover ready work.

## Instructions

When this skill is invoked:

1. **Run onboarding check**:
   ```bash
   /Users/williamboudy/.local/bin/bd onboard
   ```
   This shows setup status and any recommended configuration.

2. **Show ready work**:
   ```bash
   /Users/williamboudy/.local/bin/bd ready
   ```
   This lists issues with no blockers that are available to work on.

3. **Summarize findings**:
   - Report any setup recommendations from onboard
   - List the ready work items with their priorities
   - If there are in_progress items assigned to you, highlight those first
   - Suggest which issue to tackle based on priority and dependencies

## Output Format

Present the results clearly:

```
## Project Status

[Any setup recommendations or notes from bd onboard]

## Ready Work

[List from bd ready, formatted as a table or bullet list]

## Recommendation

[Suggest which issue to pick up, if any are in_progress assigned to claude, mention those first]
```
