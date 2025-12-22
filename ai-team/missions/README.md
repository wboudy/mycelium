# Missions Directory

This directory contains **per-mission** folders for the multi-agent workflow.

## Convention

Each mission lives in its own subfolder:
```
ai-team/missions/<mission-id>/
├── progress.yaml   # Progress Artifact (mission context + implementation log)
├── AGENT_CALL.md   # Current agent invocation for this mission
```

## Mission ID

Use a descriptive kebab-case name, e.g.:
- `api-refactor`
- `auth-integration`
- `data-pipeline`

## Lifecycle

1. **Use Mission Organizer** (recommended): Automatically sets up folder with `progress.yaml` and `AGENT_CALL.md`
2. Or manually:
   - Create folder: `ai-team/missions/<mission-id>/`
   - Copy `PROGRESS_TEMPLATE.yaml` → `<mission-id>/progress.yaml`
   - Copy `AGENT_CALL_TEMPLATE.md` → `<mission-id>/AGENT_CALL.md`
3. Agents self-sequence by updating `AGENT_CALL.md` to the next agent
4. Mission completes when Maintainer signs off
