# Missions Directory

This directory contains **per-mission** folders for the multi-agent workflow.

## Convention

Each mission lives in its own subfolder:
```
.mycelium/missions/<mission-id>/
└── progress.yaml   # Progress Artifact (mission context + current_agent + logs)
```

## Mission ID

Use a descriptive kebab-case name, e.g.:
- `api-refactor`
- `auth-integration`
- `data-pipeline`

## Lifecycle

1. **Use Mission Organizer** (recommended): Automatically sets up folder with `progress.yaml` and `current_agent: scientist`
2. Or manually:
   - Create folder: `.mycelium/missions/<mission-id>/`
   - Copy `PROGRESS_TEMPLATE.yaml` → `<mission-id>/progress.yaml`
   - Set `current_agent: "scientist"` in progress.yaml
3. Run `.mycelium/bin/mycelium next .mycelium/missions/<mission-id>` to get the agent prompt
4. Agents self-sequence by updating `current_agent` field to the next agent
5. Mission completes when Maintainer sets `current_agent` to empty string

