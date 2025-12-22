# Multi-Agent Development Workflow

This repo uses a 4-agent workflow coordinated through the `ai-team/` directory.

## Agents

### Mission Agents (`ai-team/agents/mission/`)
| Agent | Role | May edit code? |
|-------|------|----------------|
| Scientist | Translates mission → plan | No |
| Implementer | Executes plan, writes code | Yes |
| Verifier | Validates DoD, finds bugs | Run only |
| Maintainer | Cleanup, commit message | Refactor only |

### Standalone Agents (`ai-team/agents/standalone/`)
| Agent | Role | May edit code? |
|-------|------|----------------|
| Mission Organizer | Parses instructions → sets up mission | No |
| Repo Maintainer | Repo-wide cleanup, identifies stale files | No |

---

## Quick Start (Mission Organizer)

The fastest way to start a new mission:

```
Please follow ai-team/agents/standalone/mission_organizer.md with these instructions:
<your natural language instructions here>
```

The Mission Organizer will:
1. Parse your instructions into Mission Context format
2. Create `ai-team/missions/<mission-id>/` folder
3. Set up `progress.md` with Mission Context filled
4. Initialize `AGENT_CALL.md` with scientist ready

Then start the mission:
```
Please follow ai-team/missions/<mission-id>/AGENT_CALL.md
```

---

## System Files

### Stable files (rarely change)
- `ai-team/CONTRACT.md` — global rules, decisions, stop conditions, scale guidelines
- `ai-team/agents/mission/*.md` — mission agent role definitions
- `ai-team/agents/standalone/*.md` — standalone agent role definitions
- `ai-team/missions/AGENT_CALL_TEMPLATE.md` — agent invocation template
- `ai-team/missions/PROGRESS_TEMPLATE.md` — progress artifact structure
- `ai-team/WORKFLOW.md` — this file

### Per-mission files
```
ai-team/missions/<mission-id>/
├── progress.md     # Progress Artifact
├── AGENT_CALL.md   # Current agent call
```

---

## Mission Lifecycle

### 1. Create mission (Mission Organizer)
Use the Mission Organizer to set up a new mission from natural language:
```
Please follow ai-team/agents/standalone/mission_organizer.md with these instructions:
<your instructions here>
```
The Mission Organizer creates the folder, `progress.md`, and `AGENT_CALL.md` automatically.

### 2. Call Scientist
- Paste `ai-team/missions/<mission-id>/AGENT_CALL.md` into agent dashboard
- Scientist fills: DoD, Plan, Checklist mode
- Scientist updates `AGENT_CALL.md` → implementer (automatic)
- **Note:** Scientist may ask for decisions if scope is unclear — make the call and let them continue

### 3. Call Implementer
- Paste `AGENT_CALL.md` into agent dashboard
- Implementer executes plan, logs iteration
- Implementer updates `AGENT_CALL.md` → verifier (automatic)

### 4. Call Verifier
- Paste `AGENT_CALL.md` into agent dashboard
- Verifier checks DoD, reports PASS/FAIL
- If FAIL: updates `AGENT_CALL.md` → implementer (automatic)
- If PASS: updates `AGENT_CALL.md` → maintainer (automatic)

### 5. Iterate until PASS
- Keep pasting `AGENT_CALL.md` — sequencing is automatic
- **Human intervention:** If any agent hits a stop condition (ambiguous requirements, design decision needed, unclear failure), they will ask you. Make the decision, then re-paste `AGENT_CALL.md` to continue.

### 6. Maintainer
- Adds cleanup notes and **Maintainer Summary** to `progress.md`
- Generates commit message at the end
- Mission is complete after Maintainer finishes

---

## Agent Self-Sequencing

Each agent updates `AGENT_CALL.md` before completing:

| Current Agent | On Success | On Failure |
|---------------|------------|------------|
| Scientist | → Implementer | STOP (ask user) |
| Implementer | → Verifier | → Verifier |
| Verifier (PASS) | → Maintainer | — |
| Verifier (FAIL) | — | → Implementer |
| Maintainer | Done | STOP (ask user) |

**How to update**: Replace the agent line in `AGENT_CALL.md`:
```diff
- - `ai-team/agents/mission/scientist.md`
+ - `ai-team/agents/mission/implementer.md`
```

---

## Repo Maintainer (repo-wide)

A separate `repo_maintainer` agent operates **outside** individual missions:
- Reviews all completed missions, READMEs, and workflows
- Identifies unnecessary files safe to delete
- Reports findings in chat 

See `ai-team/agents/standalone/repo_maintainer.md` for details.

---

## Multiple Concurrent Missions

You can run multiple missions in parallel:
- Each mission has its own folder in `ai-team/missions/`
- Each has its own `AGENT_CALL.md`
- Paste different mission's AGENT_CALL into separate agent tabs

---

## Invariant

If something "works," the Progress Artifact must contain:
- One canonical command to run
- Expected outputs / paths
- Verifier confirmation (PASS)
