# Missions Directory

This directory contains **per-mission** folders for the multi-agent workflow.

## Convention

Each mission lives in its own subfolder:
```
ai-team/missions/<mission-id>/
├── progress.md     # Progress Artifact (mission context + implementation log)
├── AGENT_CALL.md   # Current agent invocation for this mission
```

## Mission ID

Use a descriptive kebab-case name, e.g.:
- `api-refactor`
- `auth-integration`
- `data-pipeline`

## Lifecycle

1. **Create** a new folder: `ai-team/missions/<mission-id>/`
2. **Copy** `PROGRESS_TEMPLATE.md` → `<mission-id>/progress.md`
3. **Copy** `AGENT_CALL_TEMPLATE.md` → `<mission-id>/AGENT_CALL.md`
4. Agents self-sequence by updating `AGENT_CALL.md` to the next agent
5. Mission completes when Maintainer signs off
