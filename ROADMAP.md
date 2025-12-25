# Mycelium Roadmap

---

## 🟢 Phase 1: Hardening

**Focus:** Transition from text-heavy prompts to machine-verifiable artifacts.

### 1.1 YAML-Based Artifacts ✅ (Partial)

Replace markdown progress files with structured YAML.

| Markdown | YAML |
|----------|------|
| Freeform text | Schema-enforced fields |
| Human-readable | Machine-parseable |
| Easy to miss fields | Validation catches gaps |

**Why YAML?**
- **Schema validation** — Require `definition_of_done`, `dependencies`, `estimated_impact`
- **Fewer hallucinations** — LLMs produce more consistent output with nested YAML than freeform markdown
- **Diffable** — Cleaner git diffs for mission state changes

**Sub-tasks:**
- [x] Define YAML schema for `progress.yaml` — *Completed in progress-yaml-migration mission*
- [x] Create `PROGRESS_TEMPLATE.yaml` with self-documenting comments
- [x] Update all agent files to reference `.yaml` format
- [x] Migration guide from current markdown templates — *Added to WORKFLOW.md*
- [ ] Define YAML schema for `agent_call.yaml` (optional — current `.md` works)
- [ ] Create JSON Schema for automated validation (`progress.schema.json`)

---

### 1.2 `mycelium validate` CLI

A gatekeeper that rejects malformed missions before work begins.

**Validation rules:**
- Scientist must fill `definition_of_done` before Implementer starts
- Implementer must log `commands_run` before Verifier starts
- Verifier must include `pass_fail_status` before Maintainer starts

**Example:**
```bash
$ mycelium validate .mycelium/missions/my-mission/progress.yaml
❌ Missing required field: definition_of_done
   → Mission rejected. Scientist must complete DoD.
```

**Sub-tasks:**
- [ ] Implement `mycelium validate` CLI
- [ ] Add pre-handoff validation hook
- [ ] CI integration (block PR if validation fails)

---

### 1.3 Context Metrics & Auto-Compression

Track token usage to prevent context window saturation.

**Metrics tracked in `metrics.yaml`:**
| Metric | Description |
|--------|-------------|
| `context_saturation` | % of model's context window used |
| `token_efficiency` | Code generated / prompt tokens |
| `iteration_count` | Implementer ↔ Verifier cycles |
| `time_per_phase` | Wall-clock time per agent |

**Auto-compression trigger:**
- If `context_saturation > 80%`, Maintainer triggers a "Summary & Compress" sub-mission
- Compresses verbose logs while preserving decision history
- Prevents "context rot" in long-running missions

**Sub-tasks:**
- [ ] Add `metrics.yaml` to mission template
- [ ] Implement token counting per agent call
- [ ] Auto-compression logic in Maintainer

---

## 🟡 Phase 2: Orchestration

**Focus:** Move from linear manual chains to dynamic, tool-aware systems.

### 2.1 Mycelium MCP Server 🚀 (The Monetization Engine)

**Action:** Transition Mycelium from a "folder in a repo" to a global MCP Host.

**Mycelium as MCP Host:**
| Tool | Description |
|------|-------------|
| `start_mission` | Initialize a new mission from natural language |
| `verify_logic` | Run the Verifier on current mission state |
| `run_command` | Execute shell commands, return output |
| `grid_exec` | Submit jobs to compute clusters (SLURM, etc.) |
| `arxiv_search` | Pull latest papers by topic |
| `slack_notify` | Send mission updates to Slack |

**Mycelium as MCP Resource:**
- External tools can read mission state
- Tool-aware LLMs can participate in workflow
- Enables multi-agent coordination across systems

**Monetization Strategy:**
| Model | Description |
|-------|-------------|
| **Marketplace Listing** | Publish on Apify Store or Smithery — earn pay-per-event revenue (~$0.01/run) |
| **Outcome-Based Billing** | Charge for "Successful Verifications" or "Completed Missions" not raw API calls |
| **SaaS Gateway** | Local server free; Cloud Historian + Multi-Device Sync = $19/mo subscription |

**Sub-tasks:**
- [ ] Implement standard MCP JSON-RPC interface (TypeScript or Python)
- [ ] Expose `start_mission` and `verify_logic` as MCP Tools
- [ ] Add tool registry for custom tools
- [ ] Authentication for external access
- [ ] Integrate Stripe/Apify for usage-based billing

---

### 2.2 LangGraph Integration

Model agent flow as a graph with cycles and shared state.

**Benefits over linear chains:**
- **Reflection loops** — Verifier ↔ Implementer can cycle N times autonomously before escalating
- **Conditional branching** — Skip Verifier for docs-only changes
- **Checkpoints** — "Time-travel" to previous mission state if agent goes off-track

**Sub-tasks:**
- [ ] Define agent nodes and edges
- [ ] Implement checkpoint save/restore
- [ ] Add max-iteration limits to prevent infinite loops
- [ ] Visualization of mission flow

---

### 2.3 `mycelium next` CLI

Replace manual copy-paste with automated handoffs.

**Modes:**
- `mycelium next` — Invoke next agent based on current state
- `mycelium next --auto` — Auto-approve for low-risk missions
- `mycelium watch` — Daemon that monitors `progress.yaml` and auto-invokes

**Human-in-the-Loop:**
Uses MCP Elicitation primitive to pause for high-risk approvals:
> *"Is it okay to spend $5.00 on this deep-reasoning call?"*

**Sub-tasks:**
- [ ] Implement `mycelium next` CLI
- [ ] File watcher daemon
- [ ] MCP Elicitation for cost/risk approvals
- [ ] Notification hooks (Slack, email) for human-gated steps

---

## 🔴 Phase 3: Intelligence

**Focus:** Multi-model efficiency and long-term recursive learning.

### 3.1 Role-Specific Model Routing

Route agents to appropriate models based on task complexity.

| Agent | Model Type | Rationale |
|-------|------------|-----------|
| Scientist | High-reasoning (Claude Opus, o1) | Complex architectural planning |
| Implementer | Balanced (Claude Sonnet, GPT-4o) | Code generation + context |
| Verifier | Fast/cheap (Gemini Flash, GPT-4o mini) | Parse logs, find "FAIL" |
| Maintainer | Balanced | Refactoring requires judgment |

**Sub-tasks:**
- [ ] Define complexity heuristics
- [ ] Model selection config per agent
- [ ] Cost/latency tracking

---

### 3.2 The Historian Agent

A background crawler that converts completed missions into a **local RAG knowledge base**.

**Responsibilities:**
- Crawl completed `.mycelium/missions/` folders
- Extract patterns, failures, and lessons learned
- Advise Scientist: *"In Mission #42, we tried library X — it had memory leaks on the grid"*
- Automatically warn about previously attempted (and failed) approaches

**Memory bank contents:**
- Successful patterns → reuse
- Failed approaches → avoid
- Dependency conflicts → warn early

**Sub-tasks:**
- [ ] Define memory bank schema
- [ ] Implement mission crawler
- [ ] Build local RAG index (embeddings + retrieval)
- [ ] Integrate with Scientist planning phase

---

### 3.3 Headless Execution

Run long missions autonomously — "set it and forget it."

**Use case:**
> "Test every hyperparameter combination on the JHU CLSP Grid overnight."

**How it works:**
1. Define mission with `headless: true`
2. Agents handle queueing, monitoring, error-recovery
3. On completion, write `mission_complete.yaml` with results
4. Notify user via Slack/email

**Sub-tasks:**
- [ ] Headless mode flag in mission config
- [ ] Robust error recovery (retry logic, dead-letter queue)
- [ ] Automated Slack/Email completion notifications
- [ ] Result visualization (graphs, tables)

---

## Recent Updates

### 2024-12-22: YAML Progress Migration Complete ✅

**Mission:** `progress-yaml-migration`

Migrated progress artifacts from Markdown (`.md`) to YAML (`.yaml`) format:
- Created `PROGRESS_TEMPLATE.yaml` with all original fields preserved
- Updated `mission_organizer` to create `progress.yaml` for new missions
- All agent files now reference YAML format
- Added migration guidance in `WORKFLOW.md`
- Existing missions using `.md` remain backward compatible

This is a prerequisite for Phase 2 automation (schema validation, CLI tooling).

---

## Contributing

To propose roadmap changes, open an issue or submit a PR.
