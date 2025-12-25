# Multi-Agent Development Workflow

This repo uses a 4-agent workflow coordinated through the `.mycelium/` directory.

## Agents

### Mission Agents (`.mycelium/agents/mission/`)
| Agent | Role | May edit code? |
|-------|------|----------------|
| Scientist | Translates mission → plan | No |
| Implementer | Executes plan, writes code | Yes |
| Verifier | Validates DoD, finds bugs | Run only |
| Maintainer | Cleanup, commit message | Refactor only |

### Standalone Agents (`.mycelium/agents/standalone/`)
| Agent | Role | May edit code? |
|-------|------|----------------|
| Mission Organizer | Parses instructions → sets up mission | No |
| Repo Maintainer | Repo-wide cleanup, identifies stale files | No |

---

## Quick Start (Mission Organizer)

The fastest way to start a new mission:

```
Please follow .mycelium/agents/standalone/mission_organizer.md with these instructions:
<your natural language instructions here>
```

The Mission Organizer will:
1. Parse your instructions into Mission Context format
2. Create `.mycelium/missions/<mission-id>/` folder
3. Set up `progress.yaml` with Mission Context filled and `current_agent: scientist`

Then start the mission using the CLI:
```bash
.mycelium/bin/mycelium next .mycelium/missions/<mission-id>
```

This generates the agent prompt and copies it to your clipboard.

---

## System Files

### Stable files (rarely change)
- `.mycelium/CONTRACT.md` — global rules, decisions, stop conditions, scale guidelines
- `.mycelium/agents/mission/*.md` — mission agent role definitions
- `.mycelium/agents/standalone/*.md` — standalone agent role definitions
- `.mycelium/missions/PROGRESS_TEMPLATE.yaml` — progress artifact structure
- `.mycelium/WORKFLOW.md` — this file
- `.mycelium/bin/mycelium` — CLI for agent prompt generation

### Per-mission files
```
.mycelium/missions/<mission-id>/
└── progress.yaml   # Progress Artifact (YAML format, includes current_agent)
```

---

## Mission Lifecycle

### 1. Create mission (Mission Organizer)
Use the Mission Organizer to set up a new mission from natural language:
```
Please follow .mycelium/agents/standalone/mission_organizer.md with these instructions:
<your instructions here>
```
The Mission Organizer creates the folder and `progress.yaml` with `current_agent: scientist`.

### 2. Call Scientist
```bash
.mycelium/bin/mycelium next .mycelium/missions/<mission-id>
```
- Paste the generated prompt into agent dashboard
- Scientist fills: DoD, Plan, Checklist mode
- Scientist updates `current_agent` → implementer (automatic)
- **Note:** Scientist may ask for decisions if scope is unclear — make the call and let them continue

### 3. Call Implementer
```bash
.mycelium/bin/mycelium next .mycelium/missions/<mission-id>
```
- Paste the generated prompt into agent dashboard
- Implementer executes plan, logs iteration
- Implementer updates `current_agent` → verifier (automatic)

### 4. Call Verifier
```bash
.mycelium/bin/mycelium next .mycelium/missions/<mission-id>
```
- Paste the generated prompt into agent dashboard
- Verifier checks DoD, reports PASS/FAIL
- If FAIL: updates `current_agent` → implementer (automatic)
- If PASS: updates `current_agent` → maintainer (automatic)

### 5. Iterate until PASS
- Keep running `.mycelium/bin/mycelium next` — sequencing is automatic via `current_agent` field
- **Human intervention:** If any agent hits a stop condition (ambiguous requirements, design decision needed, unclear failure), they will ask you. Make the decision, then re-run the CLI to continue.

### 6. Maintainer
- Adds cleanup notes and **Maintainer Summary** to `progress.yaml`
- Generates commit message at the end
- Sets `current_agent` to empty string to signal mission completion
- Mission is complete after Maintainer finishes

---

## Agent Self-Sequencing

Each agent updates `current_agent` in progress.yaml before completing:

| Current Agent | On Success | On Failure |
|---------------|------------|------------|
| Scientist | → implementer | STOP (ask user) |
| Implementer | → verifier | → verifier |
| Verifier (PASS) | → maintainer | — |
| Verifier (FAIL) | — | → implementer |
| Maintainer | → "" (empty) | STOP (ask user) |

**How to update**: Change the `current_agent` field in progress.yaml:
```yaml
current_agent: "implementer"
```

---

## Repo Maintainer (repo-wide)

A separate `repo_maintainer` agent operates **outside** individual missions:
- Reviews all completed missions, READMEs, and workflows
- Identifies unnecessary files safe to delete
- Reports findings in chat 

See `.mycelium/agents/standalone/repo_maintainer.md` for details.

---

## Multiple Concurrent Missions

You can run multiple missions in parallel:
- Each mission has its own folder in `.mycelium/missions/`
- Each has its own `progress.yaml` with its own `current_agent`
- Run `.mycelium/bin/mycelium next` with different mission paths

---

## Migration from Markdown to YAML

As of this version, new missions use `progress.yaml` instead of `progress.md`.

**Existing missions** (created before this change):
- Can continue using `progress.md` — agents will work with either format
- No automated migration is required
- Manual migration: copy content to YAML structure if desired

**New missions**: Always use `progress.yaml` via the Mission Organizer.

---

## Invariant

If something "works," the Progress Artifact must contain:
- One canonical command to run
- Expected outputs / paths
- Verifier confirmation (PASS)

